from django.contrib import admin
from django.utils.html import format_html
from django.contrib import messages
from django.utils.translation import ngettext
from django.db import transaction, IntegrityError
from .models import *
from userManager.models import *
from django.db.models import F
from django.utils.translation import gettext_lazy as _
from django.db.models import BooleanField, ExpressionWrapper, Q

from base.admin import *
from django.urls import reverse
from django.utils.html import format_html

from django.urls import path
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from userManager.models import User

from django.contrib.admin import DateFieldListFilter


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    icon_name = 'account_balance_wallet'
    list_display = ('user', 'user_email', 'gain_flag', 'fundsIn', 'fundsOut', 'balance_link',
                    'exposure_display', 'available_balance_display', 'running_bonus', 'updated_at', 'toggle_user_status_link')
    search_fields = ('user__id', 'user__username',
                     'user__email', 'user__phoneNumber')
    list_filter = (('updated_at', DateFieldListFilter),)
    readonly_fields = ('updated_at',)
    list_display_links = None
    list_per_page = 10
    list_max_show_all = 100

    actions = ['manual_deposit', 'manual_withdraw']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=...):
        return False

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('user')

    @admin.action(description="Manual Deposit ₹1000")
    def manual_deposit(self, request, queryset):
        from decimal import Decimal
        count = 0
        for wallet in queryset:
            wallet.balance += Decimal('1000')
            wallet.fundsIn += Decimal('1000')
            wallet.save()
            WalletHistory.objects.create(
                wallet=wallet,
                transaction_type='D',
                change=Decimal('1000'),
                isSuccess=True,
                description='Manual deposit by admin'
            )
            count += 1
        self.message_user(request, f"₹1000 deposited to {count} wallet(s).", level='success')

    @admin.action(description="Manual Withdraw ₹1000")
    def manual_withdraw(self, request, queryset):
        from decimal import Decimal
        count = 0
        for wallet in queryset:
            if wallet.balance >= Decimal('1000'):
                wallet.balance -= Decimal('1000')
                wallet.fundsOut += Decimal('1000')
                wallet.save()
                WalletHistory.objects.create(
                    wallet=wallet,
                    transaction_type='W',
                    change=Decimal('-1000'),
                    isSuccess=True,
                    description='Manual withdrawal by admin'
                )
                count += 1
        self.message_user(request, f"₹1000 withdrawn from {count} wallet(s).", level='success')

    def running_bonus(self, obj):
        return obj.bonusDebt

    def exposure_display(self, obj):
        exp = obj.exposure
        if exp > 0:
            return format_html('<span style="color:#f59e0b;font-weight:bold;">₹{}</span>', exp)
        return format_html('<span style="color:#6b7280;">₹0</span>')
    exposure_display.short_description = 'Exposure'

    def available_balance_display(self, obj):
        avail = obj.available_balance
        color = '#10b981' if avail > 0 else '#ef4444'
        return format_html('<span style="color:{};font-weight:bold;">₹{}</span>', color, avail)
    available_balance_display.short_description = 'Available'

    def balance_link(self, obj):
        url = (
            reverse("admin:wallet_wallethistory_changelist")
            + f"?wallet__exact={obj.pk}"
        )
        return format_html('<a href="{}">{}</a>', url, obj.balance)
    balance_link.short_description = 'Balance'

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = "Email"

    def toggle_user_status_link(self, obj):
        if obj.user.is_active:
            label = "Active"
            color = "green"
        else:
            label = "In-Active"
            color = "red"

        url = reverse("admin:toggle_user_active", args=[obj.user.pk])
        return format_html('<a style="color:{};" href="{}">{}</a>', color, url, label)

    toggle_user_status_link.short_description = "User Account Status"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'toggle-user/<str:user_id>/',
                self.admin_site.admin_view(self.toggle_user_active),
                name='toggle_user_active',
            ),
        ]
        return custom_urls + urls

    def toggle_user_active(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)
        user.is_active = not user.is_active
        user.save()
        messages.success(
            request, f"User {user.username} is now {'active' if user.is_active else 'inactive'}.")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/admin/'))

    def gain_flag(self, obj):
        net_gain = (obj.balance - obj.bonusDebt) + obj.fundsOut - obj.fundsIn

        if net_gain > 0:
            return format_html('<span title="Profit" style="color:red;font-size:18px;">🔺</span>')
        elif net_gain < 0:
            return format_html('<span title="Loss" style="color:green;font-size:18px;">☘️</span>')
        else:
            return format_html('<span title="No Change" style="color:gray;font-size:18px;">●</span>')

    gain_flag.short_description = 'Account Health'


@admin.register(WalletHistory)
class WalletHistoryAdmin(admin.ModelAdmin):
    icon_name = 'clear_all'
    list_display = (
        'transactionHash', 'customer_name', 'transaction_type_icon', 'isSuccess', 'change', 'description', 'created_at', 'linked_transaction'
    )
    list_filter = ('transaction_type', 'isSuccess', 'created_at')
    search_fields = (
        'wallet__user__username', 'wallet__user__email', 'wallet__user__phoneNumber', 'description', 'transactionHash'
    )
    readonly_fields = (
        'transactionHash', 'wallet', 'transaction_type', 'transactionId', 'change',
        'isSuccess', 'description', 'created_at'
    )
    list_display_links = None
    list_per_page = 20
    list_max_show_all = 40
    actions = ['export_statement_csv']

    @admin.action(description="Download as CSV")
    def export_statement_csv(self, request, queryset):
        import csv
        from django.http import HttpResponse as HR
        from django.utils import timezone as tz
        response = HR(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="statement_{tz.now().strftime("%Y%m%d_%H%M")}.csv"'
        writer = csv.writer(response)
        writer.writerow(['Hash', 'User', 'Phone', 'Type', 'Amount', 'Success', 'Description', 'Date'])
        for wh in queryset.select_related('wallet__user'):
            writer.writerow([
                wh.transactionHash or '-',
                wh.wallet.user.email if wh.wallet and wh.wallet.user else '-',
                wh.wallet.user.phoneNumber if wh.wallet and wh.wallet.user else '-',
                wh.get_transaction_type_display(),
                wh.change,
                'Yes' if wh.isSuccess else 'No',
                wh.description,
                wh.created_at.strftime('%Y-%m-%d %H:%M') if wh.created_at else '-'
            ])
        return response

    def customer_name(self, obj):
        if obj.wallet and obj.wallet.user:
            user = obj.wallet.user
            return f"{user.username} - {user.phoneNumber}"
        return '-'
    customer_name.short_description = "Customer"

    def user(self, obj):
        return obj.wallet.user
    user.short_description = "User"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def linked_transaction(self, obj):
        if (obj.transaction_type == 'D' or obj.transaction_type == 'W') and obj.isSuccess:
            url = (reverse("admin:userManager_settlementhistory_changelist") +
                   f"?id__exact={obj.transactionId}")
            return format_html('<a class="button" style="background:#000;color:#fff;padding:0.5rem 2rem;" href="{}">View</a>', url)
        return "N/A"

    linked_transaction.short_description = "Action"

    def transaction_type_icon(self, obj):
        icons = {
            'D': '<span style="color:#10b981;font-size:16px;">&#8595; Deposit</span>',
            'W': '<span style="color:#ef4444;font-size:16px;">&#8593; Withdraw</span>',
            'B': '<span style="color:#f59e0b;font-size:16px;">&#9733; Bonus</span>',
            'F': '<span style="color:#8b5cf6;font-size:16px;">&#9876; Cockfight</span>',
            'I': '<span style="color:#3b82f6;font-size:16px;">&#9858; Dice</span>',
            'C': '<span style="color:#ef4444;font-size:16px;">&#9917; Cricket</span>',
            'L': '<span style="color:#eab308;font-size:16px;">&#127922; Lottery</span>',
            'S': '<span style="color:#6b7280;font-size:16px;">&#128176; Sub</span>',
        }
        return format_html(icons.get(obj.transaction_type, obj.get_transaction_type_display()))
    transaction_type_icon.short_description = "Type"


@admin.register(PaymentQR)
class PaymentQRAdmin(admin.ModelAdmin):
    icon_name = 'qr_code'
    list_display = ('display_name', 'upi_id', 'is_active', 'min_deposit', 'max_deposit',
                    'daily_limit_display', 'daily_credited', 'limit_status', 'auto_disable_on_limit',
                    'rotation_priority', 'qr_preview')
    list_filter = ('is_active', 'auto_disable_on_limit')
    search_fields = ('upi_id', 'display_name')
    list_editable = ('is_active', 'rotation_priority', 'auto_disable_on_limit')
    list_per_page = 20

    fieldsets = (
        (None, {
            'fields': (
                ('display_name', 'upi_id'),
                'qr_image',
                ('min_deposit', 'max_deposit'),
                'is_active',
            ),
        }),
        ('Daily Credit Limit', {
            'classes': ('collapse',),
            'fields': (
                'daily_limit',
                'auto_disable_on_limit',
            ),
            'description': 'Set max amount that can be credited in 24hrs. 0 = unlimited. Auto-disable hides QR when limit reached; re-enables after 24hrs.',
        }),
        ('Advanced', {
            'classes': ('collapse',),
            'fields': (
                ('daily_credited', 'rotation_priority'),
            ),
        }),
    )

    def daily_limit_display(self, obj):
        if obj.daily_limit <= 0:
            return 'Unlimited'
        return f'₹{obj.daily_limit:,.0f}'
    daily_limit_display.short_description = '24hr Limit'

    def limit_status(self, obj):
        if obj.daily_limit <= 0:
            return format_html('<span style="color:#10b981;">No limit</span>')
        remaining = obj.limit_remaining
        pct = (float(obj.daily_credited) / float(obj.daily_limit)) * 100 if obj.daily_limit > 0 else 0
        if pct >= 100:
            return format_html('<span style="color:#ef4444;font-weight:bold;">FULL (₹{} remaining)</span>', remaining)
        elif pct >= 75:
            return format_html('<span style="color:#f59e0b;">₹{} remaining</span>', remaining)
        else:
            return format_html('<span style="color:#10b981;">₹{} remaining</span>', remaining)
    limit_status.short_description = 'Remaining'

    def qr_preview(self, obj):
        if obj.qr_image:
            return format_html('<img src="{}" style="height:40px;border-radius:4px;" />', obj.qr_image.url)
        return '-'
    qr_preview.short_description = 'QR'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(created_by=request.user)

    def save_model(self, request, obj, form, change):
        if not change or not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(PaymentBankAccount)
class PaymentBankAccountAdmin(admin.ModelAdmin):
    icon_name = 'account_balance'
    list_display = ('account_holder_name', 'bank_name', 'account_number', 'ifsc_code', 'account_type',
                    'is_active', 'min_deposit', 'max_deposit', 'daily_limit_display',
                    'daily_credited', 'limit_status', 'auto_disable_on_limit', 'rotation_priority')
    list_filter = ('is_active', 'account_type', 'auto_disable_on_limit')
    search_fields = ('account_holder_name', 'bank_name', 'account_number')
    list_editable = ('is_active', 'rotation_priority', 'auto_disable_on_limit')
    list_per_page = 20

    fieldsets = (
        (None, {
            'fields': (
                ('account_holder_name', 'bank_name'),
                ('account_number', 'ifsc_code'),
                ('account_type', 'min_deposit', 'max_deposit'),
                'is_active',
            ),
        }),
        ('Daily Credit Limit', {
            'classes': ('collapse',),
            'fields': (
                'daily_limit',
                'auto_disable_on_limit',
            ),
            'description': 'Set max amount that can be credited in 24hrs. 0 = unlimited. Auto-disable hides account when limit reached; re-enables after 24hrs.',
        }),
        ('Advanced', {
            'classes': ('collapse',),
            'fields': (
                ('daily_credited', 'rotation_priority'),
            ),
        }),
    )

    def daily_limit_display(self, obj):
        if obj.daily_limit <= 0:
            return 'Unlimited'
        return f'₹{obj.daily_limit:,.0f}'
    daily_limit_display.short_description = '24hr Limit'

    def limit_status(self, obj):
        if obj.daily_limit <= 0:
            return format_html('<span style="color:#10b981;">No limit</span>')
        remaining = obj.limit_remaining
        pct = (float(obj.daily_credited) / float(obj.daily_limit)) * 100 if obj.daily_limit > 0 else 0
        if pct >= 100:
            return format_html('<span style="color:#ef4444;font-weight:bold;">FULL (₹{} remaining)</span>', remaining)
        elif pct >= 75:
            return format_html('<span style="color:#f59e0b;">₹{} remaining</span>', remaining)
        else:
            return format_html('<span style="color:#10b981;">₹{} remaining</span>', remaining)
    limit_status.short_description = 'Remaining'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(created_by=request.user)

    def save_model(self, request, obj, form, change):
        if not change or not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(DepositRequest)
class DepositRequestAdmin(admin.ModelAdmin):
    icon_name = 'file_download'
    list_display = ['customer_phone', 'status_badge', 'deposit_type', 'utr_id',
                    'deposit_amount', 'confirm_amount', 'updated_at', 'infoNote', 'view_screenshot']
    search_fields = ['utr_id']
    list_filter = ['status', 'deposit_type']
    list_display_links = None
    list_editable = ['utr_id', 'deposit_amount', 'confirm_amount', 'infoNote']
    list_per_page = 5
    list_max_show_all = 5
    actions = ['verify_deposit_requests', 'reject_deposit_requests']
    readonly_fields = ['customer']

    fieldsets = (
        (None, {
            'fields': (
                ('deposit_type', 'utr_id', 'deposit_amount', 'confirm_amount'),
            ),
            'classes': ('wide',),
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        searchParm = request.GET.get('q')
        if searchParm:
            return qs
        return qs.exclude(customer=None)

    def view_screenshot(self, obj):
        if obj.screenShort:
            return format_html(
                '<a class="button" style="padding: 5px 10px; background-color: #4CAF50; color: white; border-radius: 4px; text-decoration: none;" href="{}" target="_blank">View Screenshot</a>',
                obj.screenShort.url
            )
        return "NAN"
    view_screenshot.short_description = "Screenshot"

    def customer_phone(self, obj):
        return f"{obj.customer.username} - {obj.customer.phoneNumber}" if obj.customer else 'No Customer'
    customer_phone.short_description = 'Customer Phone'

    def status_badge(self, obj):
        colors = {'P': '#f59e0b', 'A': '#10b981', 'R': '#ef4444'}
        labels = {'P': 'Pending', 'A': 'Accepted', 'R': 'Rejected'}
        color = colors.get(obj.status, '#6b7280')
        label = labels.get(obj.status, 'Unknown')
        return format_html('<span style="color:{};font-weight:bold;">{}</span>', color, label)
    status_badge.short_description = 'Status'

    def has_delete_permission(self, request, obj=None):
        return False

    def get_unprocessed_settlement_box(self, staff_user):
        return SettlementBox.objects.filter(user=staff_user, isProcessed=False).first()

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)

        class CustomForm(form):
            def clean(self_inner):
                cleaned_data = super().clean()
                deposit = cleaned_data.get("deposit_amount")
                confirm = cleaned_data.get("confirm_amount")

                if deposit is not None and confirm is not None and deposit != confirm:
                    self_inner.add_error('confirm_amount', _(
                        "Confirm amount must match the deposit amount."))
                return cleaned_data
        return CustomForm

    def save_model(self, request, obj, form, change):
        staff_user = request.user
        settlement_box = self.get_unprocessed_settlement_box(staff_user)

        if not change:  # only on creation

            try:
                with transaction.atomic():
                    existing = DepositRequest.objects.select_for_update().filter(
                        utr_id=obj.utr_id).first()

                    if existing:
                        customer = existing.customer
                        amount = obj.deposit_amount

                        if not customer:
                            self.message_user(
                                request, f"UTR {obj.utr_id} already exists but without a customer. Cannot verify.", level=messages.WARNING)
                            return

                        settlementHistory = None

                        if settlement_box:
                            settlement_box.verifiedValue = F(
                                'verifiedValue') + amount
                            settlement_box.save()

                            settlementHistory = SettlementHistory.objects.create(
                                settlementBox=settlement_box,
                                utr_id=obj.utr_id,
                                customer=customer,
                                transaction_type='D',
                                amount=amount
                            )

                        wallet, isCreated = Wallet.objects.get_or_create(
                            user=customer)

                        wallet.balance = F('balance') + amount
                        wallet.fundsIn = F('fundsIn') + amount
                        wallet.save()

                        WalletHistory.objects.create(
                            wallet=wallet,
                            transaction_type='D',
                            transactionId=settlementHistory.id if settlementHistory else None,
                            change=amount,
                            isSuccess=True,
                            description=f"Deposit via {existing.get_deposit_type_display()} with UTR {existing.utr_id}"
                        )

                        existing.delete()
                        self.message_user(
                            request, f"Customer deposit request with UTR {obj.utr_id} verified successfully.", messages.SUCCESS)
                        return

                    obj.customer = None
                    super().save_model(request, obj, form, change)

                    if settlement_box:
                        settlement_box.verifiedValue = F(
                            'verifiedValue') + obj.deposit_amount
                        settlement_box.save()

                        SettlementHistory.objects.create(
                            settlementBox=settlement_box,
                            utr_id=obj.utr_id,
                            customer=None,
                            transaction_type='D',
                            amount=obj.deposit_amount
                        )

                        self.message_user(
                            request, f"Deposit with UTR {obj.utr_id} added to your SettlementBox.", messages.SUCCESS)
                    else:
                        self.message_user(
                            request, "No unprocessed SettlementBox found for you.", messages.WARNING)
            except IntegrityError:
                self.message_user(
                    request, f"Failed to save deposit with UTR {obj.utr_id} due to a database error (possibly duplicate UTR).", level=messages.ERROR)
        else:
            super().save_model(request, obj, form, change)

    def verify_deposit_requests(self, request, queryset):
        staff_user = request.user
        settlement_box = self.get_unprocessed_settlement_box(staff_user)
        count = 0

        try:
            with transaction.atomic():
                for deposit in queryset.select_for_update():

                    if (deposit.deposit_amount != deposit.confirm_amount) or not deposit.confirm_amount:
                        self.message_user(
                            request, f"The confirm value is not matched with deposit value.", messages.WARNING)
                        continue

                    customer = deposit.customer
                    if not customer:
                        self.message_user(
                            request, f"Skipping UTR {deposit.utr_id} as it has no customer.", messages.WARNING)
                        continue

                    amount = deposit.deposit_amount

                    settlementHistory = None

                    if settlement_box:
                        settlement_box.verifiedValue = F(
                            'verifiedValue') + amount
                        settlement_box.save()

                        settlementHistory = SettlementHistory.objects.create(
                            settlementBox=settlement_box,
                            utr_id=deposit.utr_id,
                            customer=customer,
                            transaction_type='D',
                            amount=amount
                        )

                    wallet, _ = Wallet.objects.get_or_create(user=customer)

                    wallet.balance = F('balance') + amount
                    wallet.fundsIn = F('fundsIn') + amount
                    wallet.save()

                    WalletHistory.objects.create(
                        wallet=wallet,
                        transaction_type='D',
                        transactionId=settlementHistory.id if settlementHistory else None,
                        change=amount,
                        isSuccess=True,
                        description=f"Deposit via {deposit.get_deposit_type_display()} with UTR {deposit.utr_id}"
                    )

                    deposit.delete()
                    count += 1

                self.message_user(request, ngettext(
                    '%d deposit request was verified successfully.',
                    '%d deposit requests were verified successfully.',
                    count
                ) % count, messages.SUCCESS)
        except IntegrityError:
            self.message_user(
                request, "Identified Duplicate UTR ID. No changes were saved.", level=messages.ERROR)

    @admin.action(description="Reject selected deposit requests")
    def reject_deposit_requests(self, request, queryset):
        count = 0
        missing_info = []

        try:
            with transaction.atomic():
                for deposit in queryset.select_for_update():
                    customer = deposit.customer
                    if not customer:
                        self.message_user(
                            request, f"Skipping UTR {deposit.utr_id} with no customer for rejection.", messages.WARNING)
                        continue

                    if not deposit.infoNote or deposit.infoNote.strip() == "":
                        missing_info.append(deposit.utr_id)
                        continue

                    amount = deposit.deposit_amount
                    wallet, _ = Wallet.objects.get_or_create(user=customer)

                    WalletHistory.objects.create(
                        wallet=wallet,
                        transaction_type='D',
                        change=amount,
                        isSuccess=False,
                        description=f"Rejected deposit, {deposit.infoNote}"
                    )

                    deposit.delete()
                    count += 1

                if count:
                    self.message_user(request, ngettext(
                        '%d deposit request was rejected.',
                        '%d deposit requests were rejected.',
                        count
                    ) % count, messages.WARNING)

                if missing_info:
                    self.message_user(
                        request,
                        f"Skipped {len(missing_info)} request(s) due to missing 'infoNote'. UTRs: {', '.join(missing_info)}",
                        level=messages.ERROR
                    )

        except IntegrityError:
            self.message_user(
                request, "An error occurred while rejecting deposit requests. No changes were saved.",
                level=messages.ERROR)


@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    icon_name = 'file_upload'
    list_display = [
        'customer',
        'status_badge',
        'customer_real_balance_link',
        'withdrawal_amount',
        'customer_details',
        'handling_by',
        'utr_id',
        'view_admin_screenshot',
        'infoNote',
        'updated_at'
    ]
    search_fields = ['upi_id', 'account_number', 'customer__username']
    list_filter = ['status', 'withdrawal_type']
    list_display_links = None
    list_per_page = 5
    list_editable = ['utr_id', 'infoNote']
    list_max_show_all = 5
    actions = [
        'handle_withdrawal_requests',
        'verify_withdrawal_requests',
        'reject_withdrawal_requests'
    ]

    def view_admin_screenshot(self, obj):
        if obj.admin_screenshot:
            return format_html(
                '<a class="button" style="padding:5px 10px;background:#4CAF50;color:white;border-radius:4px;text-decoration:none;" href="{}" target="_blank">View Proof</a>',
                obj.admin_screenshot.url
            )
        return '-'
    view_admin_screenshot.short_description = 'Payment Proof'

    def customer_real_balance_link(self, obj):
        wallet = getattr(obj.customer, "wallet", None)
        if wallet:
            url = reverse("admin:wallet_wallet_changelist") + \
                f"?user__exact={wallet.pk}"
            return format_html('<a href="{}">{}</a>', url, wallet.balance - wallet.bonusDebt)
        return "N/A"

    customer_real_balance_link.short_description = "Customer Real Balance"

    def customer_phone(self, obj):
        return f"{obj.customer.username} - {obj.customer.phoneNumber}" if obj.customer else 'No Customer'
    customer_phone.short_description = 'Customer Phone'

    def status_badge(self, obj):
        colors = {'P': '#f59e0b', 'A': '#10b981', 'R': '#ef4444'}
        labels = {'P': 'Pending', 'A': 'Accepted', 'R': 'Rejected'}
        color = colors.get(obj.status, '#6b7280')
        label = labels.get(obj.status, 'Unknown')
        return format_html('<span style="color:{};font-weight:bold;">{}</span>', color, label)
    status_badge.short_description = 'Status'

    def customer_details(self, obj):
        if obj.withdrawal_type == 'U':
            return format_html(
                "<strong>UPI ID:</strong><br>{}",
                obj.upi_id or "—"
            )
        elif obj.withdrawal_type == 'B':
            return format_html(
                "<strong>Account Number:</strong> {}<br>"
                "<strong>IFSC Code:</strong> {}<br>"
                "<strong>Account Holder:</strong> {}",
                obj.account_number or "—",
                obj.ifsc_code or "—",
                obj.account_holder_name or "—"
            )
        return "-"
    customer_details.short_description = "Customer Details"
    customer_details.allow_tags = True

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.GET.get('q'):
            return qs
        return qs.annotate(
            is_mine=ExpressionWrapper(
                Q(handling_by=request.user),
                output_field=BooleanField()
            )
        ).order_by('-is_mine', '-updated_at')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_changelist_form(self, request, **kwargs):
        """Add admin_screenshot to the changelist form for inline editing."""
        from django import forms
        class WithdrawalChangeListForm(forms.ModelForm):
            class Meta:
                model = WithdrawalRequest
                fields = ['utr_id', 'infoNote', 'admin_screenshot']
        kwargs['form'] = WithdrawalChangeListForm
        return super().get_changelist_form(request, **kwargs)

    def save_model(self, request, obj, form, change):
        if change and 'utr_id' in form.changed_data:
            if obj.handling_by != request.user:
                self.message_user(
                    request, "You can only update UTR ID for requests you're handling.", messages.WARNING)
                return
        # Handle file upload for admin_screenshot
        if 'admin_screenshot' in request.FILES:
            obj.admin_screenshot = request.FILES['admin_screenshot']
        super().save_model(request, obj, form, change)

    @admin.action(description="Handle selected withdrawal requests")
    def handle_withdrawal_requests(self, request, queryset):
        count = 0
        for withdrawal in queryset:
            if withdrawal.handling_by is not None:
                self.message_user(
                    request,
                    f"Withdrawal request for {withdrawal.customer} is already being handled by {withdrawal.handling_by}.",
                    messages.WARNING
                )
                continue
            withdrawal.handling_by = request.user
            withdrawal.save()
            count += 1

        self.message_user(
            request,
            ngettext(
                '%d withdrawal request is now being handled by you.',
                '%d withdrawal requests are now being handled by you.',
                count,
            ) % count,
            messages.SUCCESS
        )

    @admin.action(description="Verify selected withdrawal requests")
    def verify_withdrawal_requests(self, request, queryset):
        count = 0
        errors = []
        try:
            with transaction.atomic():
                for withdrawal in queryset.select_for_update():
                    if withdrawal.handling_by is None:
                        errors.append(
                            f"Withdrawal for {withdrawal.customer} cannot be verified because it is not handled yet.")
                        continue
                    if withdrawal.handling_by != request.user:
                        errors.append(
                            f"You are not authorized to verify withdrawal for {withdrawal.customer}.")
                        continue
                    if not withdrawal.utr_id:
                        errors.append(
                            f"Withdrawal for {withdrawal.customer} cannot be verified because UTR ID is missing.")
                        continue

                    try:
                        settlement_box = SettlementBox.objects.get(
                            user=request.user, isProcessed=False)
                    except SettlementBox.DoesNotExist:
                        errors.append(
                            f"No unprocessed SettlementBox found for staff {request.user}.")
                        continue

                    amount = withdrawal.withdrawal_amount

                    settlement_box.verifiedValue = F('verifiedValue') - amount
                    settlement_box.save()

                    settlementHistory = SettlementHistory.objects.create(
                        settlementBox=settlement_box,
                        customer=withdrawal.customer,
                        transaction_type='W',
                        utr_id=withdrawal.utr_id,
                        amount=amount
                    )

                    wallet = withdrawal.customer.wallet

                    wallet.fundsOut = F('fundsOut') + amount
                    wallet.save()

                    WalletHistory.objects.create(
                        wallet=wallet,
                        transaction_type='W',
                        transactionId=settlementHistory.id if settlementHistory else None,
                        change=amount,
                        isSuccess=True,
                        description=f"Withdrawal verified with UTR: {withdrawal.utr_id}"
                    )

                    withdrawal.delete()
                    count += 1
        except IntegrityError:
            self.message_user(
                request, "Identified Duplicate UTR ID. No changes were saved.", level=messages.ERROR)

        self.message_user(
            request,
            ngettext(
                '%d withdrawal request was verified and processed.',
                '%d withdrawal requests were verified and processed.',
                count,
            ) % count,
            messages.SUCCESS
        )

    @admin.action(description="Reject selected withdrawal requests")
    def reject_withdrawal_requests(self, request, queryset):
        count = 0
        missing_info = 0

        with transaction.atomic():
            for withdrawal in queryset.select_for_update():
                customer = withdrawal.customer
                amount = withdrawal.withdrawal_amount

                if not withdrawal.infoNote or withdrawal.infoNote.strip() == "":
                    missing_info += 1
                    continue

                wallet, _ = Wallet.objects.get_or_create(user=customer)

                wallet.balance = F('balance') + amount
                wallet.save()

                WalletHistory.objects.create(
                    wallet=wallet,
                    transaction_type='W',
                    change=-amount,
                    isSuccess=False,
                    description=f"Rejected withdrawal, {withdrawal.infoNote}"
                )

                withdrawal.delete()
                count += 1

        self.message_user(
            request,
            ngettext(
                '%d withdrawal request was rejected and deleted.',
                '%d withdrawal requests were rejected and deleted.',
                count,
            ) % count,
            messages.WARNING
        )

        if missing_info != 0:
            self.message_user(
                request,
                f"Skipped {missing_info} request(s) due to missing 'infoNote'.",
                level=messages.ERROR
            )


@admin.register(BonusRange)
class BonusSettingAdmin(admin.ModelAdmin):
    icon_name = "pie_chart"
    list_display = ['min_deposit', 'bonus_type', 'bonus_value',
                    'only_first_deposit', 'updated_at']
    list_filter = ("only_first_deposit",)
    fieldsets = (
        ('Bonus Tier Configuration', {
            'fields': [('min_deposit', 'bonus_type', 'bonus_value', 'only_first_deposit'),],
            'description': 'Define the minimum deposit amount and the corresponding bonus.'
        }),
    )
