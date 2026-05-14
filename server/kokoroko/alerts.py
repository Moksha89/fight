"""
Security Event Alerts System (S6.8)

Tracks and alerts on security-relevant events with threshold-based alerting.
Supports webhook delivery (Telegram/Slack/email) via env config.

Env vars:
    ALERT_WEBHOOK_URL  — Webhook endpoint for alert delivery
    ALERT_CHANNEL      — "telegram", "slack", or "email"
    ALERT_ENABLED      — "true" to enable webhook delivery (default "false")
"""

import json
import logging
import os
import time

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger("kokoroko.security")

# ─── Alert Thresholds ────────────────────────────────────────────────────────

ALERT_THRESHOLDS = {
    "failed_login": {"count": 10, "window": 300, "severity": "warning"},
    "failed_otp": {"count": 10, "window": 300, "severity": "warning"},
    "rate_limit_spike": {"count": 50, "window": 60, "severity": "warning"},
    "admin_login": {"count": 1, "window": 1, "severity": "info"},
    "deposit_approve": {"count": 1, "window": 1, "severity": "info"},
    "deposit_reject": {"count": 1, "window": 1, "severity": "info"},
    "withdrawal_approve": {"count": 1, "window": 1, "severity": "info"},
    "withdrawal_reject": {"count": 1, "window": 1, "severity": "info"},
    "large_transaction": {"count": 1, "window": 1, "severity": "warning"},
    "ws_connection_spam": {"count": 20, "window": 60, "severity": "warning"},
    "negative_balance_attempt": {"count": 1, "window": 1, "severity": "critical"},
    "redis_failure": {"count": 3, "window": 60, "severity": "critical"},
    "db_failure": {"count": 3, "window": 60, "severity": "critical"},
    "ffmpeg_failure": {"count": 3, "window": 300, "severity": "warning"},
    "csrf_failure": {"count": 5, "window": 300, "severity": "warning"},
}


def track_security_event(event_type, details=None, user_id=None, ip=None):
    """
    Track a security event and check if alert threshold is reached.

    Args:
        event_type: Key from ALERT_THRESHOLDS
        details: Optional dict with event context
        user_id: Optional user ID
        ip: Optional IP address
    """
    threshold = ALERT_THRESHOLDS.get(event_type)
    if not threshold:
        logger.warning("Unknown security event type: %s", event_type)
        return

    # Increment counter
    window = threshold["window"]
    cache_key = f"security_event:{event_type}"
    try:
        count = cache.get(cache_key, 0)
        cache.set(cache_key, count + 1, timeout=window)
    except Exception:
        count = 0

    # Log the event
    log_data = {
        "event": event_type,
        "severity": threshold["severity"],
        "user_id": user_id,
        "ip": ip,
    }
    if details:
        # Never log sensitive data
        safe_details = {
            k: v for k, v in details.items()
            if k.lower() not in ("password", "token", "otp", "secret", "jwt")
        }
        log_data["details"] = safe_details

    severity = threshold["severity"]
    if severity == "critical":
        logger.critical("SECURITY EVENT [%s]: %s", event_type, json.dumps(log_data, default=str))
    elif severity == "warning":
        logger.warning("Security event [%s]: %s", event_type, json.dumps(log_data, default=str))
    else:
        logger.info("Security event [%s]: %s", event_type, json.dumps(log_data, default=str))

    # Store in recent events list
    _store_recent_event(event_type, log_data)

    # Check threshold for alerting
    if count + 1 >= threshold["count"]:
        _maybe_send_alert(event_type, count + 1, threshold, log_data)

    # Track recording failures for health checks
    if event_type == "ffmpeg_failure":
        try:
            failures = cache.get("recording_failures_24h", 0)
            cache.set("recording_failures_24h", failures + 1, timeout=86400)
            cache.set("recording_last_failure", timezone.now().isoformat(), timeout=86400)
        except Exception:
            pass


def _store_recent_event(event_type, log_data):
    """Store recent security events for admin dashboard visibility."""
    try:
        cache_key = "security_events_recent"
        events = cache.get(cache_key, [])
        events.insert(0, {
            **log_data,
            "timestamp": timezone.now().isoformat(),
        })
        events = events[:500]  # Keep last 500
        cache.set(cache_key, events, timeout=86400)  # 24h
    except Exception:
        pass


def get_recent_security_events(limit=100, event_filter=None, severity_filter=None):
    """Get recent security events for admin display."""
    try:
        events = cache.get("security_events_recent", [])
        if event_filter:
            events = [e for e in events if e.get("event") == event_filter]
        if severity_filter:
            events = [e for e in events if e.get("severity") == severity_filter]
        return events[:limit]
    except Exception:
        return []


def get_security_event_counts(hours=24):
    """Get event type counts for the last N hours."""
    counts = {}
    for event_type in ALERT_THRESHOLDS:
        cache_key = f"security_event:{event_type}"
        try:
            counts[event_type] = cache.get(cache_key, 0)
        except Exception:
            counts[event_type] = 0
    return counts


def _maybe_send_alert(event_type, count, threshold, log_data):
    """Send alert if threshold reached and not in cooldown."""
    # Cooldown: don't spam alerts (min 5 minutes between same alert type)
    cooldown_key = f"alert_cooldown:{event_type}"
    try:
        if cache.get(cooldown_key):
            return  # In cooldown
        cache.set(cooldown_key, True, timeout=300)  # 5 min cooldown
    except Exception:
        pass

    severity = threshold["severity"]
    message = (
        f"[{severity.upper()}] Security Alert: {event_type}\n"
        f"Count: {count} in {threshold['window']}s window\n"
        f"Details: {json.dumps(log_data, default=str)}"
    )

    logger.warning("ALERT TRIGGERED: %s", message)

    # Send webhook if configured
    webhook_url = os.environ.get("ALERT_WEBHOOK_URL", "")
    alert_enabled = os.environ.get("ALERT_ENABLED", "false").lower() == "true"

    if webhook_url and alert_enabled:
        _send_webhook_alert(webhook_url, event_type, message)


def _send_webhook_alert(webhook_url, event_type, message):
    """Send alert via webhook (Telegram, Slack, or generic)."""
    try:
        import requests
        channel = os.environ.get("ALERT_CHANNEL", "generic")

        if channel == "slack":
            payload = {"text": message}
        elif channel == "telegram":
            # Telegram expects chat_id in the URL params
            payload = {"text": message, "parse_mode": "HTML"}
        else:
            payload = {
                "event_type": event_type,
                "message": message,
                "timestamp": timezone.now().isoformat(),
            }

        resp = requests.post(webhook_url, json=payload, timeout=5)
        if resp.status_code not in (200, 201, 204):
            logger.error("Alert webhook failed: status=%d body=%s", resp.status_code, resp.text[:200])
    except Exception as e:
        logger.error("Alert webhook error: %s", e)
