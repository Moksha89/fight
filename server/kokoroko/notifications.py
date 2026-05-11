"""
Notification System — In-app notifications for users and admins.

Notification types:
- DEPOSIT_SUBMITTED, DEPOSIT_APPROVED, DEPOSIT_REJECTED
- WITHDRAWAL_SUBMITTED, WITHDRAWAL_APPROVED, WITHDRAWAL_REJECTED
- BET_PLACED, BET_WON, BET_LOST, BET_REFUNDED
- MATCH_CANCELLED
- BONUS_RECEIVED
- SYSTEM_ALERT

Admin notifications:
- NEW_DEPOSIT, NEW_WITHDRAWAL
- HIGH_VALUE_BET
- SUSPICIOUS_ACTIVITY
- SYSTEM_ERROR
"""

import logging
from django.utils import timezone

logger = logging.getLogger("kokoroko.notifications")


class NotificationType:
    # User notifications
    DEPOSIT_SUBMITTED = "deposit_submitted"
    DEPOSIT_APPROVED = "deposit_approved"
    DEPOSIT_REJECTED = "deposit_rejected"
    WITHDRAWAL_SUBMITTED = "withdrawal_submitted"
    WITHDRAWAL_APPROVED = "withdrawal_approved"
    WITHDRAWAL_REJECTED = "withdrawal_rejected"
    BET_PLACED = "bet_placed"
    BET_WON = "bet_won"
    BET_LOST = "bet_lost"
    BET_REFUNDED = "bet_refunded"
    MATCH_CANCELLED = "match_cancelled"
    BONUS_RECEIVED = "bonus_received"
    SYSTEM_ALERT = "system_alert"

    # Admin notifications
    ADMIN_NEW_DEPOSIT = "admin_new_deposit"
    ADMIN_NEW_WITHDRAWAL = "admin_new_withdrawal"
    ADMIN_HIGH_VALUE_BET = "admin_high_value_bet"
    ADMIN_SUSPICIOUS_ACTIVITY = "admin_suspicious"
    ADMIN_SYSTEM_ERROR = "admin_system_error"
    ADMIN_MATCH_RESULT_PENDING = "admin_match_result_pending"


# Notification templates (English + Hindi)
TEMPLATES = {
    NotificationType.DEPOSIT_SUBMITTED: {
        "title": "Deposit Submitted",
        "title_hi": "जमा अनुरोध भेजा गया",
        "body": "Your deposit of ₹{amount} has been submitted. We'll review it shortly.",
        "body_hi": "आपका ₹{amount} का जमा अनुरोध भेज दिया गया है। हम जल्द ही इसकी समीक्षा करेंगे।",
    },
    NotificationType.DEPOSIT_APPROVED: {
        "title": "Deposit Approved",
        "title_hi": "जमा स्वीकृत",
        "body": "Your deposit of ₹{amount} has been approved and added to your wallet.",
        "body_hi": "आपका ₹{amount} का जमा स्वीकृत हो गया है और आपके वॉलेट में जोड़ दिया गया है।",
    },
    NotificationType.DEPOSIT_REJECTED: {
        "title": "Deposit Rejected",
        "title_hi": "जमा अस्वीकृत",
        "body": "Your deposit of ₹{amount} was rejected. Reason: {reason}",
        "body_hi": "आपका ₹{amount} का जमा अस्वीकृत हो गया। कारण: {reason}",
    },
    NotificationType.WITHDRAWAL_SUBMITTED: {
        "title": "Withdrawal Requested",
        "title_hi": "निकासी अनुरोध",
        "body": "Your withdrawal of ₹{amount} has been submitted for processing.",
        "body_hi": "आपका ₹{amount} का निकासी अनुरोध प्रसंस्करण के लिए भेजा गया है।",
    },
    NotificationType.WITHDRAWAL_APPROVED: {
        "title": "Withdrawal Approved",
        "title_hi": "निकासी स्वीकृत",
        "body": "Your withdrawal of ₹{amount} has been approved and sent to your account.",
        "body_hi": "आपका ₹{amount} का निकासी स्वीकृत हो गया है और आपके खाते में भेज दिया गया है।",
    },
    NotificationType.BET_WON: {
        "title": "You Won!",
        "title_hi": "आप जीत गए!",
        "body": "Your bet of ₹{amount} on {game} won ₹{payout}!",
        "body_hi": "आपकी {game} पर ₹{amount} की शर्त जीत गई! जीत: ₹{payout}",
    },
    NotificationType.BET_LOST: {
        "title": "Bet Lost",
        "title_hi": "शर्त हारी",
        "body": "Your bet of ₹{amount} on {game} did not win this time.",
        "body_hi": "आपकी {game} पर ₹{amount} की शर्त इस बार नहीं जीती।",
    },
    NotificationType.BET_REFUNDED: {
        "title": "Bet Refunded",
        "title_hi": "शर्त वापस",
        "body": "Your bet of ₹{amount} has been refunded. Reason: {reason}",
        "body_hi": "आपकी ₹{amount} की शर्त वापस कर दी गई है। कारण: {reason}",
    },
    NotificationType.MATCH_CANCELLED: {
        "title": "Match Cancelled",
        "title_hi": "मैच रद्द",
        "body": "{game} has been cancelled. All bets have been refunded.",
        "body_hi": "{game} रद्द कर दिया गया है। सभी शर्तें वापस कर दी गई हैं।",
    },
    NotificationType.BONUS_RECEIVED: {
        "title": "Bonus Received",
        "title_hi": "बोनस मिला",
        "body": "You received a bonus of ₹{amount}!",
        "body_hi": "आपको ₹{amount} का बोनस मिला!",
    },
}


def _is_notification_enabled(notification_type):
    """Check if this notification type is enabled in Feature Controls."""
    try:
        from django.core.cache import cache
        config = cache.get("feature_controls", {})
        notif_config = config.get("notifications", {})
        if not notif_config.get("enabled", True):
            return False
        if notification_type in ("deposit_submitted", "deposit_approved", "deposit_rejected"):
            return notif_config.get("deposit_alerts", True)
        if notification_type in ("withdrawal_submitted", "withdrawal_approved", "withdrawal_rejected"):
            return notif_config.get("withdrawal_alerts", True)
        if notification_type in ("bet_placed", "bet_won", "bet_lost", "bet_refunded"):
            return notif_config.get("bet_alerts", True)
        return notif_config.get("system_alerts", True)
    except Exception:
        return True


def create_notification(user, notification_type, data=None):
    """
    Create an in-app notification for a user.
    Uses Django cache as lightweight storage (can be replaced with DB model).
    """
    if not _is_notification_enabled(notification_type):
        return None
    from django.core.cache import cache
    data = data or {}

    template = TEMPLATES.get(notification_type, {})
    title = template.get("title", notification_type)
    title_hi = template.get("title_hi", title)
    body = template.get("body", "").format(**data) if template.get("body") else ""
    body_hi = template.get("body_hi", body).format(**data) if template.get("body_hi") else body

    notification = {
        "type": notification_type,
        "title": title,
        "title_hi": title_hi,
        "body": body,
        "body_hi": body_hi,
        "data": data,
        "read": False,
        "created_at": timezone.now().isoformat(),
    }

    # Store in user's notification list (cache-based, 30-day TTL)
    cache_key = f"notifications:{user.id}"
    notifications = cache.get(cache_key, [])
    notifications.insert(0, notification)
    notifications = notifications[:100]  # Keep last 100
    cache.set(cache_key, notifications, timeout=30 * 24 * 3600)

    logger.info("Notification [%s] for user %s: %s", notification_type, user.id, title)

    # Broadcast via WebSocket if available
    try:
        _broadcast_notification(user.id, notification)
    except Exception:
        pass

    return notification


def get_user_notifications(user, limit=50):
    """Get user's recent notifications."""
    from django.core.cache import cache
    cache_key = f"notifications:{user.id}"
    notifications = cache.get(cache_key, [])
    return notifications[:limit]


def mark_notification_read(user, index):
    """Mark a specific notification as read."""
    from django.core.cache import cache
    cache_key = f"notifications:{user.id}"
    notifications = cache.get(cache_key, [])
    if 0 <= index < len(notifications):
        notifications[index]["read"] = True
        cache.set(cache_key, notifications, timeout=30 * 24 * 3600)
    return True


def get_unread_count(user):
    """Get count of unread notifications."""
    from django.core.cache import cache
    cache_key = f"notifications:{user.id}"
    notifications = cache.get(cache_key, [])
    return sum(1 for n in notifications if not n.get("read"))


def create_admin_notification(notification_type, data=None):
    """Create a notification visible to all admin users."""
    from django.core.cache import cache
    data = data or {}

    notification = {
        "type": notification_type,
        "data": data,
        "read": False,
        "created_at": timezone.now().isoformat(),
    }

    cache_key = "admin_notifications"
    notifications = cache.get(cache_key, [])
    notifications.insert(0, notification)
    notifications = notifications[:200]
    cache.set(cache_key, notifications, timeout=7 * 24 * 3600)

    logger.info("Admin notification [%s]: %s", notification_type, data)
    return notification


def mark_all_read(user):
    """Mark all notifications as read for a user."""
    from django.core.cache import cache
    cache_key = f"notifications:{user.id}"
    notifications = cache.get(cache_key, [])
    for n in notifications:
        n["read"] = True
    cache.set(cache_key, notifications, timeout=30 * 24 * 3600)
    return True


def _broadcast_notification(user_id, notification):
    """Send notification via WebSocket channel (if channels is available)."""
    try:
        from kokoroko.ws_broadcast import broadcast_notification
        broadcast_notification(user_id, notification)
    except (ImportError, Exception):
        pass
