"""
Per-endpoint DRF throttle classes.

These provide application-level rate limiting on top of Nginx limits.
Redis-backed via Django cache (the DRF default when CACHES uses Redis).
"""

from rest_framework.throttling import UserRateThrottle, AnonRateThrottle


# ─── Bet Placement ───────────────────────────────────────────────────────────

class CockfightBetThrottle(UserRateThrottle):
    """15 bets/minute per authenticated user for cockfight."""
    scope = "cockfight_bet"
    rate = "15/minute"


class DiceBetThrottle(UserRateThrottle):
    """
    20 bets/minute per authenticated user for dice.
    Higher than cockfight because multi-number betting sends
    up to 5 sequential API calls per round.
    """
    scope = "dice_bet"
    rate = "20/minute"


# ─── Wallet / Financial ─────────────────────────────────────────────────────

class WalletInfoThrottle(UserRateThrottle):
    """30 requests/minute for wallet balance lookups."""
    scope = "wallet_info"
    rate = "30/minute"


class DepositThrottle(UserRateThrottle):
    """10 deposit requests/hour per user."""
    scope = "deposit_request"
    rate = "10/hour"


class WithdrawalThrottle(UserRateThrottle):
    """5 withdrawal requests/hour per user."""
    scope = "withdrawal_request"
    rate = "5/hour"


# ─── History / Read-Heavy ────────────────────────────────────────────────────

class HistoryThrottle(UserRateThrottle):
    """60 requests/minute for bet/wallet history endpoints."""
    scope = "history"
    rate = "60/minute"


# ─── Admin ───────────────────────────────────────────────────────────────────

class AdminActionThrottle(UserRateThrottle):
    """60 requests/minute for admin API actions."""
    scope = "admin_action"
    rate = "60/minute"
