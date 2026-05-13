from .common import *

DEBUG = False

# =============================================================================
# PROXY & SSL SETTINGS
# =============================================================================

RATELIMIT_IP_META_KEY = "HTTP_X_FORWARDED_FOR"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# NOTE: SECURE_SSL_REDIRECT is NOT enabled because the admin panel on port 8080
# uses HTTP. Django cannot distinguish which port the request came through, so
# enabling it would cause a redirect loop for admin users on :8080.
# Nginx already handles HTTP→HTTPS redirect for public roosterrun.io domains.
# SECURE_SSL_REDIRECT = False  (Django default)

# =============================================================================
# COOKIE SECURITY
# =============================================================================

# NOTE: SESSION_COOKIE_SECURE and CSRF_COOKIE_SECURE are NOT enabled yet
# because the admin panel is served over HTTP on port 8080. Setting these to
# True would prevent session/CSRF cookies from being sent over HTTP, breaking
# admin login entirely.
#
# TODO (S2+): Move admin panel to HTTPS (e.g., on port 443 at /admin/),
# then enable these:
#   SESSION_COOKIE_SECURE = True
#   CSRF_COOKIE_SECURE = True
#
# For now, the API uses JWT (not cookies) and is HTTPS-only via Nginx,
# so cookie security is less critical for the API surface.

# =============================================================================
# CORS — production override: remove plain HTTP domain origins
# (http://roosterrun.io, http://api.roosterrun.io → always redirect to HTTPS)
# IP-direct HTTP origins kept for admin/web play on ports 8080/8081
# =============================================================================

CORS_ALLOWED_ORIGINS = [
    "https://roosterrun.io",
    "https://www.roosterrun.io",
    "https://api.roosterrun.io",
    "https://kokoroko.xyz",
    "https://api.kokoroko.xyz",
    # IP-direct HTTP origins for admin (8080) and web play (8081)
    # These stay until admin/web are moved to HTTPS-only
    "http://155.117.46.249",
    "http://155.117.46.249:8080",
    "http://155.117.46.249:8081",
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
    # Admin panel on HTTP (port 8080) — required until admin moves to HTTPS
    "http://155.117.46.249:8080",
    "http://155.117.46.249",
]

# Allow adding extra CSRF origins via env var
_csrf_extra = os.environ.get("CSRF_EXTRA_ORIGINS", "")
if _csrf_extra:
    CSRF_TRUSTED_ORIGINS += [o.strip() for o in _csrf_extra.split(",") if o.strip()]
