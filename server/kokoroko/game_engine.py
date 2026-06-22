"""
Game Engine System — Unified state machine for dice and cockfight games.

Round States:
  CREATED → BETTING_OPEN → BETTING_CLOSED → ROLLING → RESULT_REVEAL → SETTLEMENT → COMPLETED
  Any state can transition to CANCELLED (with refunds).

Cockfight States:
  CREATED → BETTING_OPEN → BETTING_CLOSED → LIVE_PLAY → RESULT_DECLARED → SETTLEMENT → COMPLETED
"""

import logging

logger = logging.getLogger("kokoroko.game_engine")


# ─── Dice Round States ───────────────────────────────────────────────────────

class DiceRoundState:
    CREATED = "created"
    BETTING_OPEN = "betting"
    BETTING_CLOSED = "betting_closed"
    ROLLING = "shuffling"
    RESULT_REVEAL = "result"
    SETTLEMENT = "settlement"
    COMPLETED = "done"
    CANCELLED = "cancelled"

    ALL = [CREATED, BETTING_OPEN, BETTING_CLOSED, ROLLING, RESULT_REVEAL,
           SETTLEMENT, COMPLETED, CANCELLED]

    TRANSITIONS = {
        CREATED: [BETTING_OPEN, CANCELLED],
        BETTING_OPEN: [BETTING_CLOSED, CANCELLED],
        BETTING_CLOSED: [ROLLING, CANCELLED],
        ROLLING: [RESULT_REVEAL, CANCELLED],
        RESULT_REVEAL: [SETTLEMENT, CANCELLED],
        SETTLEMENT: [COMPLETED],
        COMPLETED: [],
        CANCELLED: [],
    }

    @classmethod
    def can_transition(cls, from_state, to_state):
        return to_state in cls.TRANSITIONS.get(from_state, [])

    @classmethod
    def is_betting_allowed(cls, state):
        return state == cls.BETTING_OPEN

    @classmethod
    def is_terminal(cls, state):
        return state in (cls.COMPLETED, cls.CANCELLED)


# ─── Cockfight Match States ─────────────────────────────────────────────────

class CockfightMatchState:
    CREATED = "created"
    BETTING_OPEN = "betting_open"
    BETTING_CLOSED = "betting_closed"
    LIVE_PLAY = "live_play"
    RESULT_DECLARED = "result_declared"
    SETTLEMENT = "settlement"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

    TRANSITIONS = {
        CREATED: [BETTING_OPEN, CANCELLED],
        BETTING_OPEN: [BETTING_CLOSED, CANCELLED],
        BETTING_CLOSED: [LIVE_PLAY, CANCELLED],
        LIVE_PLAY: [RESULT_DECLARED, CANCELLED],
        RESULT_DECLARED: [SETTLEMENT, CANCELLED],
        SETTLEMENT: [COMPLETED],
        COMPLETED: [],
        CANCELLED: [],
    }

    @classmethod
    def can_transition(cls, from_state, to_state):
        return to_state in cls.TRANSITIONS.get(from_state, [])


# ─── Bet Statuses ────────────────────────────────────────────────────────────

class BetStatus:
    PENDING = 0
    ACCEPTED = 1
    WON = 2
    LOST = 3
    CANCELLED = 4
    REFUNDED = 5
    REJECTED = 6

    LABELS = {
        PENDING: "Pending",
        ACCEPTED: "Accepted",
        WON: "Won",
        LOST: "Lost",
        CANCELLED: "Cancelled",
        REFUNDED: "Refunded",
        REJECTED: "Rejected",
    }

    # Map old status codes to new
    LEGACY_MAP = {0: PENDING, 1: WON, 2: LOST}

    @classmethod
    def label(cls, status):
        return cls.LABELS.get(status, "Unknown")

    @classmethod
    def is_terminal(cls, status):
        return status in (cls.WON, cls.LOST, cls.CANCELLED, cls.REFUNDED, cls.REJECTED)


# ─── State Transition Helper ─────────────────────────────────────────────────

def transition_dice_round(match, new_state, save=True):
    """
    Transition a DicePlayMatch to a new state.
    Validates the transition is allowed. Logs the change.
    Returns True if transitioned, raises ValueError if invalid.
    """
    current = match.virtual_phase or DiceRoundState.CREATED
    if not DiceRoundState.can_transition(current, new_state):
        raise ValueError(
            f"Invalid dice state transition: {current} → {new_state}"
        )

    from django.utils import timezone
    match.virtual_phase = new_state
    match.phase_started_at = timezone.now()

    if new_state == DiceRoundState.BETTING_OPEN:
        match.isBettingEnabled = True
        match.isLive = True
    elif new_state == DiceRoundState.BETTING_CLOSED:
        match.isBettingEnabled = False
    elif new_state == DiceRoundState.COMPLETED:
        match.isLive = False

    if save:
        match.save()

    logger.info(
        "Dice round %s (Game #%s): %s → %s",
        match.id, match.daily_match_number, current, new_state
    )
    return True


def cancel_dice_round(match, reason="Admin cancelled"):
    """Cancel a dice round and refund all pending bets."""
    from django.utils import timezone
    current = match.virtual_phase or DiceRoundState.CREATED
    if DiceRoundState.is_terminal(current):
        raise ValueError(f"Cannot cancel round in terminal state: {current}")

    match.virtual_phase = DiceRoundState.CANCELLED
    match.phase_started_at = timezone.now()
    match.isBettingEnabled = False
    match.isLive = False
    match.save()

    # Refund all pending bets
    refunded = refund_dice_round_bets(match, reason)
    logger.warning(
        "Dice round %s cancelled (%s). Refunded %d bets.",
        match.id, reason, refunded
    )
    return refunded


def refund_dice_round_bets(match, reason="Round cancelled"):
    """Refund all unsettled bets for a dice round."""
    from dicePlayManager.models import DicePlayMatchBet
    from wallet.models import WalletHistory
    from django.db import transaction as db_transaction
    from django.db.models import F
    from decimal import Decimal

    unsettled = DicePlayMatchBet.objects.filter(
        match=match, matchWinStatus=0
    ).select_related("customer__wallet")

    count = 0
    for bet in unsettled:
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
                description=f"Refund: Dice Game #{match.daily_match_number} - {reason}",
            )
            bet.matchWinStatus = BetStatus.REFUNDED
            bet.save(update_fields=["matchWinStatus", "updatedDate"])
            count += 1

    return count
