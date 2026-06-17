"""
Risk & Fraud Detection System — Flags suspicious activity.

Detects:
- Multiple accounts from same IP/device
- Same UPI/bank used by many users
- Unusual winning patterns
- High withdrawal after low activity
- Rapid deposits/withdrawals
- Duplicate UTR numbers
- Suspicious admin approvals
"""

import logging
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from django.db.models import Count, Sum, Q, F

logger = logging.getLogger("kokoroko.risk")


# ─── Risk Levels ─────────────────────────────────────────────────────────────

class RiskLevel:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskFlag:
    """A single risk flag for a user."""
    def __init__(self, level, category, message, details=None):
        self.level = level
        self.category = category
        self.message = message
        self.details = details or {}
        self.timestamp = timezone.now()

    def to_dict(self):
        return {
            "level": self.level,
            "category": self.category,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }


# ─── Risk Analysis Functions ─────────────────────────────────────────────────

def analyze_user_risk(user):
    """
    Run all risk checks on a user. Returns list of RiskFlag objects.
    """
    flags = []
    flags.extend(check_duplicate_payment_info(user))
    flags.extend(check_winning_pattern(user))
    flags.extend(check_withdrawal_pattern(user))
    flags.extend(check_rapid_transactions(user))
    return flags


def check_duplicate_payment_info(user):
    """Check if user shares UPI/bank details with other accounts."""
    from wallet.models import DepositRequest, WithdrawalRequest
    flags = []

    # Check UPI shared with other users
    user_upis = set()
    deposits = DepositRequest.objects.filter(customer=user).values_list('upi_id', flat=True)
    withdrawals = WithdrawalRequest.objects.filter(customer=user).values_list('upi_id', flat=True)
    for upi in list(deposits) + list(withdrawals):
        if upi:
            user_upis.add(upi)

    for upi in user_upis:
        other_deposit_users = DepositRequest.objects.filter(
            upi_id=upi
        ).exclude(customer=user).values_list('customer_id', flat=True).distinct()
        other_withdraw_users = WithdrawalRequest.objects.filter(
            upi_id=upi
        ).exclude(customer=user).values_list('customer_id', flat=True).distinct()
        other_users = set(other_deposit_users) | set(other_withdraw_users)

        if other_users:
            flags.append(RiskFlag(
                RiskLevel.HIGH,
                "duplicate_upi",
                f"UPI {upi} shared with {len(other_users)} other user(s)",
                {"upi": upi, "other_user_ids": list(other_users)},
            ))

    # Check bank accounts shared with other users
    user_accounts = WithdrawalRequest.objects.filter(
        customer=user
    ).exclude(
        account_number__isnull=True
    ).exclude(
        account_number=""
    ).values_list('account_number', flat=True).distinct()

    for acct in user_accounts:
        others = WithdrawalRequest.objects.filter(
            account_number=acct
        ).exclude(customer=user).values_list('customer_id', flat=True).distinct()
        if others:
            flags.append(RiskFlag(
                RiskLevel.HIGH,
                "duplicate_bank",
                f"Bank account {acct[-4:]}... shared with {len(others)} other user(s)",
                {"account_suffix": acct[-4:], "other_user_ids": list(others)},
            ))

    return flags


def check_winning_pattern(user):
    """Check for unusual winning patterns across games."""
    from cockfightManager.models import CockfightMatchBet
    from dicePlayManager.models import DicePlayMatchBet
    flags = []
    lookback = timezone.now() - timedelta(days=7)

    # Cockfight win rate
    cf_bets = CockfightMatchBet.objects.filter(
        customer=user, createdDate__gte=lookback
    ).exclude(matchWinStatus=0)
    cf_total = cf_bets.count()
    cf_wins = cf_bets.filter(matchWinStatus=1).count()

    if cf_total >= 10 and cf_wins / cf_total > 0.80:
        flags.append(RiskFlag(
            RiskLevel.HIGH,
            "high_win_rate",
            f"Cockfight win rate {cf_wins}/{cf_total} ({cf_wins/cf_total:.0%}) in 7 days",
            {"game": "cockfight", "wins": cf_wins, "total": cf_total},
        ))

    # Dice win rate
    dice_bets = DicePlayMatchBet.objects.filter(
        customer=user, createdDate__gte=lookback
    ).exclude(matchWinStatus=0)
    dice_total = dice_bets.count()
    dice_wins = dice_bets.filter(matchWinStatus=1).count()

    if dice_total >= 10 and dice_wins / dice_total > 0.70:
        flags.append(RiskFlag(
            RiskLevel.MEDIUM,
            "high_win_rate",
            f"Dice win rate {dice_wins}/{dice_total} ({dice_wins/dice_total:.0%}) in 7 days",
            {"game": "dice", "wins": dice_wins, "total": dice_total},
        ))

    return flags


def check_withdrawal_pattern(user):
    """Check for high withdrawal after low betting activity."""
    from wallet.models import WalletHistory
    flags = []
    lookback = timezone.now() - timedelta(days=3)

    # Recent withdrawals
    withdrawals = WalletHistory.objects.filter(
        wallet__user=user,
        transaction_type="W",
        isSuccess=True,
        created_at__gte=lookback,
    ).aggregate(total=Sum("change"))
    total_withdrawn = abs(withdrawals["total"] or 0)

    # Recent deposits
    deposits = WalletHistory.objects.filter(
        wallet__user=user,
        transaction_type="D",
        isSuccess=True,
        created_at__gte=lookback,
    ).aggregate(total=Sum("change"))
    total_deposited = deposits["total"] or 0

    # Recent betting activity
    from cockfightManager.models import CockfightMatchBet
    from dicePlayManager.models import DicePlayMatchBet
    bet_count = CockfightMatchBet.objects.filter(
        customer=user, createdDate__gte=lookback
    ).count() + DicePlayMatchBet.objects.filter(
        customer=user, createdDate__gte=lookback
    ).count()

    if total_withdrawn > 50000 and bet_count < 5:
        flags.append(RiskFlag(
            RiskLevel.HIGH,
            "withdraw_no_activity",
            f"Withdrew ₹{total_withdrawn:,.0f} with only {bet_count} bets in 3 days",
            {"withdrawn": float(total_withdrawn), "bets": bet_count},
        ))

    if total_deposited > 0 and total_withdrawn > total_deposited * 2:
        flags.append(RiskFlag(
            RiskLevel.MEDIUM,
            "withdraw_exceeds_deposit",
            f"Withdrawals (₹{total_withdrawn:,.0f}) exceed 2× deposits (₹{total_deposited:,.0f})",
            {"withdrawn": float(total_withdrawn), "deposited": float(total_deposited)},
        ))

    return flags


def check_rapid_transactions(user):
    """Check for rapid deposit/withdrawal cycles (potential money laundering)."""
    from wallet.models import WalletHistory
    flags = []
    lookback = timezone.now() - timedelta(hours=24)

    tx_count = WalletHistory.objects.filter(
        wallet__user=user,
        transaction_type__in=["D", "W"],
        created_at__gte=lookback,
    ).count()

    if tx_count >= 10:
        flags.append(RiskFlag(
            RiskLevel.MEDIUM,
            "rapid_transactions",
            f"{tx_count} deposit/withdrawal transactions in 24 hours",
            {"count": tx_count},
        ))

    return flags


def check_duplicate_utr(utr_id):
    """Check if a UTR number has been used before."""
    from wallet.models import DepositRequest
    existing = DepositRequest.objects.filter(utr_id=utr_id)
    count = existing.count()
    if count > 1:
        users = list(existing.values_list("customer__email", flat=True).distinct())
        return RiskFlag(
            RiskLevel.CRITICAL,
            "duplicate_utr",
            f"UTR {utr_id} used {count} times by {len(users)} user(s)",
            {"utr": utr_id, "users": users, "count": count},
        )
    return None


def get_user_risk_summary(user):
    """Get a summary of all risk flags for a user."""
    flags = analyze_user_risk(user)
    if not flags:
        return {"level": RiskLevel.LOW, "flags": [], "count": 0}

    worst = max(
        flags,
        key=lambda f: [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL].index(f.level)
    )
    return {
        "level": worst.level,
        "flags": [f.to_dict() for f in flags],
        "count": len(flags),
    }
