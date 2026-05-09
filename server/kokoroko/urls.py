import logging

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
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
    path('', admin.site.urls),
]


if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL,
                          document_root=settings.STATIC_ROOT)
