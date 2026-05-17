"""
Security System — OTP rate limiting, IP logging, admin action audit.

Features:
- OTP rate limiting (max 5 per 10 min per phone/IP)
- Login attempt limiting (max 10 per 15 min per IP)
- IP/device logging for all auth events
- Admin action audit trail
- File upload validation
- Session expiry management
"""

import logging
import hashlib
from functools import wraps

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger("kokoroko.security")


# ─── Rate Limiting ───────────────────────────────────────────────────────────

class RateLimiter:
    """Token-bucket rate limiter using Django cache."""

    @staticmethod
    def check(key, max_attempts, window_seconds):
        """
        Check if action is allowed.
        Returns (allowed: bool, remaining: int, retry_after: int|None).
        """
        cache_key = f"ratelimit:{key}"
        data = cache.get(cache_key)

        if data is None:
            cache.set(cache_key, {"count": 1, "start": timezone.now().timestamp()}, window_seconds)
            return True, max_attempts - 1, None

        elapsed = timezone.now().timestamp() - data["start"]
        if elapsed >= window_seconds:
            cache.set(cache_key, {"count": 1, "start": timezone.now().timestamp()}, window_seconds)
            return True, max_attempts - 1, None

        if data["count"] >= max_attempts:
            retry_after = int(window_seconds - elapsed)
            return False, 0, retry_after

        data["count"] += 1
        cache.set(cache_key, data, int(window_seconds - elapsed))
        return True, max_attempts - data["count"], None

    @staticmethod
    def reset(key):
        cache.delete(f"ratelimit:{key}")


def check_otp_rate_limit(identifier, ip_address=None):
    """
    Check OTP rate limit: max 5 OTPs per 10 minutes per identifier.
    Also checks per-IP limit: max 10 OTPs per 10 minutes per IP.
    """
    allowed, remaining, retry_after = RateLimiter.check(
        f"otp:{identifier}", max_attempts=5, window_seconds=600
    )
    if not allowed:
        return False, f"Too many OTP requests. Try again in {retry_after}s.", retry_after

    if ip_address:
        ip_allowed, _, ip_retry = RateLimiter.check(
            f"otp_ip:{ip_address}", max_attempts=10, window_seconds=600
        )
        if not ip_allowed:
            return False, f"Too many OTP requests from this IP. Try again in {ip_retry}s.", ip_retry

    return True, None, None


def check_login_rate_limit(ip_address):
    """Check login attempt rate limit: max 10 per 15 min per IP."""
    allowed, remaining, retry_after = RateLimiter.check(
        f"login:{ip_address}", max_attempts=10, window_seconds=900
    )
    if not allowed:
        return False, f"Too many login attempts. Try again in {retry_after}s.", retry_after
    return True, None, None


# ─── IP/Device Logging ───────────────────────────────────────────────────────

def log_auth_event(user, event_type, request=None, details=None):
    """
    Log an authentication event with IP and device info.
    Stores in cache with 90-day TTL.
    """
    ip = get_client_ip(request) if request else "unknown"
    user_agent = request.META.get("HTTP_USER_AGENT", "")[:200] if request else ""
    device_hash = hashlib.md5(user_agent.encode()).hexdigest()[:12]

    event = {
        "type": event_type,
        "ip": ip,
        "user_agent": user_agent[:100],
        "device_hash": device_hash,
        "details": details or {},
        "timestamp": timezone.now().isoformat(),
    }

    cache_key = f"auth_log:{user.id}"
    events = cache.get(cache_key, [])
    events.insert(0, event)
    events = events[:200]  # Keep last 200 events
    cache.set(cache_key, events, timeout=90 * 24 * 3600)

    logger.info(
        "Auth event [%s] user=%s ip=%s device=%s",
        event_type, user.id, ip, device_hash
    )
    return event


def get_auth_log(user, limit=50):
    """Get user's authentication event log."""
    cache_key = f"auth_log:{user.id}"
    events = cache.get(cache_key, [])
    return events[:limit]


def get_client_ip(request):
    """Extract client IP from request, handling proxies."""
    if not request:
        return "unknown"
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


# ─── Admin Action Audit ──────────────────────────────────────────────────────

def log_admin_action(admin_user, action, target_type, target_id, details=None, request=None):
    """
    Log an admin action for audit trail.
    Examples: approve_deposit, reject_withdrawal, declare_winner, edit_user, etc.
    """
    ip = get_client_ip(request) if request else "unknown"

    entry = {
        "admin_id": admin_user.id,
        "admin_email": getattr(admin_user, "email", str(admin_user)),
        "action": action,
        "target_type": target_type,
        "target_id": str(target_id),
        "details": details or {},
        "ip": ip,
        "timestamp": timezone.now().isoformat(),
    }

    # Store in cache-based audit log (7-day TTL, max 1000 entries)
    cache_key = "admin_audit_log"
    log = cache.get(cache_key, [])
    log.insert(0, entry)
    log = log[:1000]
    cache.set(cache_key, log, timeout=7 * 24 * 3600)

    logger.info(
        "Admin action: %s by %s on %s:%s ip=%s",
        action, admin_user.id, target_type, target_id, ip
    )
    return entry


def get_admin_audit_log(limit=100, action_filter=None, admin_id=None):
    """Get admin audit log entries."""
    log = cache.get("admin_audit_log", [])
    if action_filter:
        log = [e for e in log if e["action"] == action_filter]
    if admin_id:
        log = [e for e in log if e["admin_id"] == admin_id]
    return log[:limit]


# ─── File Upload Validation ──────────────────────────────────────────────────

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def validate_file_upload(file_obj, allowed_types=None, max_size=None):
    """
    Validate uploaded file.
    Returns (valid: bool, error: str|None).
    """
    allowed = allowed_types or ALLOWED_IMAGE_TYPES
    size_limit = max_size or MAX_FILE_SIZE

    if not file_obj:
        return False, "No file provided"

    if hasattr(file_obj, "size") and file_obj.size > size_limit:
        return False, f"File too large (max {size_limit // 1024 // 1024}MB)"

    if hasattr(file_obj, "content_type") and file_obj.content_type not in allowed:
        return False, f"Invalid file type: {file_obj.content_type}"

    return True, None
