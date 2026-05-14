"""
Sentry Error Tracking Integration (S6.1)

Env-based configuration — disabled until SENTRY_DSN is provided.
Scrubs sensitive data (JWT, OTP, passwords, SMS secrets, payment secrets).

Env vars:
    SENTRY_DSN              — Sentry DSN (required to enable)
    SENTRY_ENVIRONMENT      — e.g. "production" (default)
    SENTRY_TRACES_SAMPLE_RATE — 0.0-1.0 (default 0.05)
    SENTRY_SEND_DEFAULT_PII — "true" to send PII (default "false")
"""

import logging
import os

logger = logging.getLogger("kokoroko.monitoring")

# Keys to scrub from Sentry event data
SCRUB_KEYS = {
    "authorization", "token", "jwt", "password", "passwd", "secret",
    "otp", "csrfmiddlewaretoken", "csrftoken", "sessionid",
    "msg91_auth_key", "twilio_auth_token", "twilio_account_sid",
    "sentry_dsn", "fernet_key", "secret_key", "db_password",
    "razorpay_key", "razorpay_secret", "azure_account_key",
}

SCRUB_VALUE = "[Filtered]"


def _scrub_dict(data):
    """Recursively scrub sensitive keys from a dict."""
    if not isinstance(data, dict):
        return data
    cleaned = {}
    for k, v in data.items():
        if any(s in k.lower() for s in SCRUB_KEYS):
            cleaned[k] = SCRUB_VALUE
        elif isinstance(v, dict):
            cleaned[k] = _scrub_dict(v)
        elif isinstance(v, list):
            cleaned[k] = [_scrub_dict(i) if isinstance(i, dict) else i for i in v]
        else:
            cleaned[k] = v
    return cleaned


def _before_send(event, hint):
    """Sentry before_send hook — scrub sensitive data."""
    # Scrub request data
    request_data = event.get("request", {})
    if "headers" in request_data:
        request_data["headers"] = _scrub_dict(request_data["headers"])
    if "data" in request_data:
        if isinstance(request_data["data"], dict):
            request_data["data"] = _scrub_dict(request_data["data"])
        elif isinstance(request_data["data"], str):
            # Don't send raw POST body — may contain secrets
            for key in SCRUB_KEYS:
                if key in request_data["data"].lower():
                    request_data["data"] = SCRUB_VALUE
                    break
    if "cookies" in request_data:
        request_data["cookies"] = SCRUB_VALUE
    if "query_string" in request_data:
        qs = request_data["query_string"]
        if isinstance(qs, str) and "token=" in qs.lower():
            request_data["query_string"] = "[Filtered]"
    # Scrub breadcrumb data
    for bc in event.get("breadcrumbs", {}).get("values", []):
        if "data" in bc and isinstance(bc["data"], dict):
            bc["data"] = _scrub_dict(bc["data"])
    return event


def _before_send_transaction(event, hint):
    """Scrub sensitive data from transaction events too."""
    return _before_send(event, hint)


def init_sentry():
    """Initialize Sentry SDK if SENTRY_DSN is set. Safe no-op otherwise."""
    dsn = os.environ.get("SENTRY_DSN", "")
    if not dsn:
        logger.info("Sentry disabled — SENTRY_DSN not set")
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.redis import RedisIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration

        environment = os.environ.get("SENTRY_ENVIRONMENT", "production")
        traces_rate = float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.05"))
        send_pii = os.environ.get("SENTRY_SEND_DEFAULT_PII", "false").lower() == "true"

        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            traces_sample_rate=traces_rate,
            send_default_pii=send_pii,
            before_send=_before_send,
            before_send_transaction=_before_send_transaction,
            integrations=[
                DjangoIntegration(
                    transaction_style="url",
                    middleware_spans=True,
                ),
                CeleryIntegration(monitor_beat_tasks=True),
                RedisIntegration(),
                LoggingIntegration(
                    level=logging.WARNING,
                    event_level=logging.ERROR,
                ),
            ],
            # Filter out health check transactions
            traces_sampler=_traces_sampler,
        )
        logger.info("Sentry initialized: env=%s traces=%.2f", environment, traces_rate)
        return True

    except ImportError:
        logger.warning("sentry-sdk not installed — Sentry disabled")
        return False
    except Exception as e:
        logger.error("Sentry init failed: %s", e)
        return False


def _traces_sampler(sampling_context):
    """Custom sampler — skip health check and static file traces."""
    try:
        path = sampling_context.get("wsgi_environ", {}).get("PATH_INFO", "")
        if path in ("/health/", "/favicon.ico") or path.startswith("/static/"):
            return 0.0
    except Exception:
        pass
    return float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.05"))
