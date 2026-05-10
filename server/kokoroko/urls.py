import logging

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse, HttpResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta
from kokoroko.security import log_admin_action

security_logger = logging.getLogger("kokoroko.security")

admin.site.site_header = "Kokoroko"
admin.site.site_title = "Administration • Kokoroko"
admin.site.enable_nav_sidebar = True
admin.site.index_title = "Welcome"
admin.site.site_url = "http://155.117.46.249:8080"
admin.site.name = "kokoroko"



@staff_member_required
def deposit_action_view(request, pk, action):
    from django.shortcuts import redirect
    from django.contrib import messages as msg
    from wallet.models import DepositRequest, Wallet, WalletHistory
    from django.db.models import F
    from django.db import transaction as db_transaction

    try:
        if action == 'accept':
            with db_transaction.atomic():
                deposit = DepositRequest.objects.select_for_update().get(pk=pk)
                if deposit.status != 'P':
                    msg.warning(request, f"Deposit #{pk} already processed.")
                    return redirect('/wallet/depositrequest/')
                customer = deposit.customer
                if not customer:
                    msg.warning(request, f"Deposit #{pk} has no customer.")
                    return redirect('/wallet/depositrequest/')
                amount = deposit.confirm_amount if deposit.confirm_amount else deposit.deposit_amount
                if not deposit.confirm_amount:
                    deposit.confirm_amount = deposit.deposit_amount
                wallet, _ = Wallet.objects.get_or_create(user=customer)
                wallet.balance = F('balance') + amount
                wallet.fundsIn = F('fundsIn') + amount
                wallet.save()
                WalletHistory.objects.create(
                    wallet=wallet, transaction_type='D', change=amount,
                    isSuccess=True, description=f"Deposit via {deposit.get_deposit_type_display()} UTR {deposit.utr_id}"
                )
                deposit.status = 'A'
                deposit.save()
            log_admin_action(
                request.user, 'accept_deposit', 'deposit', pk,
                {'amount': str(amount), 'customer': customer.username, 'utr': deposit.utr_id}, request
            )
            msg.success(request, f"Deposit #{pk} accepted. {amount} credited to {customer.username}.")

        elif action == 'reject':
            with db_transaction.atomic():
                deposit = DepositRequest.objects.select_for_update().get(pk=pk)
                if deposit.status != 'P':
                    msg.warning(request, f"Deposit #{pk} already processed.")
                    return redirect('/wallet/depositrequest/')
                customer = deposit.customer
                if not customer:
                    msg.warning(request, f"Deposit #{pk} has no customer.")
                    return redirect('/wallet/depositrequest/')
                wallet, _ = Wallet.objects.get_or_create(user=customer)
                WalletHistory.objects.create(
                    wallet=wallet, transaction_type='D', change=deposit.deposit_amount,
                    isSuccess=False, description=f"Rejected: {deposit.infoNote or 'No remarks'}"
                )
                deposit.status = 'R'
                deposit.save()
            log_admin_action(
                request.user, 'reject_deposit', 'deposit', pk,
                {'customer': customer.username, 'amount': str(deposit.deposit_amount)}, request
            )
            msg.warning(request, f"Deposit #{pk} rejected.")
    except DepositRequest.DoesNotExist:
        msg.error(request, f"Deposit #{pk} not found.")
    except Exception as e:
        msg.error(request, f"Error: {str(e)}")
    return redirect('/wallet/depositrequest/')


@staff_member_required
def withdrawal_action_view(request, pk, action):
    from django.shortcuts import redirect
    from django.contrib import messages as msg
    from wallet.models import WithdrawalRequest, Wallet, WalletHistory
    from django.db.models import F
    from django.db import transaction as db_transaction

    try:
        if action == 'approve':
            with db_transaction.atomic():
                wd = WithdrawalRequest.objects.select_for_update().get(pk=pk)
                if wd.status not in ('P', 'H'):
                    msg.warning(request, f"Withdrawal #{pk} already processed.")
                    return redirect('/wallet/withdrawalrequest/')
                wd.status = 'A'
                wd.save()
            log_admin_action(
                request.user, 'approve_withdrawal', 'withdrawal', pk,
                {'amount': str(wd.withdrawal_amount), 'customer': wd.customer.username}, request
            )
            msg.success(request, f"Withdrawal #{pk} approved.")

        elif action == 'reject':
            with db_transaction.atomic():
                wd = WithdrawalRequest.objects.select_for_update().get(pk=pk)
                if wd.status not in ('P', 'H'):
                    msg.warning(request, f"Withdrawal #{pk} already processed.")
                    return redirect('/wallet/withdrawalrequest/')
                customer = wd.customer
                amount = wd.withdrawal_amount
                wallet, _ = Wallet.objects.get_or_create(user=customer)
                wallet.balance = F('balance') + amount
                wallet.save()
                WalletHistory.objects.create(
                    wallet=wallet, transaction_type='W', change=amount,
                    isSuccess=False, description=f"Rejected withdrawal: {wd.infoNote or 'No remarks'}"
                )
                wd.status = 'R'
                wd.save()
            log_admin_action(
                request.user, 'reject_withdrawal', 'withdrawal', pk,
                {'amount': str(amount), 'customer': customer.username}, request
            )
            msg.warning(request, f"Withdrawal #{pk} rejected. Amount returned to {customer.username}.")

        elif action == 'handle':
            with db_transaction.atomic():
                wd = WithdrawalRequest.objects.select_for_update().get(pk=pk)
                if wd.status != 'P':
                    msg.warning(request, f"Withdrawal #{pk} already processed.")
                    return redirect('/wallet/withdrawalrequest/')
                wd.status = 'H'
                wd.handling_by = request.user
                wd.save()
            msg.info(request, f"Withdrawal #{pk} now handled by you.")
    except WithdrawalRequest.DoesNotExist:
        msg.error(request, f"Withdrawal #{pk} not found.")
    except Exception as e:
        msg.error(request, f"Error: {str(e)}")
    return redirect('/wallet/withdrawalrequest/')


@staff_member_required
def admin_sidebar_counts(request):
    """Lightweight endpoint for sidebar badge counts"""
    counts = {}
    try:
        from wallet.models import DepositRequest, WithdrawalRequest
        counts["pending_deposits"] = DepositRequest.objects.filter(status='P').count()
        counts["pending_withdrawals"] = WithdrawalRequest.objects.filter(status='P').count()
    except:
        counts["pending_deposits"] = 0
        counts["pending_withdrawals"] = 0
    try:
        from cockfightManager.models import CockfightMatch
        counts["live_matches"] = CockfightMatch.objects.filter(isLive=True).count()
    except:
        counts["live_matches"] = 0
    try:
        from cockfightManager.models import CockfightMatchBet
        counts["pending_bets"] = CockfightMatchBet.objects.filter(matchWinStatus=0).count()
    except:
        counts["pending_bets"] = 0
    return JsonResponse(counts)


@staff_member_required
def admin_dashboard_stats(request):
    """API endpoint for admin dashboard stats"""
    from userManager.models import User
    from wallet.models import Wallet, WalletHistory

    # Date filter
    days = int(request.GET.get('days', 0))
    date_filter = {}
    if days > 0:
        start_date = timezone.now() - timedelta(days=days)
        date_filter = {'created_at__gte': start_date}

    # User stats
    total_users = User.objects.filter(is_staff=False).count()
    active_users = User.objects.filter(is_staff=False, is_active=True).count()
    blocked_users = User.objects.filter(is_staff=False, is_active=False).count()

    # Wallet stats - use 'change' field and 'transaction_type' field
    total_balance = Wallet.objects.aggregate(total=Sum('balance'))['total'] or 0
    total_deposits = WalletHistory.objects.filter(
        transaction_type='D', **date_filter
    ).aggregate(total=Sum('change'))['total'] or 0
    total_withdrawals = WalletHistory.objects.filter(
        transaction_type='W', **date_filter
    ).aggregate(total=Sum('change'))['total'] or 0

    # Pending requests (no status field - just count all)
    try:
        from wallet.models import DepositRequest
        pending_deposits = DepositRequest.objects.filter(status=P ).count()
    except:
        pending_deposits = 0
    try:
        from wallet.models import WithdrawalRequest
        pending_withdrawals = WithdrawalRequest.objects.filter(status=P ).count()
    except:
        pending_withdrawals = 0

    # Match stats
    try:
        from cockfightManager.models import CockfightMatch, CockfightMatchBet
        live_cockfight = CockfightMatch.objects.filter(isLive=True).count()
        total_cockfight_bets = CockfightMatchBet.objects.count()
    except:
        live_cockfight = 0
        total_cockfight_bets = 0

    try:
        from dicePlayManager.models import DicePlayMatch
        live_dice = DicePlayMatch.objects.filter(isLive=True).count()
    except:
        live_dice = 0

    # Recent transactions
    try:
        recent_transactions = list(
            WalletHistory.objects.select_related('wallet__user').order_by('-created_at')[:10].values(
                'transactionHash', 'transaction_type', 'change', 'created_at',
                'wallet__user__username', 'wallet__user__phoneNumber'
            )
        )
    except:
        recent_transactions = []

    return JsonResponse({
        'users': {
            'total': total_users,
            'active': active_users,
            'blocked': blocked_users,
        },
        'wallet': {
            'total_balance': float(total_balance),
            'total_deposits': float(total_deposits),
            'total_withdrawals': float(abs(total_withdrawals)) if total_withdrawals else 0,
            'pending_deposits': pending_deposits,
            'pending_withdrawals': pending_withdrawals,
        },
        'matches': {
            'live_cockfight': live_cockfight,
            'total_cockfight_bets': total_cockfight_bets,
            'live_dice': live_dice,
        },
        'recent_transactions': [
            {
                'hash': t['transactionHash'] or '-',
                'type': t['transaction_type'],
                'amount': float(abs(t['change'])) if t['change'] else 0,
                'date': t['created_at'].strftime('%Y-%m-%d %H:%M') if t['created_at'] else '-',
                'user': t['wallet__user__username'] or t['wallet__user__phoneNumber'] or '-',
            } for t in recent_transactions
        ]
    })


# ─── Theme System ─────────────────────────────────────────────────────────────

import json
from django.views.decorators.csrf import csrf_exempt

PRESET_THEMES = {
    "gold-black": {
        "name": "Gold & Black (Original)",
        "preview": ["#0B0B0B", "#D4A843", "#171717"],
        "colors": {
            "gold": "#D4A843", "gold_dark": "#B8922E", "gold_light": "#f0d78c",
            "bg": "#0B0B0B", "bg_card": "#171717", "bg_elevated": "#1F1A12",
            "bg_surface": "#121212", "bg_white": "#171717",
            "text_primary": "#F5F1E8", "text_secondary": "#A8A29E", "text_muted": "#6B6560",
            "border": "rgba(212,168,67,0.18)", "border_light": "rgba(212,168,67,0.10)",
            "success": "#22C55E", "danger": "#EF4444", "warning": "#F59E0B",
            "meron": "#DC2626", "wala": "#2563EB", "draw": "#A855F7",
        }
    },
    "blue-dark": {
        "name": "Royal Blue",
        "preview": ["#0A0E1A", "#3B82F6", "#111827"],
        "colors": {
            "gold": "#3B82F6", "gold_dark": "#2563EB", "gold_light": "#93C5FD",
            "bg": "#0A0E1A", "bg_card": "#111827", "bg_elevated": "#1E293B",
            "bg_surface": "#0F172A", "bg_white": "#111827",
            "text_primary": "#F1F5F9", "text_secondary": "#94A3B8", "text_muted": "#64748B",
            "border": "rgba(59,130,246,0.20)", "border_light": "rgba(59,130,246,0.10)",
            "success": "#22C55E", "danger": "#EF4444", "warning": "#F59E0B",
            "meron": "#DC2626", "wala": "#2563EB", "draw": "#A855F7",
        }
    },
    "emerald-dark": {
        "name": "Emerald Night",
        "preview": ["#0A1A0F", "#10B981", "#11251A"],
        "colors": {
            "gold": "#10B981", "gold_dark": "#059669", "gold_light": "#6EE7B7",
            "bg": "#0A1A0F", "bg_card": "#11251A", "bg_elevated": "#1A3A28",
            "bg_surface": "#0D1F14", "bg_white": "#11251A",
            "text_primary": "#ECFDF5", "text_secondary": "#A7F3D0", "text_muted": "#6EE7B7",
            "border": "rgba(16,185,129,0.20)", "border_light": "rgba(16,185,129,0.10)",
            "success": "#22C55E", "danger": "#EF4444", "warning": "#F59E0B",
            "meron": "#DC2626", "wala": "#2563EB", "draw": "#A855F7",
        }
    },
    "purple-dark": {
        "name": "Neon Purple",
        "preview": ["#0F0A1A", "#A855F7", "#1A1127"],
        "colors": {
            "gold": "#A855F7", "gold_dark": "#9333EA", "gold_light": "#D8B4FE",
            "bg": "#0F0A1A", "bg_card": "#1A1127", "bg_elevated": "#2D1F4E",
            "bg_surface": "#130E20", "bg_white": "#1A1127",
            "text_primary": "#F5F3FF", "text_secondary": "#C4B5FD", "text_muted": "#8B5CF6",
            "border": "rgba(168,85,247,0.20)", "border_light": "rgba(168,85,247,0.10)",
            "success": "#22C55E", "danger": "#EF4444", "warning": "#F59E0B",
            "meron": "#DC2626", "wala": "#2563EB", "draw": "#A855F7",
        }
    },
    "red-dark": {
        "name": "Crimson Fire",
        "preview": ["#1A0A0A", "#EF4444", "#271111"],
        "colors": {
            "gold": "#EF4444", "gold_dark": "#DC2626", "gold_light": "#FCA5A5",
            "bg": "#1A0A0A", "bg_card": "#271111", "bg_elevated": "#3B1515",
            "bg_surface": "#1F0E0E", "bg_white": "#271111",
            "text_primary": "#FEF2F2", "text_secondary": "#FCA5A5", "text_muted": "#F87171",
            "border": "rgba(239,68,68,0.20)", "border_light": "rgba(239,68,68,0.10)",
            "success": "#22C55E", "danger": "#F97316", "warning": "#F59E0B",
            "meron": "#DC2626", "wala": "#2563EB", "draw": "#A855F7",
        }
    },
    "orange-dark": {
        "name": "Sunset Orange",
        "preview": ["#1A120A", "#F97316", "#271A11"],
        "colors": {
            "gold": "#F97316", "gold_dark": "#EA580C", "gold_light": "#FDBA74",
            "bg": "#1A120A", "bg_card": "#271A11", "bg_elevated": "#3B2515",
            "bg_surface": "#1F150E", "bg_white": "#271A11",
            "text_primary": "#FFF7ED", "text_secondary": "#FED7AA", "text_muted": "#FB923C",
            "border": "rgba(249,115,22,0.20)", "border_light": "rgba(249,115,22,0.10)",
            "success": "#22C55E", "danger": "#EF4444", "warning": "#FBBF24",
            "meron": "#DC2626", "wala": "#2563EB", "draw": "#A855F7",
        }
    },
    "cyan-dark": {
        "name": "Ocean Cyan",
        "preview": ["#0A1A1A", "#06B6D4", "#112727"],
        "colors": {
            "gold": "#06B6D4", "gold_dark": "#0891B2", "gold_light": "#67E8F9",
            "bg": "#0A1A1A", "bg_card": "#112727", "bg_elevated": "#1A3A3A",
            "bg_surface": "#0D1F1F", "bg_white": "#112727",
            "text_primary": "#ECFEFF", "text_secondary": "#A5F3FC", "text_muted": "#22D3EE",
            "border": "rgba(6,182,212,0.20)", "border_light": "rgba(6,182,212,0.10)",
            "success": "#22C55E", "danger": "#EF4444", "warning": "#F59E0B",
            "meron": "#DC2626", "wala": "#2563EB", "draw": "#A855F7",
        }
    },
    "white-gold": {
        "name": "Light Gold (White)",
        "preview": ["#FAFAFA", "#B8922E", "#FFFFFF"],
        "colors": {
            "gold": "#B8922E", "gold_dark": "#9A7A24", "gold_light": "#D4A843",
            "bg": "#F5F5F5", "bg_card": "#FFFFFF", "bg_elevated": "#FFF9EB",
            "bg_surface": "#FAFAFA", "bg_white": "#FFFFFF",
            "text_primary": "#1A1A1A", "text_secondary": "#6B7280", "text_muted": "#9CA3AF",
            "border": "rgba(184,146,46,0.25)", "border_light": "rgba(184,146,46,0.12)",
            "success": "#16A34A", "danger": "#DC2626", "warning": "#D97706",
            "meron": "#DC2626", "wala": "#2563EB", "draw": "#7C3AED",
        }
    },
}

def _get_active_theme():
    """Get the active theme from cache or DB."""
    from django.core.cache import cache
    theme = cache.get("active_theme")
    if theme:
        return theme
    # Default
    theme = {"preset": "gold-black", "custom": None}
    try:
        from base.models import Setting
        s = Setting.objects.filter(action='Z').first()
        if s:
            theme = json.loads(s.actionValue)
    except Exception:
        pass
    cache.set("active_theme", theme, timeout=86400)
    return theme


def get_theme_api(request):
    """Public API: returns the active theme colors for web/app."""
    theme_data = _get_active_theme()
    preset_key = theme_data.get("preset", "gold-black")
    custom = theme_data.get("custom")

    if custom:
        colors = custom
        name = "Custom Theme"
    else:
        preset = PRESET_THEMES.get(preset_key, PRESET_THEMES["gold-black"])
        colors = preset["colors"]
        name = preset["name"]

    return JsonResponse({
        "preset": preset_key,
        "name": name,
        "is_custom": bool(custom),
        "colors": colors,
    })


@csrf_exempt
@staff_member_required
def set_theme_api(request):
    """Admin API: set the active theme."""
    if request.method != 'POST':
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    preset = body.get("preset", "gold-black")
    custom = body.get("custom")  # dict of colors or None

    if not custom and preset not in PRESET_THEMES:
        return JsonResponse({"error": f"Unknown preset: {preset}"}, status=400)

    theme_data = {"preset": preset, "custom": custom}

    from base.models import Setting as SettingModel
    obj, created = SettingModel.objects.update_or_create(
        action='Z',
        defaults={"actionValue": json.dumps(theme_data)}
    )

    from django.core.cache import cache
    cache.set("active_theme", theme_data, timeout=86400)

    log_admin_action(
        request.user, 'change_theme', 'system', preset,
        {'custom': bool(custom)}, request
    )

    return JsonResponse({"success": True, "theme": theme_data})


def get_theme_presets_api(request):
    """Public API: list all available preset themes."""
    presets = []
    for key, theme in PRESET_THEMES.items():
        presets.append({
            "key": key,
            "name": theme["name"],
            "preview": theme["preview"],
            "colors": theme["colors"],
        })
    return JsonResponse({"presets": presets})


@staff_member_required
def admin_theme_page(request):
    """Admin page for theme management."""
    theme_data = _get_active_theme()
    active_preset = theme_data.get("preset", "gold-black")
    custom_colors = theme_data.get("custom")
    is_custom = bool(custom_colors)

    presets_json = json.dumps([
        {"key": k, "name": v["name"], "preview": v["preview"], "colors": v["colors"]}
        for k, v in PRESET_THEMES.items()
    ])

    active_colors = custom_colors if is_custom else PRESET_THEMES.get(active_preset, PRESET_THEMES["gold-black"])["colors"]

    return HttpResponse(_theme_page_html(presets_json, active_preset, is_custom, json.dumps(active_colors)))


def _theme_page_html(presets_json, active_preset, is_custom, active_colors_json):
    from django.middleware.csrf import get_token
    return f'''<!DOCTYPE html>
<html><head>
<title>Theme Settings — Kokoroko Admin</title>
<link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: 'Inter', -apple-system, sans-serif; background: #0B0B0B; color: #F5F1E8; min-height: 100vh; }}
.theme-container {{ max-width: 1100px; margin: 0 auto; padding: 30px 24px; }}
.page-header {{ display: flex; align-items: center; gap: 12px; margin-bottom: 30px; }}
.page-header .material-icons {{ font-size: 28px; color: #D4A843; }}
.page-header h1 {{ font-size: 24px; font-weight: 700; }}
.page-header .back {{ color: #A8A29E; text-decoration: none; margin-left: auto; font-size: 14px; display: flex; align-items: center; gap: 4px; }}
.page-header .back:hover {{ color: #D4A843; }}

.section {{ margin-bottom: 32px; }}
.section-title {{ font-size: 16px; font-weight: 600; margin-bottom: 16px; color: #D4A843; display: flex; align-items: center; gap: 8px; }}

.presets-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 16px; }}
.preset-card {{
    background: #171717; border: 2px solid rgba(255,255,255,0.08); border-radius: 14px;
    padding: 16px; cursor: pointer; transition: all 0.2s;
}}
.preset-card:hover {{ border-color: rgba(255,255,255,0.2); transform: translateY(-2px); }}
.preset-card.active {{ border-color: #D4A843; box-shadow: 0 0 20px rgba(212,168,67,0.15); }}
.preset-preview {{ display: flex; gap: 6px; margin-bottom: 12px; height: 48px; border-radius: 8px; overflow: hidden; }}
.preset-preview span {{ flex: 1; }}
.preset-name {{ font-size: 14px; font-weight: 600; }}
.preset-check {{ float: right; color: #D4A843; display: none; }}
.preset-card.active .preset-check {{ display: inline; }}

.custom-section {{ background: #171717; border-radius: 14px; padding: 24px; border: 1px solid rgba(255,255,255,0.08); }}
.color-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 16px; }}
.color-item {{ display: flex; align-items: center; gap: 10px; }}
.color-item label {{ font-size: 13px; color: #A8A29E; min-width: 100px; }}
.color-item input[type=color] {{
    width: 40px; height: 34px; border: 2px solid rgba(255,255,255,0.15);
    border-radius: 8px; cursor: pointer; background: transparent; padding: 2px;
}}
.color-item input[type=text] {{
    background: #0B0B0B; border: 1px solid rgba(255,255,255,0.15); color: #F5F1E8;
    padding: 6px 10px; border-radius: 6px; font-size: 13px; width: 110px; font-family: monospace;
}}

.preview-section {{ background: #171717; border-radius: 14px; padding: 24px; border: 1px solid rgba(255,255,255,0.08); }}
.preview-phone {{
    width: 280px; height: 500px; margin: 0 auto; border-radius: 24px;
    overflow: hidden; border: 3px solid #333; position: relative;
}}
.preview-header {{ height: 50px; display: flex; align-items: center; padding: 0 14px; justify-content: space-between; }}
.preview-header h3 {{ font-size: 15px; font-weight: 700; }}
.preview-body {{ padding: 12px; }}
.preview-card {{ border-radius: 10px; padding: 14px; margin-bottom: 10px; }}
.preview-btn {{ padding: 10px 0; border-radius: 8px; text-align: center; font-weight: 700; font-size: 13px; margin-top: 8px; }}
.preview-nav {{ position: absolute; bottom: 0; left: 0; right: 0; height: 52px; display: flex; align-items: center; justify-content: space-around; border-top: 1px solid; }}
.preview-nav span {{ font-size: 22px; }}

.btn-row {{ display: flex; gap: 12px; margin-top: 20px; }}
.btn {{ padding: 12px 28px; border-radius: 10px; font-size: 14px; font-weight: 700; cursor: pointer; border: none; transition: all 0.2s; }}
.btn-primary {{ background: #D4A843; color: #000; }}
.btn-primary:hover {{ background: #B8922E; }}
.btn-secondary {{ background: transparent; color: #D4A843; border: 1px solid #D4A843; }}
.btn-secondary:hover {{ background: rgba(212,168,67,0.1); }}
.btn:disabled {{ opacity: 0.5; cursor: not-allowed; }}

.toast {{ position: fixed; top: 20px; right: 20px; padding: 14px 24px; border-radius: 10px; font-weight: 600; z-index: 9999; display: none; font-size: 14px; }}
.toast.success {{ background: #22C55E; color: #fff; }}
.toast.error {{ background: #EF4444; color: #fff; }}

.tab-row {{ display: flex; gap: 0; margin-bottom: 24px; }}
.tab-btn {{ padding: 10px 24px; font-size: 14px; font-weight: 600; cursor: pointer; border: none; background: #171717; color: #A8A29E; border-bottom: 2px solid transparent; transition: all 0.2s; }}
.tab-btn.active {{ color: #D4A843; border-bottom-color: #D4A843; background: #1F1A12; }}
.tab-content {{ display: none; }}
.tab-content.active {{ display: block; }}
</style>
</head><body>
<div class="theme-container">
    <div class="page-header">
        <span class="material-icons">palette</span>
        <h1>Theme Settings</h1>
        <a href="/" class="back"><span class="material-icons" style="font-size:18px">arrow_back</span> Back to Admin</a>
    </div>

    <div class="tab-row">
        <button class="tab-btn active" onclick="switchTab('presets')">Preset Themes</button>
        <button class="tab-btn" onclick="switchTab('custom')">Custom Colors</button>
    </div>

    <!-- PRESETS TAB -->
    <div id="tab-presets" class="tab-content active">
        <div class="section">
            <div class="presets-grid" id="presetsGrid"></div>
        </div>
    </div>

    <!-- CUSTOM TAB -->
    <div id="tab-custom" class="tab-content">
        <div class="custom-section">
            <div class="section-title"><span class="material-icons">colorize</span> Pick Your Colors</div>
            <div class="color-grid" id="colorGrid"></div>
        </div>
    </div>

    <!-- LIVE PREVIEW -->
    <div class="section" style="margin-top:24px;">
        <div class="section-title"><span class="material-icons">phone_iphone</span> Live Preview</div>
        <div class="preview-section">
            <div class="preview-phone" id="previewPhone">
                <div class="preview-header" id="pvHeader">
                    <h3 id="pvBrand">KOKOROKO</h3>
                    <span style="font-size:13px;font-weight:700" id="pvWallet">₹5,000</span>
                </div>
                <div class="preview-body" id="pvBody">
                    <div class="preview-card" id="pvCard1">
                        <div style="font-size:12px;opacity:0.7;">Live Match</div>
                        <div style="font-size:16px;font-weight:700;margin:6px 0;">Meron vs Wala</div>
                        <div style="font-size:11px;opacity:0.6;">Game #124 &bull; Betting Open</div>
                    </div>
                    <div class="preview-card" id="pvCard2">
                        <div style="font-size:12px;opacity:0.7;">Dice Game</div>
                        <div style="display:flex;gap:6px;margin:8px 0;" id="pvDice"></div>
                        <div style="font-size:11px;opacity:0.6;">Next round in 45s</div>
                    </div>
                    <div class="preview-btn" id="pvBtn">Place Bet</div>
                </div>
                <div class="preview-nav" id="pvNav">
                    <span class="material-icons">home</span>
                    <span class="material-icons">sports_mma</span>
                    <span class="material-icons">casino</span>
                    <span class="material-icons">account_balance_wallet</span>
                </div>
            </div>
        </div>
    </div>

    <div class="btn-row">
        <button class="btn btn-primary" id="saveBtn" onclick="saveTheme()">
            <span class="material-icons" style="font-size:16px;vertical-align:middle;margin-right:4px;">save</span>
            Apply Theme
        </button>
        <button class="btn btn-secondary" onclick="resetToOriginal()">
            <span class="material-icons" style="font-size:16px;vertical-align:middle;margin-right:4px;">restore</span>
            Reset to Original
        </button>
    </div>
</div>

<div class="toast" id="toast"></div>

<script>
const PRESETS = {presets_json};
const ACTIVE_PRESET = "{active_preset}";
const IS_CUSTOM = {"true" if is_custom else "false"};
const ACTIVE_COLORS = {active_colors_json};

const COLOR_LABELS = {{
    gold: "Accent / Brand", gold_dark: "Accent Dark", gold_light: "Accent Light",
    bg: "Background", bg_card: "Card Background", bg_elevated: "Elevated BG",
    bg_surface: "Surface BG", bg_white: "White / Card",
    text_primary: "Primary Text", text_secondary: "Secondary Text", text_muted: "Muted Text",
    border: "Border Color", border_light: "Light Border",
    success: "Success", danger: "Danger", warning: "Warning",
    meron: "Meron (Red)", wala: "Wala (Blue)", draw: "Draw (Purple)",
}};

let currentMode = IS_CUSTOM ? 'custom' : 'preset';
let selectedPreset = ACTIVE_PRESET;
let customColors = JSON.parse(JSON.stringify(ACTIVE_COLORS));

function switchTab(tab) {{
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    event.target.classList.add('active');
    document.getElementById('tab-' + tab).classList.add('active');
    currentMode = tab === 'custom' ? 'custom' : 'preset';
    updatePreview();
}}

function renderPresets() {{
    const grid = document.getElementById('presetsGrid');
    grid.innerHTML = '';
    PRESETS.forEach(p => {{
        const active = (!IS_CUSTOM && selectedPreset === p.key) ? 'active' : '';
        grid.innerHTML += `
            <div class="preset-card ${{active}}" data-key="${{p.key}}" onclick="selectPreset('${{p.key}}')">
                <div class="preset-preview">
                    ${{p.preview.map(c => `<span style="background:${{c}}"></span>`).join('')}}
                </div>
                <div class="preset-name">
                    ${{p.name}}
                    <span class="preset-check material-icons">check_circle</span>
                </div>
            </div>
        `;
    }});
}}

function selectPreset(key) {{
    selectedPreset = key;
    currentMode = 'preset';
    document.querySelectorAll('.preset-card').forEach(c => c.classList.remove('active'));
    document.querySelector(`[data-key="${{key}}"]`).classList.add('active');
    const preset = PRESETS.find(p => p.key === key);
    customColors = JSON.parse(JSON.stringify(preset.colors));
    renderColorGrid();
    updatePreview();
}}

function renderColorGrid() {{
    const grid = document.getElementById('colorGrid');
    grid.innerHTML = '';
    Object.entries(COLOR_LABELS).forEach(([key, label]) => {{
        const val = customColors[key] || '#000000';
        const isRgba = val.startsWith('rgba');
        const hexVal = isRgba ? rgbaToHex(val) : val;
        grid.innerHTML += `
            <div class="color-item">
                <label>${{label}}</label>
                <input type="color" value="${{hexVal}}" onchange="updateColor('${{key}}', this.value)" id="cp-${{key}}">
                <input type="text" value="${{val}}" onchange="updateColorText('${{key}}', this.value)" id="ct-${{key}}">
            </div>
        `;
    }});
}}

function rgbaToHex(rgba) {{
    const m = rgba.match(/[\\d.]+/g);
    if (!m) return '#000000';
    const r = Math.round(parseFloat(m[0]));
    const g = Math.round(parseFloat(m[1]));
    const b = Math.round(parseFloat(m[2]));
    return '#' + [r,g,b].map(x => x.toString(16).padStart(2,'0')).join('');
}}

function updateColor(key, value) {{
    customColors[key] = value;
    document.getElementById('ct-' + key).value = value;
    currentMode = 'custom';
    updatePreview();
}}

function updateColorText(key, value) {{
    customColors[key] = value;
    if (!value.startsWith('rgba')) {{
        document.getElementById('cp-' + key).value = value;
    }}
    currentMode = 'custom';
    updatePreview();
}}

function updatePreview() {{
    let c;
    if (currentMode === 'preset') {{
        const preset = PRESETS.find(p => p.key === selectedPreset);
        c = preset ? preset.colors : ACTIVE_COLORS;
    }} else {{
        c = customColors;
    }}

    const phone = document.getElementById('previewPhone');
    phone.style.background = c.bg;
    phone.style.color = c.text_primary;

    const header = document.getElementById('pvHeader');
    header.style.background = c.bg_card;
    header.style.borderBottom = '1px solid ' + c.border;

    document.getElementById('pvBrand').style.color = c.gold;
    document.getElementById('pvWallet').style.color = c.gold;

    document.getElementById('pvBody').style.background = c.bg;

    ['pvCard1','pvCard2'].forEach(id => {{
        const el = document.getElementById(id);
        el.style.background = c.bg_card;
        el.style.border = '1px solid ' + c.border;
    }});

    const btn = document.getElementById('pvBtn');
    btn.style.background = `linear-gradient(135deg, ${{c.gold}}, ${{c.gold_dark}})`;
    btn.style.color = isLightColor(c.gold) ? '#000' : '#fff';

    const nav = document.getElementById('pvNav');
    nav.style.background = c.bg_card;
    nav.style.borderColor = c.border;
    nav.querySelectorAll('span').forEach((s, i) => {{
        s.style.color = i === 0 ? c.gold : c.text_muted;
    }});

    // Dice dots
    const diceDiv = document.getElementById('pvDice');
    diceDiv.innerHTML = '';
    for (let i = 1; i <= 6; i++) {{
        const d = document.createElement('div');
        d.style.cssText = `width:28px;height:28px;border-radius:6px;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:13px;background:${{c.bg_elevated}};border:1px solid ${{c.border}};color:${{c.text_primary}}`;
        d.textContent = i;
        diceDiv.appendChild(d);
    }}
}}

function isLightColor(hex) {{
    if (!hex || hex.startsWith('rgba')) return false;
    const c = hex.replace('#','');
    const r = parseInt(c.substr(0,2),16);
    const g = parseInt(c.substr(2,2),16);
    const b = parseInt(c.substr(4,2),16);
    return (r*299 + g*587 + b*114) / 1000 > 155;
}}

function saveTheme() {{
    const btn = document.getElementById('saveBtn');
    btn.disabled = true;
    btn.textContent = 'Saving...';

    const body = currentMode === 'preset'
        ? {{ preset: selectedPreset, custom: null }}
        : {{ preset: 'custom', custom: customColors }};

    fetch('/admin-api/set-theme/', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify(body),
    }})
    .then(r => r.json())
    .then(data => {{
        if (data.success) {{
            showToast('Theme applied! Web & App will update on next refresh.', 'success');
        }} else {{
            showToast('Error: ' + (data.error || 'Unknown'), 'error');
        }}
    }})
    .catch(e => showToast('Network error: ' + e.message, 'error'))
    .finally(() => {{
        btn.disabled = false;
        btn.innerHTML = '<span class="material-icons" style="font-size:16px;vertical-align:middle;margin-right:4px;">save</span> Apply Theme';
    }});
}}

function resetToOriginal() {{
    if (!confirm('Reset to original Gold & Black theme?')) return;
    selectedPreset = 'gold-black';
    currentMode = 'preset';
    const preset = PRESETS.find(p => p.key === 'gold-black');
    customColors = JSON.parse(JSON.stringify(preset.colors));
    renderPresets();
    renderColorGrid();
    updatePreview();
    saveTheme();
}}

function showToast(msg, type) {{
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.className = 'toast ' + type;
    t.style.display = 'block';
    setTimeout(() => t.style.display = 'none', 3000);
}}

// Init
renderPresets();
renderColorGrid();
updatePreview();
</script>
</body></html>'''


from django.views.static import serve
from django.urls import re_path

urlpatterns = [
    # Media files (before admin catch-all, no auth required)
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    path('api/', include('apiManager.urls')),
    path("auth/", include("djoser.urls.jwt")),
    path('admin-api/deposit-action/<int:pk>/<str:action>/', deposit_action_view, name='deposit_action'),
    path('admin-api/withdrawal-action/<int:pk>/<str:action>/', withdrawal_action_view, name='withdrawal_action'),
    path('admin-api/sidebar-counts/', admin_sidebar_counts, name='admin_sidebar_counts'),
    path('admin-api/dashboard-stats/', admin_dashboard_stats, name='admin_dashboard_stats'),
    path('admin-api/get-theme/', get_theme_api, name='get_theme_api'),
    path('admin-api/set-theme/', set_theme_api, name='set_theme_api'),
    path('admin-api/theme-presets/', get_theme_presets_api, name='get_theme_presets_api'),
    path('admin-api/theme-settings/', admin_theme_page, name='admin_theme_page'),
    path('', admin.site.urls),
]


if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL,
                          document_root=settings.STATIC_ROOT)
