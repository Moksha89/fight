from .common import *

DEBUG = False

# =============================================================================
# PROXY & SSL SETTINGS
# =============================================================================

RATELIMIT_IP_META_KEY = "HTTP_X_FORWARDED_FOR"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Nginx handles HTTP→HTTPS redirect for public domains.
# Admin now served over HTTPS at api.roosterrun.io/admin/ (S5).
# SECURE_SSL_REDIRECT left off because port 8081 (web play) still proxies
# HTTP API calls. Nginx handles the redirect for port 8080 instead.

# =============================================================================
# COOKIE SECURITY (S5: enabled after admin moved to HTTPS)
# =============================================================================

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# =============================================================================
# CORS — HTTPS-only origins (S5: removed HTTP admin origins)
# =============================================================================

CORS_ALLOWED_ORIGINS = [
    "https://roosterrun.io",
    "https://www.roosterrun.io",
    "https://api.roosterrun.io",
    "https://kokoroko.xyz",
    "https://api.kokoroko.xyz",
]

# Allow adding extra origins via env var for internal testing
_cors_extra = os.environ.get("CORS_EXTRA_ORIGINS", "")
if _cors_extra:
    CORS_ALLOWED_ORIGINS += [o.strip() for o in _cors_extra.split(",") if o.strip()]

CSRF_TRUSTED_ORIGINS = [
    "https://roosterrun.io",
    "https://www.roosterrun.io",
    "https://api.roosterrun.io",
    "https://kokoroko.xyz",
    "https://api.kokoroko.xyz",
]

# Allow adding extra CSRF origins via env var
_csrf_extra = os.environ.get("CSRF_EXTRA_ORIGINS", "")
if _csrf_extra:
    CSRF_TRUSTED_ORIGINS += [o.strip() for o in _csrf_extra.split(",") if o.strip()]
