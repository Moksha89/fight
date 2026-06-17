"""
Backup & Recovery System — Automated backups of critical data.

Runs as Celery beat tasks:
- Daily database dump
- Wallet ledger export
- Result history export
- Admin activity log export

Backups stored in /backups/ directory with date-stamped filenames.
"""

import json
import logging
import os
import subprocess
from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger("kokoroko.backup")

BACKUP_DIR = os.environ.get("KOKOROKO_BACKUP_DIR", "/backups")


def ensure_backup_dir():
    """Ensure backup directory exists."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    return BACKUP_DIR


def get_backup_filename(prefix, ext="json"):
    """Generate a date-stamped backup filename."""
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{date_str}.{ext}"


def backup_database():
    """
    Full database backup via Django dumpdata.
    Saves JSON fixture of all important models.
    """
    ensure_backup_dir()
    filename = get_backup_filename("db_full", "json")
    filepath = os.path.join(BACKUP_DIR, filename)

    try:
        from django.core.management import call_command
        from io import StringIO
        output = StringIO()
        call_command(
            "dumpdata",
            "wallet", "dicePlayManager", "cockfightManager", "userManager",
            "--indent", "2",
            "--output", filepath,
        )
        logger.info("Database backup completed: %s", filepath)
        return filepath
    except Exception as e:
        logger.error("Database backup failed: %s", e)
        return None


def backup_wallet_ledger():
    """Export wallet balances and recent transaction history."""
    ensure_backup_dir()
    filename = get_backup_filename("wallet_ledger")
    filepath = os.path.join(BACKUP_DIR, filename)

    try:
        from wallet.models import Wallet, WalletHistory

        wallets = list(Wallet.objects.all().values(
            "user_id", "balance", "bonusDebt", "fundsIn", "fundsOut", "updated_at"
        ))

        recent_tx = list(WalletHistory.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=7)
        ).values(
            "wallet_id", "transaction_type", "change", "isSuccess",
            "description", "created_at", "transactionHash"
        ).order_by("-created_at")[:10000])

        data = {
            "exported_at": timezone.now().isoformat(),
            "wallet_count": len(wallets),
            "transaction_count": len(recent_tx),
            "wallets": _serialize_values(wallets),
            "recent_transactions": _serialize_values(recent_tx),
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)

        logger.info("Wallet ledger backup: %s (%d wallets, %d tx)", filepath, len(wallets), len(recent_tx))
        return filepath
    except Exception as e:
        logger.error("Wallet ledger backup failed: %s", e)
        return None


def backup_result_history():
    """Export game result history."""
    ensure_backup_dir()
    filename = get_backup_filename("results")
    filepath = os.path.join(BACKUP_DIR, filename)

    try:
        from dicePlayManager.models import DicePlayMatch
        from cockfightManager.models import CockfightMatch, CockfightAutoMatch

        dice = list(DicePlayMatch.objects.filter(
            isWinnerDeclared=True,
            created_at__gte=timezone.now() - timedelta(days=30)
        ).values(
            "id", "board_id", "title", "match_type", "daily_match_number",
            "match_date", "dice_result_json", "game_hash",
            "total1Rolled", "total2Rolled", "total3Rolled",
            "total4Rolled", "total5Rolled", "total6Rolled",
            "created_at"
        ))

        cockfight = list(CockfightMatch.objects.filter(
            isWinnerDeclared=True,
            created_at__gte=timezone.now() - timedelta(days=30)
        ).values(
            "id", "zone_id", "title", "winTeam", "match_mode",
            "oddsSnapshot", "created_at"
        ))

        data = {
            "exported_at": timezone.now().isoformat(),
            "dice_results": _serialize_values(dice),
            "cockfight_results": _serialize_values(cockfight),
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)

        logger.info("Result history backup: %s (%d dice, %d cockfight)", filepath, len(dice), len(cockfight))
        return filepath
    except Exception as e:
        logger.error("Result history backup failed: %s", e)
        return None


def backup_admin_activity():
    """Export admin audit log from cache."""
    ensure_backup_dir()
    filename = get_backup_filename("admin_activity")
    filepath = os.path.join(BACKUP_DIR, filename)

    try:
        from django.core.cache import cache
        log = cache.get("admin_audit_log", [])

        data = {
            "exported_at": timezone.now().isoformat(),
            "entries": len(log),
            "log": log,
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)

        logger.info("Admin activity backup: %s (%d entries)", filepath, len(log))
        return filepath
    except Exception as e:
        logger.error("Admin activity backup failed: %s", e)
        return None


def run_all_backups():
    """Run all backup tasks. Intended for Celery beat daily schedule."""
    results = {
        "database": backup_database(),
        "wallet_ledger": backup_wallet_ledger(),
        "result_history": backup_result_history(),
        "admin_activity": backup_admin_activity(),
    }

    success = sum(1 for v in results.values() if v)
    failed = sum(1 for v in results.values() if not v)
    logger.info("Backup complete: %d succeeded, %d failed", success, failed)
    return results


def cleanup_old_backups(days=30):
    """Remove backup files older than specified days."""
    ensure_backup_dir()
    cutoff = datetime.now() - timedelta(days=days)
    removed = 0

    for filename in os.listdir(BACKUP_DIR):
        filepath = os.path.join(BACKUP_DIR, filename)
        if os.path.isfile(filepath):
            mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
            if mtime < cutoff:
                os.remove(filepath)
                removed += 1

    logger.info("Cleaned up %d old backup files", removed)
    return removed


def _serialize_values(values_list):
    """Convert Django ValuesQuerySet items for JSON serialization."""
    result = []
    for item in values_list:
        row = {}
        for k, v in item.items():
            row[k] = str(v) if hasattr(v, 'isoformat') else v
        result.append(row)
    return result
