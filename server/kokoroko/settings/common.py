from pathlib import Path
import os
import json
from datetime import timedelta
from celery.schedules import crontab
from django.utils.translation import gettext_lazy as _

# =============================================================================
# BASE DIRECTORY & ENVIRONMENT SETUP
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load .env only if not in production (Docker prod uses env_file)
if os.environ.get("DJANGO_ENV") != "prod":
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")

# =============================================================================
# CONFIG IMPORTS
# =============================================================================
from config.base import *
from config.azure import *
from config.email import *
from config.constants import *

# =============================================================================
# SECURITY & CORE SETTINGS
# =============================================================================

SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    raise Exception("SECRET_KEY not set. Add it to .env or set the environment variable.")

FERNET_KEY = os.environ.get("FERNET_KEY")
if not FERNET_KEY:
    raise Exception("FERNET_KEY not set. Add it to .env (use cryptography.fernet.Fernet.generate_key()).")

_allowed = os.environ.get("ALLOWED_HOSTS", "")
if _allowed:
    try:
        ALLOWED_HOSTS = json.loads(_allowed)
    except json.JSONDecodeError:
        ALLOWED_HOSTS = [h.strip() for h in _allowed.split(",") if h.strip()]
else:
    ALLOWED_HOSTS = [
        "155.117.46.249",
        "roosterrun.io",
        "www.roosterrun.io",
        "api.roosterrun.io",
        "api.kokoroko.xyz",
        "kokoroko.xyz",
        "localhost",
        "127.0.0.1",
    ]

_csrf_origins = os.environ.get("CSRF_TRUSTED_ORIGINS", "")
if _csrf_origins:
    try:
        CSRF_TRUSTED_ORIGINS = json.loads(_csrf_origins)
    except json.JSONDecodeError:
        CSRF_TRUSTED_ORIGINS = []
else:
    CSRF_TRUSTED_ORIGINS = [
        "http://155.117.46.249:8080",
        "http://155.117.46.249:8081",
        "http://155.117.46.249",
        "https://roosterrun.io",
        "https://www.roosterrun.io",
        "https://api.roosterrun.io",
        "http://roosterrun.io",
        "http://www.roosterrun.io",
        "http://api.roosterrun.io",
        "https://api.kokoroko.xyz",
        "https://kokoroko.xyz",
    ]

INTERNAL_IPS = ["127.0.0.1", "localhost"]

# =============================================================================
# REST FRAMEWORK CONFIGURATION
# =============================================================================

REST_FRAMEWORK = {
    "COERCE_DECIMAL_TO_STRING": False,
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "EXCEPTION_HANDLER": "kokoroko.error_handler.kokoroko_exception_handler",
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/minute",
        "user": "120/minute",
    },
}

# =============================================================================
# APPLICATION DEFINITION
# =============================================================================

INSTALLED_APPS = [
    "daphne",
    "material",
    "material.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "storages",
    "rest_framework",
    "django_extensions",
    "channels",
    "corsheaders",
    "apiManager",
    "base",
    "userManager",
    "wallet",
    "cockfightManager",
    "dicePlayManager",
    "lotteryManager",
    "rest_framework_simplejwt.token_blacklist",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "kokoroko.middleware.SecurityHeadersMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "kokoroko.middleware.ErrorHandlingMiddleware",
    "kokoroko.middleware.RequestLoggingMiddleware",
    "kokoroko.middleware.AdminSessionSecurityMiddleware",
]

ROOT_URLCONF = "kokoroko.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# =============================================================================
# DATABASE & WSGI/ASGI APPLICATIONS
# =============================================================================

if os.environ.get("DB_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.environ.get("DB_NAME"),
            "USER": os.environ.get("DB_USER"),
            "PASSWORD": os.environ.get("DB_PASSWORD"),
            "HOST": os.environ.get("DB_HOST"),
            "PORT": os.environ.get("DB_PORT", "3306"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

WSGI_APPLICATION = "kokoroko.wsgi.application"
ASGI_APPLICATION = "kokoroko.asgi.application"

# =============================================================================
# AUTHENTICATION & AUTHORIZATION
# =============================================================================

AUTH_USER_MODEL = "userManager.User"
AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

SIMPLE_JWT = {
    "AUTH_HEADER_TYPES": ("Bearer", "JWT",),
    "JWT_SECRET_KEY": SECRET_KEY,
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.environ.get("JWT_ACCESS_LIFETIME_MINUTES", "30"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
}

# =============================================================================
# INTERNATIONALIZATION & LOCALIZATION
# =============================================================================

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# =============================================================================
# STATIC FILES & STORAGE
# =============================================================================

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

if AZURE_ACCOUNT_NAME:
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.azure_storage.AzureStorage",
            "OPTIONS": {"timeout": 20, "expiration_secs": 10},
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
else:
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
            "OPTIONS": {"location": str(BASE_DIR / "media")},
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }

# =============================================================================
# CELERY CONFIGURATION
# =============================================================================

CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
result_backend = CELERY_BROKER_URL
timezone = "Asia/Kolkata"

CELERY_BEAT_SCHEDULE = {
    "clear-expired-otps-every-2min": {
        "task": "userManager.tasks.delete_expired_otps",
        "schedule": timedelta(minutes=2),
    },
    "poll-cockfight-api-beat": {
        "task": "cockfightManager.tasks.poll_auto_match_status",
        "schedule": timedelta(seconds=2),
    },
    "expire-subscriptions-every-day": {
        "task": "userManager.tasks.expire_subscriptions",
        "schedule": crontab(hour=0, minute=0),
    },

    "manage-scheduled-matches": {
        "task": "cockfightManager.tasks.manage_scheduled_matches",
        "schedule": timedelta(seconds=10),
    },
    "reset-payment-daily-limits": {
        "task": "wallet.tasks.reset_payment_daily_limits",
        "schedule": timedelta(minutes=5),
    },
    "manage-virtual-dice-rounds": {
        "task": "dicePlayManager.tasks.manage_virtual_dice_rounds",
        "schedule": timedelta(seconds=5),
    },
    "check-cockfight-stream-health": {
        "task": "cockfightManager.tasks.check_stream_health",
        "schedule": timedelta(seconds=15),
    },
    "run-daily-backups": {
        "task": "kokoroko.task_utils.run_scheduled_backups",
        "schedule": crontab(hour=2, minute=0),  # Daily at 2:00 AM IST
    },
    "cleanup-old-backups": {
        "task": "kokoroko.task_utils.cleanup_scheduled_backups",
        "schedule": crontab(hour=3, minute=0),  # Daily at 3:00 AM IST
    },
    "wallet-integrity-check": {
        "task": "kokoroko.task_utils.check_wallet_integrity_task",
        "schedule": crontab(hour=4, minute=0),  # Daily at 4:00 AM IST
    },
}

# =============================================================================
# CACHE CONFIGURATION (Redis — shared across all workers)
# =============================================================================

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", os.environ.get("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0").rsplit("/", 1)[0] + "/1"),
    }
}

# CHANNELS & WEBSOCKETS CONFIGURATION
# =============================================================================

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [os.environ.get("CHANNELS_REDIS_URL", "redis://127.0.0.1:6379/2")],
        },
    },
}

# =============================================================================
# CORS CONFIGURATION
# =============================================================================

CORS_ALLOW_ALL_ORIGINS = False

_PRODUCTION_CORS_ORIGINS = [
    "http://api.roosterrun.io",
    "http://roosterrun.io",
    "https://roosterrun.io",
    "https://www.roosterrun.io",
    "https://api.roosterrun.io",
    "https://kokoroko.xyz",
    "https://api.kokoroko.xyz",
    "http://155.117.46.249",
    "http://155.117.46.249:8080",
    "http://155.117.46.249:8081",
]

_DEV_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8080",
    "http://localhost:8081",
]

# Include localhost origins only in development
_cors_extra = os.environ.get("CORS_EXTRA_ORIGINS", "")
_cors_extra_list = [o.strip() for o in _cors_extra.split(",") if o.strip()] if _cors_extra else []

# DEBUG is defined in devConfig/prodConfig which import common first,
# so use globals().get() to safely check without NameError.
_debug = globals().get("DEBUG", os.environ.get("DJANGO_ENV") != "prod")

CORS_ALLOWED_ORIGINS = _PRODUCTION_CORS_ORIGINS + _cors_extra_list
if _debug:
    CORS_ALLOWED_ORIGINS += _DEV_CORS_ORIGINS
CORS_ALLOW_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
CORS_ALLOW_CREDENTIALS = True

# =============================================================================
# ADMIN INTERFACE CONFIGURATION
# =============================================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

MATERIAL_ADMIN_SITE = {
    "HEADER": _("Kokoroko"),
    "TITLE": _("Kokoroko"),
    "FAVICON": "logo.png",
    "MAIN_BG_COLOR": "#FF7700",
    "MAIN_HOVER_COLOR": "#000",
    "PROFILE_PICTURE": "logo.png",
    "PROFILE_BG": "loginBackground.png",
    "LOGIN_LOGO": "logo.png",
    "LOGOUT_BG": "loginBackground.png",
    "SHOW_THEMES": True,
    "TRAY_REVERSE": True,
    "NAVBAR_REVERSE": False,
    "SHOW_COUNTS": False,
    "APP_ICONS": {"sites": "send"},
    "MODEL_ICONS": {"site": "ac_unit"},
}


# =============================================================================
# LOGGING CONFIGURATION (Smart Error Handling Engine)
# =============================================================================

from kokoroko.logging_config import get_logging_config
LOGGING = get_logging_config()

# =============================================================================
# SECURITY HARDENING
# =============================================================================

# Prevent clickjacking
X_FRAME_OPTIONS = "DENY"

# Prevent MIME type sniffing
SECURE_CONTENT_TYPE_NOSNIFF = True

# XSS protection header
SECURE_BROWSER_XSS_FILTER = True

# Session security
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 3600 * 8  # 8 hours for admin sessions
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_SAVE_EVERY_REQUEST = True

# CSRF cookie security
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"

# DEBUG must be off in production
DEBUG = os.environ.get("DJANGO_ENV") != "prod"

# File upload limits
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
DATA_UPLOAD_MAX_NUMBER_FIELDS = 100
