from django.contrib import admin, messages
from django.utils.html import format_html
import os
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.utils.translation import gettext_lazy as _

from utility.encryption import decrypt, encrypt
from .models import *
from wallet.models import *

# Constants for file extensions
IMAGE_EXTS = {'.jpg', '.jpeg', '.png'}
VIDEO_EXTS = {'.mp4'}


def media_preview(file_field, width=100, video_width=120):
    if not file_field:
        return "No File"

    ext = os.path.splitext(file_field.name)[1].lower()
    url = file_field.url
    if ext in IMAGE_EXTS:
        return format_html(
            '<a href="{0}" target="_blank" style="display:inline-block; width: {1}px;">'
            '<img src="{0}" style="width: 100%; height: auto;" /></a>',
            url, width
        )
    elif ext in VIDEO_EXTS:
        return format_html(
            '<a href="{0}" target="_blank" style="display:inline-block; width: {1}px;">'
            '<video style="width: 100%;" src="{0}" controls></video></a>',
            url, video_width
        )
    return format_html('<a href="{}" target="_blank">View File</a>', url)


class MediaDeleteMixin:
    media_fields = []

    def delete_media(self, obj):
        for field in self.media_fields:
            f = getattr(obj, field)
            if f and f.storage.exists(f.name):
                f.storage.delete(f.name)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            self.delete_media(obj)
        super().delete_queryset(request, queryset)

    def delete_model(self, request, obj):
        self.delete_media(obj)
        super().delete_model(request, obj)


class MediaUpdateMixin:
    media_fields = []

    def delete_old_media_on_update(self, obj):
        if not obj.pk:
            return  # New object, nothing to compare

        try:
            old_obj = obj.__class__.objects.get(pk=obj.pk)
        except obj.__class__.DoesNotExist:
            return

        for field in self.media_fields:
            old_file = getattr(old_obj, field, None)
            new_file = getattr(obj, field, None)

            if old_file and old_file != new_file:
                if old_file.storage.exists(old_file.name):
                    old_file.storage.delete(old_file.name)


@admin.register(Setting)
class SettingAdmin(admin.ModelAdmin):
    list_display = ('get_action_display', 'actionValue', 'updated_at')
    ordering = ('action',)
    list_editable = ('actionValue',)
    list_display_links = None

    fieldsets = (
        ('Settings & Values', {
            'fields': (('action', 'actionValue'),),
        }),
    )

    def has_add_permission(self, request):
        total_choices = len(dict(Setting.CATEGORY_CHOICES))
        current_settings = Setting.objects.count()
        return current_settings < total_choices

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if obj.action == 'X' and obj.actionValue != 'EMPTY':
            try:
                # Skip if already encrypted
                decrypt(obj.actionValue)
            except Exception:
                obj.actionValue = encrypt(obj.actionValue)
        super().save_model(request, obj, form, change)


@admin.register(Status)
class StatusAdmin(MediaDeleteMixin, MediaUpdateMixin, admin.ModelAdmin):
    icon_name = 'art_track'
    list_display = ['category', 'preview',
                    'copy_link', 'uploaded_at', 'isActive']
    list_filter = ['category', 'isActive']
    media_fields = ['status']

    fieldsets = (
        ('Upload Status', {
            'fields': ('category', 'status', 'isActive'),
        }),
    )

    def preview(self, obj):
        return media_preview(obj.status)

    def copy_link(self, obj):
        return format_html(
            '<button style="border:none; padding:6px 3px;" '
            'onclick="navigator.clipboard.writeText(\'{}\'); alert(\'Link Copied Successfully !!!\')">📋 Copy Link</button>',
            obj.status.url
        )

    def save_model(self, request, obj, form, change):
        if change:
            self.delete_old_media_on_update(obj)
        super().save_model(request, obj, form, change)


@admin.register(Product)
class ProductAdmin(MediaDeleteMixin, MediaUpdateMixin, admin.ModelAdmin):
    icon_name = 'shopping_basket'
    list_display = ['title', 'preview', 'price',
                    'strikePrice', 'minWalletBalance', 'isActive']
    search_fields = ['title']
    readonly_fields = ['uploaded_at']
    media_fields = ['image']

    fieldsets = (
        ('Product Details', {
            'fields': (
                ('title', 'price', 'strikePrice', 'minWalletBalance', 'isActive'),
                'image',
            ),
        }),
    )

    def preview(self, obj):
        return media_preview(obj.image)

    def save_model(self, request, obj, form, change):
        if change:
            self.delete_old_media_on_update(obj)
        super().save_model(request, obj, form, change)


@admin.register(ProductOrder)
class ProductOrderAdmin(admin.ModelAdmin):
    icon_name = 'shopping_cart'
    list_display = ('user', 'product', 'status', 'created_at')
    list_filter = ('status',)
    actions = ['approve_orders', 'reject_orders',
               'mark_delivered', 'refund_orders']
    list_display_links = None
    list_per_page = 20

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=...):
        return False

    def has_change_permission(self, request, obj=...):
        return False

    def approve_orders(self, request, queryset):
        queryset.filter(status='P').update(status='A')
        self.message_user(request, f"{queryset.count()} order(s) approved.")

    def reject_orders(self, request, queryset):
        for order in queryset.filter(status='P'):
            order.status = 'R'
            order.save()
        self.message_user(request, f"{queryset.count()} order(s) rejected.")

    def mark_delivered(self, request, queryset):
        queryset.filter(status='A').update(status='D')
        self.message_user(
            request, f"{queryset.count()} order(s) marked as delivered.")

    def refund_orders(self, request, queryset):
        with transaction.atomic():
            for order in queryset.filter(status__in=['P', 'A']):
                wallet = order.user.wallet
                wallet.balance = F('balance') + order.deducted_price
                wallet.save()

                WalletHistory.objects.create(
                    wallet=wallet,
                    transaction_type='P',
                    change=order.deducted_price,
                    isSuccess=True,
                    description=f"Refund for {order.product.title}"
                )
                order.status = 'F'
                order.save()

        self.message_user(request, f"{queryset.count()} order(s) refunded.")

    approve_orders.short_description = "Approve selected orders"
    reject_orders.short_description = "Reject selected orders"
    mark_delivered.short_description = "Mark selected orders as delivered"
    refund_orders.short_description = "Refund selected orders"


@admin.register(Banner)
class BannerAdmin(MediaDeleteMixin, MediaUpdateMixin, admin.ModelAdmin):
    icon_name = 'compare'
    list_display = ['placement', 'category', 'preview', 'uploaded_at']
    list_filter = ['placement', 'category']
    media_fields = ['banner']
    list_display_links = None
    list_editable = ['placement', 'category']

    fieldsets = (
        ('Banner Details', {
            'fields': (('placement', 'category'), 'banner'),
        }),
    )

    def preview(self, obj):
        return media_preview(obj.banner)
    preview.short_description = 'Preview'

    def save_model(self, request, obj, form, change):
        if change:
            self.delete_old_media_on_update(obj)
        super().save_model(request, obj, form, change)


@admin.register(Highlight)
class HighlightAdmin(MediaDeleteMixin, MediaUpdateMixin, admin.ModelAdmin):
    icon_name = 'whatshot'
    list_display = ('title', 'category', 'updated_at',
                    'thumbnail_preview', 'video_preview')
    list_filter = ('category', 'updated_at')
    search_fields = ('title',)
    readonly_fields = ('thumbnail_preview', 'video_preview')
    media_fields = ['thumbnail', 'video']
    list_display_links = None

    fieldsets = (
        ("Highlight Info", {
            'fields': (('category', 'title'),),
            'classes': ('wide',),
        }),
        ("Media Uploads", {
            'fields': (('thumbnail', 'video'),),
            'classes': ('wide',),
        }),
    )

    def thumbnail_preview(self, obj):
        return media_preview(obj.thumbnail)

    thumbnail_preview.short_description = "Thumbnail Preview"

    def video_preview(self, obj):
        return media_preview(obj.video)

    video_preview.short_description = "Video Preview"

    def has_change_permission(self, request, obj=...):
        return False

    def save_model(self, request, obj, form, change):
        if change:
            self.delete_old_media_on_update(obj)
        super().save_model(request, obj, form, change)


@admin.register(LearningVideo)
class LearningVideoAdmin(MediaDeleteMixin, MediaUpdateMixin, admin.ModelAdmin):
    icon_name = 'video_library'
    list_display = ('title', 'language', 'updated_at',
                    'thumbnail_preview', 'video_preview')
    list_filter = ('language',)
    search_fields = ('title', 'language')
    readonly_fields = ('thumbnail_preview', 'video_preview')
    media_fields = ['thumbnail', 'video']

    fieldsets = (
        (None, {
            'fields': (('language', 'title'), ('video', 'thumbnail'))
        }),
    )

    def thumbnail_preview(self, obj):
        return media_preview(obj.thumbnail)

    thumbnail_preview.short_description = "Thumbnail Preview"

    def video_preview(self, obj):
        return media_preview(obj.video)

    video_preview.short_description = "Video Preview"

    def save_model(self, request, obj, form, change):
        if change:
            self.delete_old_media_on_update(obj)
        super().save_model(request, obj, form, change)
