import logging

from django.contrib import admin
from .models import *
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.urls import reverse, path
from django.utils.html import format_html
from django.contrib import messages
from django.db.models import Q, F
from django.http import HttpResponseRedirect, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.template.response import TemplateResponse
from decimal import Decimal
import csv
from django.utils import timezone
from kokoroko.security import log_admin_action, get_client_ip

security_logger = logging.getLogger("kokoroko.security")


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    icon_name = 'view_carousel'
    list_display = ('name', 'user_count_link')
    search_fields = ['name']
    autocomplete_fields = ['manager']

    def user_count_link(self, obj):
        count = obj.users.count()
        url = (
            reverse(
                f"admin:{User._meta.app_label}_{User._meta.model_name}_changelist")
            + f"?room__id__exact={obj.id}"
        )
        return format_html('<a href="{}">{}</a>', url, count)

    user_count_link.short_description = "Users in Room"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    icon_name = 'person'
    list_display = ["phoneNumber", "username", "wallet_balance_display", "risk_badge", "status_badge", "joinedDate", "action_buttons"]
    search_fields = ["phoneNumber", "username", "email"]
    list_filter = ["is_active", "is_staff", "room"]
    readonly_fields = ["last_login", "joinedDate"]
    autocomplete_fields = ['room']
    list_per_page = 25
    list_display_links = ["phoneNumber"]
    ordering = ['-joinedDate']

    fieldsets = (
        (None, {"fields": [("phoneNumber", "email", "last_login"), "password"]}),
        (
            ("Personal info"),
            {"fields": [("username", "dateOfBirth", "gender", "room")]},
        ),
        (
            ("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": [("phoneNumber", "username", "email"), ("password1", "password2")],
            },
        ),
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('wallet')

    change_list_template = 'admin/userManager/user/change_list.html'

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['users_count'] = User.objects.filter(is_staff=False).count()
        extra_context['admin_count'] = User.objects.filter(is_staff=True).count()
        extra_context['export_url'] = reverse("admin:export_users_csv")
        # Default to showing users (non-staff) if no filter is applied
        if 'is_staff__exact' not in request.GET and 'is_active__exact' not in request.GET:
            from django.http import HttpResponseRedirect
            return HttpResponseRedirect(request.path + '?is_staff__exact=0')
        return super().changelist_view(request, extra_context=extra_context)

    def wallet_balance_display(self, obj):
        try:
            bal = obj.wallet.balance
            return format_html('<span style="font-weight:bold;color:#1a73e8;">₹{}</span>', bal)
        except Exception:
            return format_html('<span style="color:#999;">No wallet</span>')
    wallet_balance_display.short_description = "Balance"

    def status_badge(self, obj):
        if obj.is_active:
            return format_html('<span style="background:#4caf50;color:#fff;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:bold;">Active</span>')
        return format_html('<span style="background:#f44336;color:#fff;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:bold;">Blocked</span>')
    status_badge.short_description = "Status"

    def risk_badge(self, obj):
        try:
            from kokoroko.risk_detection import get_user_risk_summary
            summary = get_user_risk_summary(obj)
            level = summary.get("level", "LOW")
            count = summary.get("count", 0)
            if count == 0:
                return format_html('<span style="background:#4caf50;color:#fff;padding:3px 8px;border-radius:12px;font-size:10px;">LOW</span>')
            colors = {"LOW": "#4caf50", "MEDIUM": "#ff9800", "HIGH": "#f44336", "CRITICAL": "#d50000"}
            color = colors.get(level, "#999")
            return format_html(
                '<a href="/admin-api/user-risk/{}/" target="_blank" style="background:{};color:#fff;padding:3px 8px;border-radius:12px;font-size:10px;text-decoration:none;cursor:pointer;">{} ({})</a>',
                obj.pk, color, level, count
            )
        except Exception:
            return format_html('<span style="color:#999;font-size:10px;">—</span>')
    risk_badge.short_description = "Risk"

    def action_buttons(self, obj):
        deposit_url = reverse("admin:user_deposit", args=[obj.pk])
        withdraw_url = reverse("admin:user_withdraw", args=[obj.pk])
        reset_url = reverse("admin:user_reset_password", args=[obj.pk])
        statement_url = reverse("admin:wallet_wallethistory_changelist") + f"?wallet__exact={obj.pk}"
        try:
            bet_url = reverse("admin:cockfightManager_cockfightmatchbet_changelist") + f"?customer__id__exact={obj.pk}"
        except Exception:
            bet_url = "#"

        # BL/WL logic: only show the relevant action
        if obj.is_active:
            toggle_url = reverse("admin:user_block", args=[obj.pk])
            toggle_btn = f'<a href="{toggle_url}" onclick="return confirm(\'Block this user?\')" title="Blacklist" style="background:#f44336;color:#fff;padding:4px 8px;border-radius:4px;text-decoration:none;font-size:11px;font-weight:bold;margin:1px;">BL</a>'
        else:
            toggle_url = reverse("admin:user_activate", args=[obj.pk])
            toggle_btn = f'<a href="{toggle_url}" onclick="return confirm(\'Activate this user?\')" title="Whitelist" style="background:#4caf50;color:#fff;padding:4px 8px;border-radius:4px;text-decoration:none;font-size:11px;font-weight:bold;margin:1px;">WL</a>'

        html = f'''
        <a href="{deposit_url}" title="Deposit" style="background:#1976d2;color:#fff;padding:4px 8px;border-radius:4px;text-decoration:none;font-size:11px;font-weight:bold;margin:1px;">D</a>
        <a href="{withdraw_url}" title="Withdraw" style="background:#e65100;color:#fff;padding:4px 8px;border-radius:4px;text-decoration:none;font-size:11px;font-weight:bold;margin:1px;">W</a>
        <a href="{statement_url}" title="Statement" style="background:#6a1b9a;color:#fff;padding:4px 8px;border-radius:4px;text-decoration:none;font-size:11px;font-weight:bold;margin:1px;">S</a>
        <a href="{bet_url}" title="Bet History" style="background:#ff6f00;color:#fff;padding:4px 8px;border-radius:4px;text-decoration:none;font-size:11px;font-weight:bold;margin:1px;">BH</a>
        {toggle_btn}
        <a href="{reset_url}" onclick="return confirm(\'Reset password for this user?\')" title="Reset Password" style="background:#607d8b;color:#fff;padding:4px 8px;border-radius:4px;text-decoration:none;font-size:11px;font-weight:bold;margin:1px;">PR</a>
        '''
        return format_html(html)
    action_buttons.short_description = "Actions"

    class Media:
        css = {
            'all': ('admin/css/admin_responsive.css',)
        }

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('deposit/<str:user_id>/', self.admin_site.admin_view(self.deposit_view), name='user_deposit'),
            path('withdraw/<str:user_id>/', self.admin_site.admin_view(self.withdraw_view), name='user_withdraw'),
            path('block/<str:user_id>/', self.admin_site.admin_view(self.block_view), name='user_block'),
            path('activate/<str:user_id>/', self.admin_site.admin_view(self.activate_view), name='user_activate'),
            path('reset-password/<str:user_id>/', self.admin_site.admin_view(self.reset_password_view), name='user_reset_password'),
            path('export-users/', self.admin_site.admin_view(self.export_users_csv), name='export_users_csv'),
        ]
        return custom_urls + urls

    def deposit_view(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)
        if request.method == 'POST':
            amount = request.POST.get('amount', '0')
            reason = request.POST.get('reason', '').strip()
            if not reason:
                messages.error(request, "Reason is required for manual wallet operations.")
                return HttpResponseRedirect(request.get_full_path())
            try:
                amount = Decimal(amount)
                if amount <= 0:
                    raise ValueError("Amount must be positive")
                from wallet.models import Wallet, WalletHistory
                wallet = Wallet.objects.get(user=user)
                wallet.balance += amount
                wallet.fundsIn += amount
                wallet.save()
                WalletHistory.objects.create(
                    wallet=wallet,
                    transaction_type='D',
                    change=amount,
                    isSuccess=True,
                    description=f'Manual deposit by admin ({request.user}): ₹{amount} — {reason}'
                )
                log_admin_action(
                    request.user, 'manual_deposit', 'user', user_id,
                    {'amount': str(amount), 'reason': reason}, request
                )
                messages.success(request, f"₹{amount} deposited to {user.phoneNumber or user.email}")
            except Wallet.DoesNotExist:
                messages.error(request, "User has no wallet")
            except (ValueError, Exception) as e:
                messages.error(request, f"Error: {e}")
            return HttpResponseRedirect(reverse("admin:userManager_user_changelist"))

        # Show form
        try:
            from wallet.models import Wallet
            wallet = Wallet.objects.get(user=user)
            balance = wallet.balance
        except Exception:
            balance = 0

        html = f'''<!DOCTYPE html><html><head><title>Deposit - {user.phoneNumber or user.email}</title>
        <style>body{{font-family:'Inter',Arial,sans-serif;max-width:500px;margin:50px auto;padding:20px;background:#0d1117;color:#e6edf3;}}
        .card{{background:#1c2128;border-radius:12px;padding:30px;box-shadow:0 4px 16px rgba(0,0,0,0.4);border:1px solid #30363d;}}
        h2{{color:#2ea043;margin:0 0 5px;}}
        .info{{color:#8b949e;margin-bottom:20px;}}
        .balance{{font-size:24px;font-weight:bold;color:#58a6ff;margin:15px 0;}}
        input[type=number],input[type=text]{{width:100%;padding:12px;font-size:18px;border:2px solid #30363d;border-radius:8px;box-sizing:border-box;background:#161b22;color:#e6edf3;margin-bottom:12px;}}
        input:focus{{border-color:#1976d2;outline:none;}}
        label{{display:block;margin-bottom:4px;color:#8b949e;font-size:14px;}}
        .btn{{background:#1976d2;color:#fff;padding:12px 30px;border:none;border-radius:8px;font-size:16px;cursor:pointer;width:100%;margin-top:15px;}}
        .btn:hover{{background:#1565c0;}}
        .back{{display:inline-block;margin-top:15px;color:#8b949e;text-decoration:none;}}
        .required{{color:#f44336;}}
        </style></head><body>
        <div class="card">
        <h2>Deposit Funds</h2>
        <p class="info">User: <b>{user.phoneNumber or user.email}</b></p>
        <p class="balance">Current Balance: ₹{balance}</p>
        <form method="post" onsubmit="return confirm('Confirm deposit of ₹' + this.amount.value + '?')">
        <input type="hidden" name="csrfmiddlewaretoken" value="{request.META.get("CSRF_COOKIE", "")}">
        <label>Amount to Deposit (₹)</label>
        <input type="number" name="amount" min="1" step="1" required autofocus placeholder="Enter amount...">
        <label>Reason <span class="required">*</span></label>
        <input type="text" name="reason" required placeholder="Why is this deposit being made?" maxlength="200">
        <button type="submit" class="btn">Confirm Deposit</button>
        </form>
        <a href="{reverse("admin:userManager_user_changelist")}" class="back">← Back to Users</a>
        </div></body></html>'''
        from django.middleware.csrf import get_token
        get_token(request)
        return HttpResponse(html)

    def withdraw_view(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)
        if request.method == 'POST':
            amount = request.POST.get('amount', '0')
            reason = request.POST.get('reason', '').strip()
            if not reason:
                messages.error(request, "Reason is required for manual wallet operations.")
                return HttpResponseRedirect(request.get_full_path())
            try:
                amount = Decimal(amount)
                if amount <= 0:
                    raise ValueError("Amount must be positive")
                from wallet.models import Wallet, WalletHistory
                wallet = Wallet.objects.get(user=user)
                if wallet.balance < amount:
                    raise ValueError(f"Insufficient balance (₹{wallet.balance})")
                wallet.balance -= amount
                wallet.fundsOut += amount
                wallet.save()
                WalletHistory.objects.create(
                    wallet=wallet,
                    transaction_type='W',
                    change=-amount,
                    isSuccess=True,
                    description=f'Manual withdrawal by admin ({request.user}): ₹{amount} — {reason}'
                )
                log_admin_action(
                    request.user, 'manual_withdrawal', 'user', user_id,
                    {'amount': str(amount), 'reason': reason}, request
                )
                messages.success(request, f"₹{amount} withdrawn from {user.phoneNumber or user.email}")
            except Wallet.DoesNotExist:
                messages.error(request, "User has no wallet")
            except (ValueError, Exception) as e:
                messages.error(request, f"Error: {e}")
            return HttpResponseRedirect(reverse("admin:userManager_user_changelist"))
        
        try:
            from wallet.models import Wallet
            wallet = Wallet.objects.get(user=user)
            balance = wallet.balance
        except Exception:
            balance = 0
        
        html = f'''<!DOCTYPE html><html><head><title>Withdraw - {user.phoneNumber or user.email}</title>
        <style>body{{font-family:'Inter',Arial,sans-serif;max-width:500px;margin:50px auto;padding:20px;background:#0d1117;color:#e6edf3;}}
        .card{{background:#1c2128;border-radius:12px;padding:30px;box-shadow:0 4px 16px rgba(0,0,0,0.4);border:1px solid #30363d;}}
        h2{{color:#f0883e;margin:0 0 5px;}}
        .info{{color:#8b949e;margin-bottom:20px;}}
        .balance{{font-size:24px;font-weight:bold;color:#58a6ff;margin:15px 0;}}
        input[type=number],input[type=text]{{width:100%;padding:12px;font-size:18px;border:2px solid #30363d;border-radius:8px;box-sizing:border-box;background:#161b22;color:#e6edf3;margin-bottom:12px;}}
        input:focus{{border-color:#e65100;outline:none;}}
        label{{display:block;margin-bottom:4px;color:#8b949e;font-size:14px;}}
        .btn{{background:#e65100;color:#fff;padding:12px 30px;border:none;border-radius:8px;font-size:16px;cursor:pointer;width:100%;margin-top:15px;}}
        .btn:hover{{background:#bf360c;}}
        .back{{display:inline-block;margin-top:15px;color:#8b949e;text-decoration:none;}}
        .required{{color:#f44336;}}
        </style></head><body>
        <div class="card">
        <h2>Withdraw Funds</h2>
        <p class="info">User: <b>{user.phoneNumber or user.email}</b></p>
        <p class="balance">Current Balance: ₹{balance}</p>
        <form method="post" onsubmit="return confirm('Confirm withdrawal of ₹' + this.amount.value + '?')">
        <input type="hidden" name="csrfmiddlewaretoken" value="{request.META.get("CSRF_COOKIE", "")}">
        <label>Amount to Withdraw (₹)</label>
        <input type="number" name="amount" min="1" max="{balance}" step="1" required autofocus placeholder="Enter amount...">
        <label>Reason <span class="required">*</span></label>
        <input type="text" name="reason" required placeholder="Why is this withdrawal being made?" maxlength="200">
        <button type="submit" class="btn">Confirm Withdrawal</button>
        </form>
        <a href="{reverse("admin:userManager_user_changelist")}" class="back">← Back to Users</a>
        </div></body></html>'''
        from django.middleware.csrf import get_token
        get_token(request)
        return HttpResponse(html)

    def block_view(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)
        user.is_active = False
        user.save()
        log_admin_action(
            request.user, 'block_user', 'user', user_id,
            {'target_phone': user.phoneNumber}, request
        )
        messages.success(request, f"User {user.phoneNumber or user.email} has been BLOCKED.")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse("admin:userManager_user_changelist")))

    def activate_view(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)
        user.is_active = True
        user.save()
        log_admin_action(
            request.user, 'activate_user', 'user', user_id,
            {'target_phone': user.phoneNumber}, request
        )
        messages.success(request, f"User {user.phoneNumber or user.email} has been ACTIVATED.")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse("admin:userManager_user_changelist")))

    def reset_password_view(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)
        import string, random
        new_pass = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
        user.set_password(new_pass)
        user.save()
        log_admin_action(
            request.user, 'reset_password', 'user', user_id,
            {'target_phone': user.phoneNumber}, request
        )
        # Show password briefly - admin must note it down
        messages.success(request, f"Password reset for {user.phoneNumber or user.username}. New password: {new_pass} (note it now, it won't be shown again)")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse("admin:userManager_user_changelist")))

    def export_users_csv(self, request):
        if not request.user.is_superuser:
            messages.error(request, "Only super admins can export user data.")
            return HttpResponseRedirect(reverse("admin:userManager_user_changelist"))
        log_admin_action(
            request.user, 'export_users_csv', 'system', 'all_users',
            {'ip': get_client_ip(request)}, request
        )
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="users_{timezone.now().strftime("%Y%m%d_%H%M")}.csv"'
        writer = csv.writer(response)
        writer.writerow(['Phone', 'Username', 'Email', 'Balance', 'Status', 'Joined'])
        for user in User.objects.filter(is_staff=False).select_related('wallet'):
            try:
                balance = user.wallet.balance
            except Exception:
                balance = 0
            writer.writerow([user.phoneNumber or '-', user.username or '-', user.email, balance, 'Active' if user.is_active else 'Blocked', user.joinedDate])
        return response

    def save_model(self, request, obj, form, change):
        if not change:
            obj.is_staff = True
        super().save_model(request, obj, form, change)


@admin.register(SettlementBox)
class SettlementBoxAdmin(admin.ModelAdmin):
    icon_name = 'compare_arrows'
    list_display = ('user', 'verified_value',
                    'collected_value_link', 'updated_at')
    actions = ['verify_accounts']
    list_filter = ['isProcessed']
    list_display_links = None
    search_fields = ['id']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        user = request.user

        isProcessed = request.GET.get('isProcessed__exact')
        if (isProcessed and user.is_superuser) or (hasattr(user, 'managed_room') and user.managed_room and isProcessed):
            return qs.filter(isProcessed=isProcessed, user=user)

        processed_id = request.GET.get('processedId__id__exact')
        if processed_id:
            return qs.filter(processedId__id=processed_id)

        if user.is_superuser:
            manager_ids = Room.objects.filter(
                manager__isnull=False).values_list('manager_id', flat=True)
            return qs.filter(
                Q(user__id__in=manager_ids) | Q(user=user),
                isProcessed=False
            )

        if hasattr(user, 'managed_room') and user.managed_room:
            staff_ids = user.managed_room.users.exclude(
                id=user.id).values_list('id', flat=True)
            return qs.filter(user__id__in=staff_ids, isProcessed=False)

        return qs.none()

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def verified_value(self, obj):
        if obj.verifiedValue != 0:
            url = reverse("admin:userManager_settlementhistory_changelist") + \
                f"?settlementBox__id__exact={obj.id}"
            return format_html('<a href="{}">{}</a>', url, obj.verifiedValue)
        return f"{obj.verifiedValue}"
    verified_value.short_description = "Verified Value"

    def collected_value_link(self, obj):
        if obj.collectedValue > 0:
            url = reverse("admin:userManager_settlementbox_changelist") + \
                f"?processedId__id__exact={obj.id}"
            return format_html('<a href="{}">{}</a>', url, obj.collectedValue)
        return f"{obj.collectedValue}"
    collected_value_link.short_description = "Collected Value"

    @admin.action(description="Verify accounts")
    def verify_accounts(self, request, queryset):
        from django.db import transaction
        user = request.user
        if not (user.is_superuser or hasattr(user, 'managed_room')):
            self.message_user(request, "Only Superusers or Managers can perform this action.", level=messages.ERROR)
            return

        total_verified = 0
        try:
            with transaction.atomic():
                current_box, _ = SettlementBox.objects.get_or_create(
                    user=user, isProcessed=False,
                    defaults={'verifiedValue': 0, 'collectedValue': 0}
                )

                isSuperUserRecordExist = False

                for box in queryset.select_for_update():
                    total_verified += (box.verifiedValue + box.collectedValue)
                    box.isProcessed = True
                    box.processedId = current_box
                    box.save()

                    if box.user == user:
                        isSuperUserRecordExist = True

                    SettlementBox.objects.create(user=box.user)

                current_box.collectedValue = F('collectedValue') + total_verified

                if isSuperUserRecordExist:
                    current_box.isProcessed = True
                    current_box.processedId = current_box

                current_box.save()

                self.message_user(
                    request,
                    f"Verified {queryset.count()} settlements. Total collected: {total_verified}",
                    level=messages.SUCCESS
                )
        except Exception as e:
            self.message_user(request, f"Error: {str(e)}", level=messages.ERROR)


@admin.register(SettlementHistory)
class SettlementHistoryAdmin(admin.ModelAdmin):
    icon_name = 'chrome_reader_mode'
    list_filter = ['transaction_type']
    search_fields = ['id', 'utr_id']
    list_per_page = 20
    list_max_show_all = 40
    list_display_links = None

    def get_list_display(self, request):
        historyId = (request.GET.get('id__exact'))
        if historyId and historyId != 'None':
            return ['verifiedBy', 'customer', 'transaction_type', 'utr_id', 'amount', 'timestamp']
        return ['customer', 'transaction_type', 'utr_id', 'amount', 'timestamp']

    def verifiedBy(self, object):
        return object.settlementBox.user
    verifiedBy.short_description = "Verified By"

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        walletById = request.GET.get('settlementBox__id__exact')
        if walletById:
            return qs

        boxId = (request.GET.get('id__exact'))
        if boxId and boxId != 'None':
            return qs.filter(pk=boxId)

        return qs.none()

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=...):
        return False

    def has_delete_permission(self, request, obj=...):
        return False

    def get_model_perms(self, request):
        return {}
