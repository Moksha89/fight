"""
Monitoring Health System (S6) — Comprehensive health checks for all subsystems.

Checks: Database, Redis, Celery, Disk, Media, FFmpeg, Backups, MySQL status.
Used by /health/ (public) and /admin-api/health/ (detailed admin view).
"""

import logging
import os
import shutil
import subprocess
import time
from datetime import datetime, timedelta

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger("kokoroko.monitoring")


# ─── Individual Health Checks ────────────────────────────────────────────────

def check_database():
    """Verify MySQL database is reachable and measure latency."""
    try:
        from django.db import connection
        start = time.time()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        latency_ms = round((time.time() - start) * 1000, 1)
        return {"status": "ok", "latency_ms": latency_ms}
    except Exception as e:
        logger.error("Database health check failed: %s", e)
        return {"status": "error", "error": str(e)}


def check_redis_cache():
    """Verify Django cache (Redis DB 1) is reachable."""
    try:
        start = time.time()
        test_key = "_health_check_cache_"
        cache.set(test_key, "ok", 10)
        result = cache.get(test_key)
        cache.delete(test_key)
        latency_ms = round((time.time() - start) * 1000, 1)
        return {
            "status": "ok" if result == "ok" else "degraded",
            "latency_ms": latency_ms,
        }
    except Exception as e:
        logger.error("Redis cache health check failed: %s", e)
        return {"status": "error", "error": str(e)}


def check_redis_detailed():
    """Get Redis memory, clients, and key stats."""
    try:
        import redis as redis_lib
        broker_url = getattr(settings, "CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
        parts = broker_url.replace("redis://", "").split("/")
        host_port = parts[0].split(":")
        host = host_port[0] if host_port[0] else "127.0.0.1"
        port = int(host_port[1]) if len(host_port) > 1 else 6379
        r = redis_lib.Redis(host=host, port=port, db=0, socket_timeout=3)
        info = r.info()
        return {
            "status": "ok",
            "used_memory_human": info.get("used_memory_human", "?"),
            "used_memory_peak_human": info.get("used_memory_peak_human", "?"),
            "connected_clients": info.get("connected_clients", 0),
            "blocked_clients": info.get("blocked_clients", 0),
            "total_connections_received": info.get("total_connections_received", 0),
            "keyspace_hits": info.get("keyspace_hits", 0),
            "keyspace_misses": info.get("keyspace_misses", 0),
            "uptime_seconds": info.get("uptime_in_seconds", 0),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def check_redis_channels():
    """Verify Redis channels layer (DB 2) is reachable."""
    try:
        import redis as redis_lib
        channels_url = getattr(settings, "CHANNEL_LAYERS", {}).get(
            "default", {}
        ).get("CONFIG", {}).get("hosts", ["redis://127.0.0.1:6379/2"])[0]
        if isinstance(channels_url, str):
            parts = channels_url.replace("redis://", "").split("/")
            host_port = parts[0].split(":")
            host = host_port[0] if host_port[0] else "127.0.0.1"
            port = int(host_port[1]) if len(host_port) > 1 else 6379
            db = int(parts[1]) if len(parts) > 1 else 2
        else:
            host, port, db = "127.0.0.1", 6379, 2
        r = redis_lib.Redis(host=host, port=port, db=db, socket_timeout=3)
        r.ping()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def check_celery():
    """Check if Celery workers are responding."""
    try:
        from celery import current_app
        inspector = current_app.control.inspect(timeout=3)
        active = inspector.active()
        if active:
            worker_names = list(active.keys())
            active_tasks = sum(len(tasks) for tasks in active.values())
            return {
                "status": "ok",
                "workers": len(worker_names),
                "worker_names": worker_names,
                "active_tasks": active_tasks,
            }
        return {"status": "warning", "workers": 0, "message": "No active workers"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def check_celery_beat():
    """Check if Celery beat is alive by checking recent task schedule."""
    try:
        from celery import current_app
        inspector = current_app.control.inspect(timeout=3)
        scheduled = inspector.scheduled()
        if scheduled:
            total = sum(len(tasks) for tasks in scheduled.values())
            return {"status": "ok", "scheduled_tasks": total}
        # Beat might be alive but no scheduled tasks pending
        return {"status": "ok", "scheduled_tasks": 0, "message": "No pending scheduled tasks"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def check_celery_queues():
    """Get Celery queue stats."""
    try:
        from celery import current_app
        inspector = current_app.control.inspect(timeout=3)
        reserved = inspector.reserved()
        active = inspector.active()
        result = {
            "status": "ok",
            "reserved_tasks": 0,
            "active_tasks": 0,
        }
        if reserved:
            result["reserved_tasks"] = sum(len(t) for t in reserved.values())
        if active:
            result["active_tasks"] = sum(len(t) for t in active.values())
        return result
    except Exception as e:
        return {"status": "error", "error": str(e)}


def check_disk_space():
    """Check disk space on the application volume."""
    try:
        usage = shutil.disk_usage("/")
        total_gb = round(usage.total / (1024**3), 1)
        used_gb = round(usage.used / (1024**3), 1)
        free_gb = round(usage.free / (1024**3), 1)
        pct_used = round((usage.used / usage.total) * 100, 1)
        status = "ok"
        if pct_used > 90:
            status = "error"
        elif pct_used > 80:
            status = "warning"
        return {
            "status": status,
            "total_gb": total_gb,
            "used_gb": used_gb,
            "free_gb": free_gb,
            "percent_used": pct_used,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def check_media_directory():
    """Check if media directory exists and is writable."""
    try:
        media_root = str(getattr(settings, "MEDIA_ROOT", "/server/media"))
        exists = os.path.isdir(media_root)
        writable = os.access(media_root, os.W_OK) if exists else False
        file_count = 0
        total_size = 0
        if exists:
            for dirpath, dirnames, filenames in os.walk(media_root):
                file_count += len(filenames)
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    try:
                        total_size += os.path.getsize(fp)
                    except OSError:
                        pass
        size_mb = round(total_size / (1024 * 1024), 1)
        status = "ok" if exists and writable else "error"
        return {
            "status": status,
            "exists": exists,
            "writable": writable,
            "file_count": file_count,
            "size_mb": size_mb,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def check_ffmpeg():
    """Check if FFmpeg is installed and accessible."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            version_line = result.stdout.split("\n")[0] if result.stdout else "unknown"
            return {"status": "ok", "version": version_line}
        return {"status": "error", "error": f"exit code {result.returncode}"}
    except FileNotFoundError:
        return {"status": "error", "error": "ffmpeg not found in PATH"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def check_mysql_status():
    """Get MySQL connection and performance stats."""
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            result = {}
            # Max connections
            cursor.execute("SHOW VARIABLES LIKE 'max_connections'")
            row = cursor.fetchone()
            result["max_connections"] = int(row[1]) if row else 0
            # Current connections
            cursor.execute("SHOW STATUS LIKE 'Threads_connected'")
            row = cursor.fetchone()
            result["current_connections"] = int(row[1]) if row else 0
            # Slow query log
            cursor.execute("SHOW VARIABLES LIKE 'slow_query_log'")
            row = cursor.fetchone()
            result["slow_query_log"] = row[1] if row else "OFF"
            # Long query time
            cursor.execute("SHOW VARIABLES LIKE 'long_query_time'")
            row = cursor.fetchone()
            result["long_query_time"] = row[1] if row else "?"
            # Table locks waited
            cursor.execute("SHOW STATUS LIKE 'Table_locks_waited'")
            row = cursor.fetchone()
            result["table_locks_waited"] = int(row[1]) if row else 0
            # Slow queries count
            cursor.execute("SHOW STATUS LIKE 'Slow_queries'")
            row = cursor.fetchone()
            result["slow_queries_total"] = int(row[1]) if row else 0
            result["status"] = "ok"
            return result
    except Exception as e:
        return {"status": "error", "error": str(e)}


def check_backups():
    """Check backup status — last backup time, file count, size."""
    try:
        backup_dir = os.environ.get("KOKOROKO_BACKUP_DIR", "/backups")
        if not os.path.isdir(backup_dir):
            return {
                "status": "warning",
                "message": f"Backup directory {backup_dir} does not exist",
                "file_count": 0,
            }
        files = sorted(
            [f for f in os.listdir(backup_dir) if os.path.isfile(os.path.join(backup_dir, f))],
            key=lambda f: os.path.getmtime(os.path.join(backup_dir, f)),
            reverse=True,
        )
        total_size = sum(
            os.path.getsize(os.path.join(backup_dir, f))
            for f in files
        )
        last_backup = None
        last_backup_age = None
        if files:
            newest = os.path.join(backup_dir, files[0])
            mtime = datetime.fromtimestamp(os.path.getmtime(newest))
            last_backup = mtime.isoformat()
            age_hours = (datetime.now() - mtime).total_seconds() / 3600
            last_backup_age = f"{age_hours:.1f}h"
        status = "ok"
        if not files:
            status = "warning"
        elif last_backup_age:
            age_h = float(last_backup_age.rstrip("h"))
            if age_h > 48:
                status = "error"
            elif age_h > 26:
                status = "warning"
        return {
            "status": status,
            "file_count": len(files),
            "total_size_mb": round(total_size / (1024 * 1024), 1),
            "last_backup": last_backup,
            "last_backup_age": last_backup_age,
            "newest_file": files[0] if files else None,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def check_recording_health():
    """Check recent recording failures and proof video health."""
    try:
        from django.core.cache import cache
        recent_failures = cache.get("recording_failures_24h", 0)
        last_failure = cache.get("recording_last_failure", None)
        # Check if media/recordings directory has recent files
        recordings_dir = os.path.join(
            str(getattr(settings, "MEDIA_ROOT", "/server/media")),
            "recordings"
        )
        recent_recordings = 0
        if os.path.isdir(recordings_dir):
            cutoff = time.time() - 86400  # last 24h
            for f in os.listdir(recordings_dir):
                fp = os.path.join(recordings_dir, f)
                try:
                    if os.path.getmtime(fp) > cutoff:
                        recent_recordings += 1
                except OSError:
                    pass
        status = "ok"
        if recent_failures > 5:
            status = "error"
        elif recent_failures > 0:
            status = "warning"
        return {
            "status": status,
            "recent_failures_24h": recent_failures,
            "last_failure": last_failure,
            "recent_recordings_24h": recent_recordings,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ─── Aggregated Health Checks ────────────────────────────────────────────────

def public_health_check():
    """Simple health check for public /health/ endpoint."""
    db = check_database()
    redis = check_redis_cache()
    overall = "ok"
    if db["status"] == "error" or redis["status"] == "error":
        overall = "error"
    elif db["status"] != "ok" or redis["status"] != "ok":
        overall = "degraded"
    return {
        "status": overall,
        "timestamp": timezone.now().isoformat(),
    }


def detailed_health_check():
    """Comprehensive health check for admin /admin-api/health/ endpoint."""
    checks = {
        "database": check_database(),
        "redis_cache": check_redis_cache(),
        "redis_detailed": check_redis_detailed(),
        "redis_channels": check_redis_channels(),
        "celery_workers": check_celery(),
        "celery_beat": check_celery_beat(),
        "celery_queues": check_celery_queues(),
        "disk_space": check_disk_space(),
        "media_directory": check_media_directory(),
        "ffmpeg": check_ffmpeg(),
        "mysql_status": check_mysql_status(),
        "backups": check_backups(),
        "recording_health": check_recording_health(),
        "timestamp": timezone.now().isoformat(),
    }

    # Determine overall status
    overall = "ok"
    critical_checks = ["database", "redis_cache", "celery_workers"]
    for name, result in checks.items():
        if name == "timestamp":
            continue
        s = result.get("status", "ok")
        if s == "error":
            if name in critical_checks:
                overall = "error"
                break
            elif overall != "error":
                overall = "degraded"
        elif s in ("warning", "degraded"):
            if overall == "ok":
                overall = "degraded"

    checks["overall"] = overall
    return checks
