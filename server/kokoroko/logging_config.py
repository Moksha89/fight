"""
Kokoroko Logging Configuration (S6 Enhanced)
==============================================
Structured logging for all backend components.
Includes security event logger, monitoring logger, and JSON formatter option.

Env vars:
    LOG_DIR           — Log directory (default: /var/log/kokoroko)
    LOG_FORMAT        — "json" for structured JSON output (default: verbose text)
"""

import os

LOG_DIR = os.environ.get("LOG_DIR", "/var/log/kokoroko")
LOG_FORMAT = os.environ.get("LOG_FORMAT", "verbose")

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
        "json": {
            "()": "kokoroko.logging_config.JsonFormatter",
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
            "formatter": LOG_FORMAT if LOG_FORMAT in ("verbose", "json") else "verbose",
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
        "security_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(LOG_DIR, "security.log"),
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "verbose",
            "level": "INFO",
        },
        "monitoring_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": os.path.join(LOG_DIR, "monitoring.log"),
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
        "kokoroko.security": {
            "handlers": ["console", "security_file"],
            "level": "INFO",
            "propagate": False,
        },
        "kokoroko.monitoring": {
            "handlers": ["console", "monitoring_file"],
            "level": "INFO",
            "propagate": False,
        },
        "kokoroko.backup": {
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


class JsonFormatter:
    """JSON log formatter for structured log aggregation."""

    def __init__(self, **kwargs):
        import json
        self.json = json

    def format(self, record):
        import traceback as tb
        log_entry = {
            "ts": record.created,
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = tb.format_exception(*record.exc_info)
        return self.json.dumps(log_entry, default=str)


def get_logging_config():
    """Get logging config, creating log dir if needed."""
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
    except OSError:
        # Fallback: disable file handlers if dir can't be created
        for handler_name in list(LOGGING["handlers"].keys()):
            if handler_name != "console":
                LOGGING["handlers"][handler_name] = {
                    "class": "logging.StreamHandler",
                    "formatter": "verbose",
                }
    return LOGGING
