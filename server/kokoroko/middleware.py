"""
Kokoroko Middleware Stack
=========================
- ErrorHandlingMiddleware: Catches unhandled exceptions
- RequestLoggingMiddleware: Logs API requests
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
        logger.error(
            "Unhandled middleware exception [%s]: %s | user=%s path=%s method=%s\n%s",
            error_id,
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
    Logs all API requests with timing, status code, and user context.
    Useful for debugging and monitoring.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not (request.path.startswith("/api/") or request.path.startswith("/ws/")):
            return self.get_response(request)

        start_time = time.time()
        response = self.get_response(request)
        duration_ms = (time.time() - start_time) * 1000

        user = getattr(request, "user", None)
        user_str = str(user) if user and user.is_authenticated else "anonymous"

        log_level = logging.WARNING if response.status_code >= 400 else logging.INFO
        request_logger.log(
            log_level,
            "%s %s %d %.0fms user=%s",
            request.method,
            request.path,
            response.status_code,
            duration_ms,
            user_str,
        )

        # Add error tracking header
        if response.status_code >= 400 and hasattr(response, "content"):
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
            if response.status_code >= 400:
                track_metric("api_errors", tags={"status": str(response.status_code)})
            if response.status_code >= 500:
                track_metric("api_5xx_errors")
            if duration_ms > 2000:
                track_metric("slow_requests", tags={"path": request.path[:50]})
        except Exception:
            pass

        return response


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

        return self.get_response(request)

    @staticmethod
    def _get_ip(request):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "unknown")
