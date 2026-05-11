"""
Kokoroko Smart Error Handling Engine — Backend Core
====================================================
Centralized DRF exception handler with:
- Structured error response format
- Error code taxonomy (AUTH, WALLET, BET, GAME, SYSTEM)
- Severity classification
- Request context logging
- Safe production error messages
"""

import logging
import traceback
import uuid
from datetime import datetime

from django.core.exceptions import (
    PermissionDenied as DjangoPermissionDenied,
    ValidationError as DjangoValidationError,
    ObjectDoesNotExist,
)
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    MethodNotAllowed,
    NotAuthenticated,
    NotFound,
    ParseError,
    PermissionDenied,
    Throttled,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger("kokoroko.errors")


# ─── Error Code Taxonomy ─────────────────────────────────────────────────────

class ErrorCode:
    # Authentication & Authorization (1xxx)
    AUTH_TOKEN_EXPIRED = "AUTH_1001"
    AUTH_TOKEN_INVALID = "AUTH_1002"
    AUTH_NOT_AUTHENTICATED = "AUTH_1003"
    AUTH_PERMISSION_DENIED = "AUTH_1004"
    AUTH_OTP_INVALID = "AUTH_1005"
    AUTH_OTP_EXPIRED = "AUTH_1006"
    AUTH_ACCOUNT_DISABLED = "AUTH_1007"
    AUTH_SESSION_EXPIRED = "AUTH_1008"

    # Wallet & Payments (2xxx)
    WALLET_INSUFFICIENT_BALANCE = "WALLET_2001"
    WALLET_NOT_FOUND = "WALLET_2002"
    WALLET_DEPOSIT_DUPLICATE = "WALLET_2003"
    WALLET_DEPOSIT_MIN_AMOUNT = "WALLET_2004"
    WALLET_UTR_INVALID = "WALLET_2005"
    WALLET_UTR_DUPLICATE = "WALLET_2006"
    WALLET_WITHDRAWAL_LIMIT = "WALLET_2007"
    WALLET_PAYMENT_METHOD_UNAVAILABLE = "WALLET_2008"
    WALLET_DEPOSIT_ACTIVE = "WALLET_2009"
    WALLET_WITHDRAWAL_ACTIVE = "WALLET_2010"
    WALLET_TRANSACTION_FAILED = "WALLET_2011"

    # Betting (3xxx)
    BET_INSUFFICIENT_BALANCE = "BET_3001"
    BET_MATCH_NOT_FOUND = "BET_3002"
    BET_BETTING_CLOSED = "BET_3003"
    BET_INVALID_AMOUNT = "BET_3004"
    BET_INVALID_SELECTION = "BET_3005"
    BET_ALREADY_PLACED = "BET_3006"
    BET_MATCH_EXPIRED = "BET_3007"
    BET_LIMIT_EXCEEDED = "BET_3008"
    BET_SETTLEMENT_FAILED = "BET_3009"

    # Game State (4xxx)
    GAME_MATCH_NOT_FOUND = "GAME_4001"
    GAME_NOT_LIVE = "GAME_4002"
    GAME_ALREADY_SETTLED = "GAME_4003"
    GAME_INVALID_PHASE = "GAME_4004"
    GAME_BOARD_NOT_FOUND = "GAME_4005"
    GAME_BOARD_INACTIVE = "GAME_4006"
    GAME_NOT_VIRTUAL = "GAME_4007"
    GAME_ACTIVE_MATCH_EXISTS = "GAME_4008"
    GAME_STREAM_UNAVAILABLE = "GAME_4009"

    # Validation (5xxx)
    VALIDATION_REQUIRED_FIELD = "VALIDATION_5001"
    VALIDATION_INVALID_FORMAT = "VALIDATION_5002"
    VALIDATION_INVALID_VALUE = "VALIDATION_5003"
    VALIDATION_DUPLICATE = "VALIDATION_5004"

    # System (9xxx)
    SYSTEM_INTERNAL_ERROR = "SYSTEM_9001"
    SYSTEM_SERVICE_UNAVAILABLE = "SYSTEM_9002"
    SYSTEM_RATE_LIMITED = "SYSTEM_9003"
    SYSTEM_METHOD_NOT_ALLOWED = "SYSTEM_9004"
    SYSTEM_NOT_FOUND = "SYSTEM_9005"
    SYSTEM_MAINTENANCE = "SYSTEM_9006"
    SYSTEM_DATABASE_ERROR = "SYSTEM_9007"
    SYSTEM_WEBSOCKET_ERROR = "SYSTEM_9008"
    SYSTEM_TASK_FAILED = "SYSTEM_9009"


# ─── Severity Levels ─────────────────────────────────────────────────────────

class Severity:
    LOW = "low"          # User can retry, not critical
    MEDIUM = "medium"    # Needs attention, may affect UX
    HIGH = "high"        # Critical — money/game state affected
    CRITICAL = "critical"  # System-level failure


# ─── Error Messages (English + Hindi) ────────────────────────────────────────

ERROR_MESSAGES = {
    ErrorCode.AUTH_TOKEN_EXPIRED: {
        "en": "Your session has expired. Please login again.",
        "hi": "आपका सत्र समाप्त हो गया है। कृपया फिर से लॉगिन करें।",
    },
    ErrorCode.AUTH_TOKEN_INVALID: {
        "en": "Invalid authentication token.",
        "hi": "अमान्य प्रमाणीकरण टोकन।",
    },
    ErrorCode.AUTH_NOT_AUTHENTICATED: {
        "en": "Please login to continue.",
        "hi": "जारी रखने के लिए कृपया लॉगिन करें।",
    },
    ErrorCode.AUTH_PERMISSION_DENIED: {
        "en": "You don't have permission to perform this action.",
        "hi": "आपको यह कार्रवाई करने की अनुमति नहीं है।",
    },
    ErrorCode.WALLET_INSUFFICIENT_BALANCE: {
        "en": "Insufficient wallet balance.",
        "hi": "वॉलेट में पर्याप्त शेष नहीं है।",
    },
    ErrorCode.WALLET_NOT_FOUND: {
        "en": "Wallet not found.",
        "hi": "वॉलेट नहीं मिला।",
    },
    ErrorCode.WALLET_DEPOSIT_DUPLICATE: {
        "en": "You already have an active deposit request.",
        "hi": "आपका पहले से एक जमा अनुरोध सक्रिय है।",
    },
    ErrorCode.WALLET_DEPOSIT_MIN_AMOUNT: {
        "en": "Deposit amount is below the minimum required.",
        "hi": "जमा राशि न्यूनतम आवश्यक से कम है।",
    },
    ErrorCode.WALLET_UTR_INVALID: {
        "en": "UTR ID must contain only numbers.",
        "hi": "UTR ID में केवल संख्याएं होनी चाहिए।",
    },
    ErrorCode.WALLET_UTR_DUPLICATE: {
        "en": "This UTR ID is already linked to another user.",
        "hi": "यह UTR ID पहले से किसी अन्य उपयोगकर्ता से जुड़ी है।",
    },
    ErrorCode.BET_INSUFFICIENT_BALANCE: {
        "en": "Insufficient balance to place this bet.",
        "hi": "यह दांव लगाने के लिए पर्याप्त शेष नहीं है।",
    },
    ErrorCode.BET_MATCH_NOT_FOUND: {
        "en": "Match not found or has ended.",
        "hi": "मैच नहीं मिला या समाप्त हो गया है।",
    },
    ErrorCode.BET_BETTING_CLOSED: {
        "en": "Betting is closed for this match.",
        "hi": "इस मैच के लिए सट्टेबाज़ी बंद है।",
    },
    ErrorCode.BET_INVALID_AMOUNT: {
        "en": "Invalid bet amount.",
        "hi": "अमान्य दांव राशि।",
    },
    ErrorCode.BET_INVALID_SELECTION: {
        "en": "Invalid bet selection.",
        "hi": "अमान्य दांव चयन।",
    },
    ErrorCode.GAME_MATCH_NOT_FOUND: {
        "en": "Game not found.",
        "hi": "गेम नहीं मिला।",
    },
    ErrorCode.GAME_NOT_LIVE: {
        "en": "This game is not currently live.",
        "hi": "यह गेम वर्तमान में लाइव नहीं है।",
    },
    ErrorCode.GAME_ALREADY_SETTLED: {
        "en": "This game has already been settled.",
        "hi": "इस गेम का निपटान पहले ही हो चुका है।",
    },
    ErrorCode.SYSTEM_INTERNAL_ERROR: {
        "en": "Something went wrong. Please try again.",
        "hi": "कुछ गलत हो गया। कृपया पुन: प्रयास करें।",
    },
    ErrorCode.SYSTEM_SERVICE_UNAVAILABLE: {
        "en": "Service temporarily unavailable. Please try again later.",
        "hi": "सेवा अस्थायी रूप से अनुपलब्ध है। कृपया बाद में पुन: प्रयास करें।",
    },
    ErrorCode.SYSTEM_RATE_LIMITED: {
        "en": "Too many requests. Please wait and try again.",
        "hi": "बहुत अधिक अनुरोध। कृपया प्रतीक्षा करें और पुन: प्रयास करें।",
    },
    ErrorCode.SYSTEM_METHOD_NOT_ALLOWED: {
        "en": "This action is not allowed.",
        "hi": "यह कार्रवाई अनुमत नहीं है।",
    },
    ErrorCode.SYSTEM_NOT_FOUND: {
        "en": "The requested resource was not found.",
        "hi": "अनुरोधित संसाधन नहीं मिला।",
    },
    ErrorCode.VALIDATION_REQUIRED_FIELD: {
        "en": "Required field is missing.",
        "hi": "आवश्यक फ़ील्ड गायब है।",
    },
    ErrorCode.VALIDATION_INVALID_FORMAT: {
        "en": "Invalid data format.",
        "hi": "अमान्य डेटा प्रारूप।",
    },
}


def get_error_message(code, lang="en"):
    """Get localized error message for an error code."""
    msgs = ERROR_MESSAGES.get(code, {})
    return msgs.get(lang, msgs.get("en", "An error occurred."))


# ─── Structured Error Response Builder ────────────────────────────────────────

def build_error_response(
    code,
    message=None,
    http_status=status.HTTP_400_BAD_REQUEST,
    details=None,
    severity=Severity.MEDIUM,
    retry_allowed=True,
    field_errors=None,
):
    """Build a structured error response."""
    error_id = str(uuid.uuid4())[:8]

    body = {
        "success": False,
        "error": {
            "id": error_id,
            "code": code,
            "message": message or get_error_message(code),
            "message_hi": get_error_message(code, "hi"),
            "severity": severity,
            "retry_allowed": retry_allowed,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        },
    }

    if details:
        body["error"]["details"] = details
    if field_errors:
        body["error"]["field_errors"] = field_errors

    return Response(body, status=http_status)


# ─── Custom App Exception ────────────────────────────────────────────────────

class KokorokoError(APIException):
    """Custom exception with error code support."""
    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, code, message=None, http_status=None, details=None, severity=Severity.MEDIUM):
        self.error_code = code
        self.error_message = message or get_error_message(code)
        self.error_severity = severity
        self.error_details = details
        if http_status:
            self.status_code = http_status
        super().__init__(detail=self.error_message)


# ─── DRF Exception Handler ──────────────────────────────────────────────────

def kokoroko_exception_handler(exc, context):
    """
    Central exception handler for all DRF views.
    Converts every exception into a structured error response.
    """
    request = context.get("request")
    view = context.get("view")

    # Build log context
    log_ctx = {
        "user": str(getattr(request, "user", "anonymous")),
        "method": getattr(request, "method", "?"),
        "path": getattr(request, "path", "?"),
        "view": str(view.__class__.__name__) if view else "?",
    }

    # Handle our custom KokorokoError
    if isinstance(exc, KokorokoError):
        logger.warning(
            "KokorokoError [%s]: %s | %s",
            exc.error_code, exc.error_message, log_ctx,
        )
        return build_error_response(
            code=exc.error_code,
            message=exc.error_message,
            http_status=exc.status_code,
            details=exc.error_details,
            severity=exc.error_severity,
        )

    # Handle DRF ValidationError
    if isinstance(exc, ValidationError):
        field_errors = {}
        details_list = []
        if isinstance(exc.detail, dict):
            for field, errors in exc.detail.items():
                if isinstance(errors, list):
                    field_errors[field] = [str(e) for e in errors]
                    details_list.extend([str(e) for e in errors])
                else:
                    field_errors[field] = [str(errors)]
                    details_list.append(str(errors))
        elif isinstance(exc.detail, list):
            details_list = [str(e) for e in exc.detail]
        else:
            details_list = [str(exc.detail)]

        message = details_list[0] if details_list else "Validation error."

        logger.info("ValidationError: %s | %s", details_list, log_ctx)
        return build_error_response(
            code=ErrorCode.VALIDATION_INVALID_VALUE,
            message=message,
            http_status=status.HTTP_400_BAD_REQUEST,
            details=details_list if len(details_list) > 1 else None,
            severity=Severity.LOW,
            field_errors=field_errors or None,
        )

    # Handle DRF AuthenticationFailed
    if isinstance(exc, AuthenticationFailed):
        logger.info("AuthenticationFailed: %s | %s", exc.detail, log_ctx)
        return build_error_response(
            code=ErrorCode.AUTH_TOKEN_INVALID,
            http_status=status.HTTP_401_UNAUTHORIZED,
            severity=Severity.MEDIUM,
            retry_allowed=False,
        )

    # Handle DRF NotAuthenticated
    if isinstance(exc, NotAuthenticated):
        logger.info("NotAuthenticated | %s", log_ctx)
        return build_error_response(
            code=ErrorCode.AUTH_NOT_AUTHENTICATED,
            http_status=status.HTTP_401_UNAUTHORIZED,
            severity=Severity.MEDIUM,
            retry_allowed=False,
        )

    # Handle PermissionDenied
    if isinstance(exc, (PermissionDenied, DjangoPermissionDenied)):
        logger.warning("PermissionDenied | %s", log_ctx)
        return build_error_response(
            code=ErrorCode.AUTH_PERMISSION_DENIED,
            http_status=status.HTTP_403_FORBIDDEN,
            severity=Severity.MEDIUM,
            retry_allowed=False,
        )

    # Handle NotFound / Http404
    if isinstance(exc, (NotFound, Http404, ObjectDoesNotExist)):
        logger.info("NotFound: %s | %s", str(exc), log_ctx)
        return build_error_response(
            code=ErrorCode.SYSTEM_NOT_FOUND,
            http_status=status.HTTP_404_NOT_FOUND,
            severity=Severity.LOW,
        )

    # Handle MethodNotAllowed
    if isinstance(exc, MethodNotAllowed):
        return build_error_response(
            code=ErrorCode.SYSTEM_METHOD_NOT_ALLOWED,
            http_status=status.HTTP_405_METHOD_NOT_ALLOWED,
            severity=Severity.LOW,
            retry_allowed=False,
        )

    # Handle Throttled
    if isinstance(exc, Throttled):
        return build_error_response(
            code=ErrorCode.SYSTEM_RATE_LIMITED,
            message=f"Too many requests. Retry after {exc.wait} seconds.",
            http_status=status.HTTP_429_TOO_MANY_REQUESTS,
            details={"retry_after_seconds": exc.wait},
            severity=Severity.LOW,
        )

    # Handle Django ValidationError
    if isinstance(exc, DjangoValidationError):
        messages = exc.messages if hasattr(exc, "messages") else [str(exc)]
        logger.info("DjangoValidationError: %s | %s", messages, log_ctx)
        return build_error_response(
            code=ErrorCode.VALIDATION_INVALID_VALUE,
            message=messages[0] if messages else "Validation error.",
            http_status=status.HTTP_400_BAD_REQUEST,
            details=messages if len(messages) > 1 else None,
            severity=Severity.LOW,
        )

    # Handle any other APIException
    if isinstance(exc, APIException):
        logger.warning("APIException [%s]: %s | %s", exc.status_code, exc.detail, log_ctx)
        return build_error_response(
            code=ErrorCode.SYSTEM_INTERNAL_ERROR,
            message=str(exc.detail),
            http_status=exc.status_code,
            severity=Severity.MEDIUM,
        )

    # Unhandled exception — log full traceback, return safe response
    error_id = str(uuid.uuid4())[:8]
    logger.error(
        "Unhandled exception [%s]: %s\n%s | %s",
        error_id, str(exc), traceback.format_exc(), log_ctx,
    )
    return build_error_response(
        code=ErrorCode.SYSTEM_INTERNAL_ERROR,
        message="Something went wrong. Please try again.",
        http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        details={"error_id": error_id},
        severity=Severity.HIGH,
    )
