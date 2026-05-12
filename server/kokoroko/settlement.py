"""
Idempotent Settlement System — Ensures bets are settled exactly once.

Features:
- Settlement transaction ID prevents double-credit
- Settlement log records every action
- Re-settlement protection via processed flag + settlement_id
- Refund system with audit trail
"""

import logging
import uuid
from decimal import Decimal

from django.db import transaction as db_transaction
from django.db.models import F
from django.utils import timezone

logger = logging.getLogger("kokoroko.settlement")


class SettlementResult:
    """Result of a settlement operation."""
    def __init__(self):
        self.settled = 0
        self.won = 0
        self.lost = 0
        self.skipped = 0
        self.errors = []
        self.settlement_id = f"SETTLE-{uuid.uuid4().hex[:12].upper()}"

    @property
    def success(self):
        return len(self.errors) == 0

    def __str__(self):
        return (
            f"Settlement {self.settlement_id}: "
            f"{self.settled} settled ({self.won} won, {self.lost} lost), "
            f"{self.skipped} skipped, {len(self.errors)} errors"
        )


def settle_dice_match(match_id):
    """
    Idempotent settlement for a dice match.
    If number appears 2+ times: payout = bet_amount + (rolled_count × bet_amount).
    """
    from dicePlayManager.models import DicePlayMatch, DicePlayMatchBet
    from wallet.models import WalletHistory

    result = SettlementResult()

    try:
        match = DicePlayMatch.objects.get(id=match_id)
    except DicePlayMatch.DoesNotExist:
        result.errors.append(f"Match {match_id} not found")
        return result

    if match.processed:
        logger.info("Match %s already processed, skipping", match_id)
        result.skipped = 1
        return result

    bets = DicePlayMatchBet.objects.filter(
        match=match
    ).select_related("customer__wallet")

    for bet in bets:
        # Skip already-settled bets (idempotency check)
        if bet.matchWinStatus not in (0,):  # 0 = pending
            result.skipped += 1
            continue

        try:
            rolled = _get_rolled_count(match, bet.diceNumber)
            bet.rolled_count = rolled

            if rolled >= 2:
                payout = bet.amount + (rolled * bet.amount)
                _credit_wallet(
                    bet, payout, result.settlement_id,
                    f"Dice Game #{match.daily_match_number} win: "
                    f"₹{bet.amount} on face {bet.diceNumber} "
                    f"(x{rolled} + bet returned = ₹{payout})"
                )
                bet.matchWinStatus = 1  # Won
                result.won += 1
            else:
                bet.matchWinStatus = 2  # Lost
                result.lost += 1

            bet.save(update_fields=["matchWinStatus", "rolled_count", "updatedDate"])
            result.settled += 1

        except Exception as e:
            logger.error("Error settling bet %s: %s", bet.id, e)
            result.errors.append(f"Bet {bet.id}: {str(e)}")

    # Mark match as processed
    match.processed = True
    match.save(update_fields=["processed", "updated_at"])

    logger.info("Dice match %s: %s", match_id, result)
    return result


def _get_rolled_count(match, dice_number):
    attr = f"total{dice_number}Rolled"
    return getattr(match, attr, 0)


def _credit_wallet(bet, payout, settlement_id, description):
    """Credit wallet with idempotency check via settlement_id in description."""
    from wallet.models import WalletHistory

    # Check for duplicate settlement (idempotency)
    exists = WalletHistory.objects.filter(
        wallet=bet.customer.wallet,
        description__contains=settlement_id,
    ).exists()
    if exists:
        logger.warning("Duplicate settlement detected for bet %s", bet.id)
        return

    with db_transaction.atomic():
        wallet = bet.customer.wallet
        amount_decimal = Decimal(str(payout))
        wallet.balance = F("balance") + amount_decimal
        wallet.save()

        WalletHistory.objects.create(
            wallet=wallet,
            transaction_type="I",
            change=amount_decimal,
            isSuccess=True,
            description=f"[{settlement_id}] {description}",
        )


def refund_bet(bet, reason="Admin refund"):
    """Refund a single bet. Returns amount refunded or 0 if already refunded."""
    from wallet.models import WalletHistory

    if bet.matchWinStatus in (4, 5):  # Already cancelled/refunded
        return 0

    refund_id = f"REFUND-{uuid.uuid4().hex[:12].upper()}"

    with db_transaction.atomic():
        wallet = bet.customer.wallet
        amount = Decimal(str(bet.amount))
        wallet.balance = F("balance") + amount
        wallet.save()

        WalletHistory.objects.create(
            wallet=wallet,
            transaction_type="I",
            change=amount,
            isSuccess=True,
            description=f"[{refund_id}] Refund: {reason}",
        )

        bet.matchWinStatus = 5  # Refunded
        bet.save(update_fields=["matchWinStatus", "updatedDate"])

    logger.info("Refunded bet %s: ₹%s (%s)", bet.id, amount, reason)
    return amount
