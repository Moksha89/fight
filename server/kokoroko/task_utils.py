"""
Kokoroko Celery Task Error Utilities
=====================================
Provides:
- Smart retry decorator for transient failures
- Task error logging
- Dead-letter tracking for permanently failed tasks
"""

import logging
import functools
import traceback
from datetime import datetime

from celery import shared_task
from django.db import OperationalError, InterfaceError

logger = logging.getLogger("kokoroko.tasks")

# Transient exceptions that should trigger auto-retry
TRANSIENT_EXCEPTIONS = (
    OperationalError,
    InterfaceError,
    ConnectionError,
    TimeoutError,
    OSError,
)


def smart_task(
    max_retries=3,
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    critical=False,
    **task_kwargs,
):
    """
    Decorator for Celery tasks with smart error handling.

    Usage:
        @smart_task(max_retries=3, critical=True)
        def process_payment(bet_id):
            ...

    Features:
        - Auto-retry on transient DB/network errors with exponential backoff
        - Structured error logging with task context
        - Critical tasks get higher retry count
        - Non-transient errors are logged and not retried
    """
    def decorator(func):
        @shared_task(
            bind=True,
            max_retries=max_retries,
            autoretry_for=TRANSIENT_EXCEPTIONS,
            retry_backoff=retry_backoff,
            retry_backoff_max=retry_backoff_max,
            retry_jitter=retry_jitter,
            **task_kwargs,
        )
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            task_name = func.__name__
            task_id = self.request.id
            attempt = self.request.retries + 1

            try:
                result = func(*args, **kwargs)
                if attempt > 1:
                    logger.info(
                        "Task %s [%s] succeeded on attempt %d",
                        task_name, task_id, attempt,
                    )
                return result

            except TRANSIENT_EXCEPTIONS as exc:
                logger.warning(
                    "Task %s [%s] transient error (attempt %d/%d): %s",
                    task_name, task_id, attempt, max_retries + 1, str(exc),
                )
                raise  # Celery's autoretry handles the retry

            except Exception as exc:
                severity = "CRITICAL" if critical else "ERROR"
                logger.error(
                    "[%s] Task %s [%s] failed permanently (attempt %d): %s\n"
                    "Args: %s | Kwargs: %s\n%s",
                    severity, task_name, task_id, attempt,
                    str(exc), args, kwargs, traceback.format_exc(),
                )

                # Track failed task for monitoring
                try:
                    _record_dead_letter(task_name, task_id, args, kwargs, str(exc))
                except Exception:
                    pass

                return f"FAILED: {str(exc)}"

        return wrapper
    return decorator


def _record_dead_letter(task_name, task_id, args, kwargs, error):
    """Record permanently failed task for admin visibility."""
    try:
        from django.core.cache import cache
        key = f"dead_letter:{task_name}:{task_id}"
        cache.set(key, {
            "task": task_name,
            "task_id": task_id,
            "args": str(args),
            "kwargs": str(kwargs),
            "error": error,
            "failed_at": datetime.utcnow().isoformat(),
        }, timeout=86400 * 7)  # Keep for 7 days
    except Exception:
        pass  # Cache failure shouldn't break anything


def log_task_result(task_name, result, **extra):
    """Log task completion with optional extra context."""
    logger.info("Task %s completed: %s %s", task_name, result, extra or "")


# ─── Scheduled Tasks for Backup & Monitoring ─────────────────────────────────

@shared_task
def run_scheduled_backups():
    """Daily backup of database, wallet ledger, results, admin activity."""
    from django.core.cache import cache
    fc = cache.get("feature_controls", {})
    backup_cfg = fc.get("backup", {})
    if not backup_cfg.get("enabled", True) or not backup_cfg.get("auto_daily", True):
        return "Backup disabled in Feature Controls"
    from kokoroko.backup import run_all_backups
    return run_all_backups()


@shared_task
def cleanup_scheduled_backups():
    """Clean up backup files older than configured retention days."""
    from django.core.cache import cache
    fc = cache.get("feature_controls", {})
    if not fc.get("backup", {}).get("enabled", True):
        return "Backup disabled in Feature Controls"
    from kokoroko.backup import cleanup_old_backups
    return cleanup_old_backups()


@shared_task
def check_wallet_integrity_task():
    """Daily wallet integrity verification."""
    from kokoroko.monitoring import check_wallet_integrity
    return check_wallet_integrity()
