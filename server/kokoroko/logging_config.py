"""
Kokoroko Logging Configuration
===============================
Structured logging for all backend components.
"""

import os

LOG_DIR = os.environ.get("LOG_DIR", "/var/log/kokoroko")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} {message}",
            "style": "{",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "simple": {
            "format": "{levelname} {name}: {message}",
            "style": "{",
        },
    },
    "filters": {
        "require_debug_false": {
            "()": "django.utils.log.RequireDebugFalse",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "error_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(LOG_DIR, "errors.log"),
            "maxBytes": 10 * 1024 * 1024,  # 10 MB
            "backupCount": 5,
            "formatter": "verbose",
            "level": "WARNING",
        },
        "request_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(LOG_DIR, "requests.log"),
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 3,
            "formatter": "verbose",
        },
        "task_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(LOG_DIR, "tasks.log"),
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 3,
            "formatter": "verbose",
        },
    },
    "loggers": {
        "kokoroko.errors": {
            "handlers": ["console", "error_file"],
            "level": "WARNING",
            "propagate": False,
        },
        "kokoroko.requests": {
            "handlers": ["console", "request_file"],
            "level": "INFO",
            "propagate": False,
        },
        "kokoroko.tasks": {
            "handlers": ["console", "task_file"],
            "level": "INFO",
            "propagate": False,
        },
        "django": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": True,
        },
        "django.request": {
            "handlers": ["console", "error_file"],
            "level": "WARNING",
            "propagate": False,
        },
        "celery": {
            "handlers": ["console", "task_file"],
            "level": "WARNING",
            "propagate": False,
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}


def get_logging_config():
    """Get logging config, creating log dir if needed."""
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
    except OSError:
        # Fallback: disable file handlers if dir can't be created
        for handler_name in ["error_file", "request_file", "task_file"]:
            LOGGING["handlers"][handler_name] = {
                "class": "logging.StreamHandler",
                "formatter": "verbose",
            }
    return LOGGING
