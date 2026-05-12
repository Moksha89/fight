from django.contrib import admin
from .models import *
from base.admin import media_preview, MediaDeleteMixin
from base.admin import *

class GiftPoolGiftsInline(admin.TabularInline):
    model = GiftPoolGifts
    extra = 1


class GiftPoolWinnerInline(admin.TabularInline):
    model = GiftPoolWinner
    extra = 1



@admin.register(GiftPool)
class GiftPoolAdmin(MediaDeleteMixin, MediaUpdateMixin, admin.ModelAdmin):
    icon_name = 'card_giftcard'
    list_display = ['name', 'preview', 'amount', 'minWalletBalance', 'liveDate', 'closingDate', 'isLocked']
    list_filter = ['isLocked', 'liveDate', 'closingDate']
    search_fields = ['name']
    inlines = [GiftPoolGiftsInline, GiftPoolWinnerInline]
    media_fields = ['image']

    fieldsets = (
        ("Basic Info", {
            'fields': (('name', 'image'),)
        }),
        ("Conditions", {
            'fields': (('amount', 'minWalletBalance', 'isLocked'),)
        }),
        ("Schedule", {
            'fields': (('liveDate', 'closingDate'),)
        }),
    )


    def preview(self, obj):
        return media_preview(obj.image)
    

    def save_model(self, request, obj, form, change):
        if change:
            self.delete_old_media_on_update(obj)
        super().save_model(request, obj, form, change)



@admin.register(PricePoolStream)
class PricePoolStreamAdmin(MediaDeleteMixin, MediaUpdateMixin, admin.ModelAdmin):
    icon_name = 'play_circle_outline'
    list_display = ['roomSize', 'winningNumbers', 'lastUpdated', 'video_preview']
    list_filter = ['lastUpdated']
    search_fields = ['roomSize', 'winningNumbers']
    readonly_fields = ['video_preview']
    media_fields = ['video']
    list_per_page = 20
    list_max_show_all = 50

    fieldsets = (
        ("Stream Details", {
            'fields': (('roomSize', 'winningNumbers', 'video',),),
            'classes': ('wide',),
        }),
    )

    def video_preview(self, obj):
        return media_preview(obj.video)

    video_preview.short_description = "Video Preview"


    def save_model(self, request, obj, form, change):
        if change:
            self.delete_old_media_on_update(obj)
        super().save_model(request, obj, form, change)



@admin.register(PricePoolRange)
class PricePoolRangeAdmin(admin.ModelAdmin):
    icon_name = 'multiline_chart'
    list_display = ['price', 'lastUpdated']

    fieldsets = (
        ("Range Info", {
            'fields': (('price',),)
        }),
    )


class PricePoolGiftsInline(admin.TabularInline):
    model = PricePoolGifts
    extra = 1


@admin.register(PricePool)
class PricePoolAdmin(admin.ModelAdmin):
    icon_name = 'blur_on'
    list_display = ['range', 'ticketCount', 'timeIntervalMin', 'isLocked', 'isClosed']
    list_filter = ['isLocked', 'isClosed']
    inlines = [PricePoolGiftsInline]

    fieldsets = (
        ("Schedule", {
            'fields': (('range', 'ticketCount', 'timeIntervalMin'),)
        }),
        ("Status", {
            'fields': (('isLocked', 'isClosed'),)
        }),
    )

