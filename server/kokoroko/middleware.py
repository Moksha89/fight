"""
Kokoroko Middleware Stack
=========================
- RequestIDMiddleware: Assigns unique request ID and X-Request-ID header (S6.2)
- ErrorHandlingMiddleware: Catches unhandled exceptions
- RequestLoggingMiddleware: Structured request logging with timing + slow request alerts (S6.2, S6.3)
- SecurityHeadersMiddleware: Adds security response headers
- AdminSessionSecurityMiddleware: Admin session timeout & IP logging
"""

import json
import logging
import traceback
import uuid
import time

from django.http import JsonResponse
from django.utils import timezone

logger = logging.getLogger("kokoroko.errors")
request_logger = logging.getLogger("kokoroko.requests")
security_logger = logging.getLogger("kokoroko.security")

# Paths to skip for detailed request logging (high-frequency, low-value)
_SKIP_LOG_PREFIXES = ("/static/", "/favicon.ico")

# Slow request thresholds (seconds)
SLOW_WARN_THRESHOLD = 1.0
SLOW_ERROR_THRESHOLD = 3.0


class RequestIDMiddleware:
    """
    Assigns a unique request ID to every request (S6.2).
    - Uses incoming X-Request-ID header if present (from reverse proxy)
    - Otherwise generates a UUID4
    - Stores on request.request_id for downstream use
    - Sets X-Request-ID response header
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.META.get("HTTP_X_REQUEST_ID") or str(uuid.uuid4())
        request.request_id = request_id
        response = self.get_response(request)
        response["X-Request-ID"] = request_id
        return response


class ErrorHandlingMiddleware:
    """
    Catches unhandled exceptions that slip past DRF's handler.
    Only catches exceptions for API endpoints (not admin/static).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            response = self.get_response(request)
            return response
        except Exception as exc:
            if request.path.startswith("/api/") or request.path.startswith("/ws/"):
                return self._handle_api_error(request, exc)
            raise

    def _handle_api_error(self, request, exc):
        error_id = str(uuid.uuid4())[:8]
        request_id = getattr(request, "request_id", "?")
        logger.error(
            "Unhandled middleware exception [%s] req=%s: %s | user=%s path=%s method=%s\n%s",
            error_id,
            request_id,
            str(exc),
            getattr(request, "user", "anonymous"),
            request.path,
            request.method,
            traceback.format_exc(),
        )
        return JsonResponse(
            {
                "success": False,
                "error": {
                    "id": error_id,
                    "code": "SYSTEM_9001",
                    "message": "Something went wrong. Please try again.",
                    "message_hi": "कुछ गलत हो गया। कृपया पुन: प्रयास करें।",
                    "severity": "high",
                    "retry_allowed": True,
                },
            },
            status=500,
        )


class RequestLoggingMiddleware:
    """
    Structured request logging with timing, request ID, user context,
    and slow request detection (S6.2 + S6.3).

    Logs warning for requests >1s, error for >3s.
    Includes request ID for correlation across services.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip static files and favicon
        if any(request.path.startswith(p) for p in _SKIP_LOG_PREFIXES):
            return self.get_response(request)

        start_time = time.time()
        response = self.get_response(request)
        duration = time.time() - start_time
        duration_ms = duration * 1000

        request_id = getattr(request, "request_id", "-")
        user = getattr(request, "user", None)
        user_str = str(user) if user and user.is_authenticated else "anonymous"
        user_id = getattr(user, "id", None) if user and user.is_authenticated else None
        client_ip = self._get_ip(request)
        status_code = response.status_code

        # Structured log data
        log_data = {
            "req_id": request_id,
            "method": request.method,
            "path": request.path[:200],
            "status": status_code,
            "duration_ms": round(duration_ms, 1),
            "user": user_str,
            "user_id": user_id,
            "ip": client_ip,
        }

        # Determine log level
        if duration >= SLOW_ERROR_THRESHOLD:
            request_logger.error(
                "SLOW REQUEST (%.1fs) %s %s %d req=%s user=%s ip=%s",
                duration, request.method, request.path, status_code,
                request_id, user_str, client_ip,
            )
        elif duration >= SLOW_WARN_THRESHOLD:
            request_logger.warning(
                "Slow request (%.1fs) %s %s %d req=%s user=%s ip=%s",
                duration, request.method, request.path, status_code,
                request_id, user_str, client_ip,
            )
        elif status_code >= 500:
            request_logger.error(
                "%s %s %d %.0fms req=%s user=%s ip=%s",
                request.method, request.path, status_code, duration_ms,
                request_id, user_str, client_ip,
            )
        elif status_code >= 400:
            request_logger.warning(
                "%s %s %d %.0fms req=%s user=%s ip=%s",
                request.method, request.path, status_code, duration_ms,
                request_id, user_str, client_ip,
            )
        else:
            # Only log API and admin requests at INFO (not every static/page request)
            if request.path.startswith(("/api/", "/ws/", "/admin", "/health")):
                request_logger.info(
                    "%s %s %d %.0fms req=%s user=%s ip=%s",
                    request.method, request.path, status_code, duration_ms,
                    request_id, user_str, client_ip,
                )

        # Add error tracking header
        if status_code >= 400 and hasattr(response, "content"):
            try:
                data = json.loads(response.content)
                error_id = data.get("error", {}).get("id")
                if error_id:
                    response["X-Error-Id"] = error_id
            except (json.JSONDecodeError, AttributeError):
                pass

        # Track metrics for monitoring dashboard
        try:
            from kokoroko.monitoring import track_metric
            track_metric("api_requests")
            if status_code >= 400:
                track_metric("api_errors", tags={"status": str(status_code)})
            if status_code >= 500:
                track_metric("api_5xx_errors")
            if duration >= SLOW_WARN_THRESHOLD:
                track_metric("slow_requests", tags={"path": request.path[:50]})
        except Exception:
            pass

        # Track security events for alerts
        if status_code == 429:
            try:
                from kokoroko.alerts import track_security_event
                track_security_event(
                    "rate_limit_spike",
                    details={"path": request.path[:100]},
                    ip=client_ip,
                )
            except Exception:
                pass

        return response

    @staticmethod
    def _get_ip(request):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "unknown")


class SecurityHeadersMiddleware:
    """
    Adds security headers to all responses:
    - Content-Security-Policy
    - X-Content-Type-Options
    - Referrer-Policy
    - Permissions-Policy
    - Cache-Control for sensitive responses
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        response["X-Content-Type-Options"] = "nosniff"
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        if request.path.startswith("/api/"):
            response["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            response["Pragma"] = "no-cache"

        if not response.get("Content-Security-Policy"):
            response["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: blob: https:; "
                "font-src 'self' data: https:; "
                "connect-src 'self' ws: wss: http: https:; "
                "frame-ancestors 'none';"
            )

        return response


class AdminSessionSecurityMiddleware:
    """
    Admin session security:
    - Log admin access with IP
    - Enforce session timeout for admin users
    - Track last activity timestamp
    """

    ADMIN_SESSION_TIMEOUT = 8 * 3600  # 8 hours

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith(("/admin", "/login", "/userManager")):
            return self.get_response(request)

        user = getattr(request, "user", None)
        if user and user.is_authenticated and user.is_staff:
            last_activity = request.session.get("admin_last_activity")
            now = timezone.now().timestamp()

            if last_activity:
                idle = now - last_activity
                if idle > self.ADMIN_SESSION_TIMEOUT:
                    from django.contrib.auth import logout
                    security_logger.warning(
                        "Admin session expired: user=%s idle=%.0fs ip=%s",
                        user, idle, self._get_ip(request),
                    )
                    logout(request)
                    from django.shortcuts import redirect
                    return redirect("/login/")

            request.session["admin_last_activity"] = now

            if not request.session.get("admin_ip_logged"):
                security_logger.info(
                    "Admin access: user=%s ip=%s path=%s",
                    user, self._get_ip(request), request.path,
                )
                request.session["admin_ip_logged"] = True

                # Track admin login as security event
                try:
                    from kokoroko.alerts import track_security_event
                    track_security_event(
                        "admin_login",
                        details={"path": request.path},
                        user_id=user.id,
                        ip=self._get_ip(request),
                    )
                except Exception:
                    pass

        return self.get_response(request)

    @staticmethod
    def _get_ip(request):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "unknown")
