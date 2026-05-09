"""
Kokoroko Error Handling Middleware
==================================
Catches unhandled exceptions in non-DRF views (admin, static, etc.)
and adds request context for structured logging.
"""

import json
import logging
import traceback
import uuid
import time

from django.http import JsonResponse

logger = logging.getLogger("kokoroko.errors")
request_logger = logging.getLogger("kokoroko.requests")


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

        return response
