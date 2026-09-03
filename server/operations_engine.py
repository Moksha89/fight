"""Durable operations, notification, reconciliation, and backup services.

The engine deliberately keeps recovery actions conservative: reconciliation
never mutates financial state, and backup restore is not exposed through the
browser. Operators receive evidence and can acknowledge incidents while a
separately controlled recovery procedure remains the production boundary.
"""

from __future__ import annotations

import hashlib
import io
import json
import secrets
import sqlite3
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path


UTC = timezone.utc
INCIDENT_STATES = {"OPEN", "ACKNOWLEDGED", "RESOLVED"}


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class OperationsEngine:
    """Coordinates operator alerts and non-destructive reliability controls."""

    def __init__(self, platform_service):
        self.platform = platform_service
        self.backup_dir = (self.platform.data_dir / "private" / "backups").resolve()
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def connect(self) -> sqlite3.Connection:
        return self.platform.connect()

    def _initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    audience TEXT NOT NULL CHECK(audience IN ('USER','ADMIN')),
                    user_id TEXT NOT NULL DEFAULT '',
                    event_type TEXT NOT NULL,
                    severity TEXT NOT NULL DEFAULT 'INFO' CHECK(severity IN ('INFO','SUCCESS','WARNING','CRITICAL')),
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    action_route TEXT NOT NULL DEFAULT '',
                    channel TEXT NOT NULL DEFAULT 'IN_APP' CHECK(channel IN ('IN_APP','SMS','EMAIL')),
                    delivery_status TEXT NOT NULL DEFAULT 'DELIVERED' CHECK(delivery_status IN ('QUEUED','DELIVERED','FAILED','SUPPRESSED')),
                    dedupe_key TEXT NOT NULL UNIQUE,
                    read_at TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS reconciliation_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reference TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL CHECK(status IN ('PASS','WARNING','FAILED')),
                    critical_count INTEGER NOT NULL DEFAULT 0,
                    warning_count INTEGER NOT NULL DEFAULT 0,
                    check_count INTEGER NOT NULL DEFAULT 0,
                    initiated_by TEXT NOT NULL,
                    summary_json TEXT NOT NULL DEFAULT '{}',
                    started_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS reconciliation_findings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL REFERENCES reconciliation_runs(id),
                    check_code TEXT NOT NULL,
                    severity TEXT NOT NULL CHECK(severity IN ('WARNING','CRITICAL')),
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL DEFAULT '',
                    expected TEXT NOT NULL DEFAULT '',
                    actual TEXT NOT NULL DEFAULT '',
                    message TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS operations_incidents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reference TEXT NOT NULL UNIQUE,
                    source TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    severity TEXT NOT NULL CHECK(severity IN ('WARNING','CRITICAL')),
                    status TEXT NOT NULL DEFAULT 'OPEN' CHECK(status IN ('OPEN','ACKNOWLEDGED','RESOLVED')),
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    occurrence_count INTEGER NOT NULL DEFAULT 1,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    acknowledged_at TEXT NOT NULL DEFAULT '',
                    acknowledged_by TEXT NOT NULL DEFAULT '',
                    resolved_at TEXT NOT NULL DEFAULT '',
                    resolved_by TEXT NOT NULL DEFAULT '',
                    resolution_note TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS backup_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reference TEXT NOT NULL UNIQUE,
                    filename TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL CHECK(status IN ('CREATING','COMPLETED','FAILED')),
                    size_bytes INTEGER NOT NULL DEFAULT 0,
                    sha256 TEXT NOT NULL DEFAULT '',
                    contents_json TEXT NOT NULL DEFAULT '{}',
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL DEFAULT '',
                    verified_at TEXT NOT NULL DEFAULT '',
                    failure_reason TEXT NOT NULL DEFAULT ''
                );

                CREATE INDEX IF NOT EXISTS idx_notifications_user_created
                ON notifications(audience,user_id,created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_notifications_unread
                ON notifications(audience,user_id,read_at) WHERE read_at='';
                CREATE INDEX IF NOT EXISTS idx_reconciliation_findings_run
                ON reconciliation_findings(run_id,severity);
                CREATE INDEX IF NOT EXISTS idx_operations_incidents_status_seen
                ON operations_incidents(status,last_seen_at DESC);
                CREATE INDEX IF NOT EXISTS idx_operations_incidents_fingerprint
                ON operations_incidents(source,fingerprint,status);
                CREATE INDEX IF NOT EXISTS idx_backup_records_created
                ON backup_records(created_at DESC);
                """
            )
            connection.execute("PRAGMA optimize")

    @staticmethod
    def _notification_dict(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"], "audience": row["audience"], "event_type": row["event_type"],
            "severity": row["severity"], "title": row["title"], "message": row["message"],
            "action_route": row["action_route"], "channel": row["channel"],
            "delivery_status": row["delivery_status"], "read": bool(row["read_at"]),
            "read_at": row["read_at"], "created_at": row["created_at"],
        }

    def notify(
        self,
        connection: sqlite3.Connection,
        *,
        audience: str,
        event_type: str,
        title: str,
        message: str,
        dedupe_key: str,
        user_id: str = "",
        severity: str = "INFO",
        action_route: str = "",
    ) -> None:
        normalized_audience = str(audience).upper()
        normalized_severity = str(severity).upper()
        if normalized_audience not in {"USER", "ADMIN"} or normalized_severity not in {"INFO", "SUCCESS", "WARNING", "CRITICAL"}:
            raise ValueError("Invalid notification classification.")
        if normalized_audience == "USER" and not user_id:
            raise ValueError("A player notification requires a user.")
        connection.execute(
            """INSERT OR IGNORE INTO notifications
            (audience,user_id,event_type,severity,title,message,action_route,channel,delivery_status,dedupe_key,created_at)
            VALUES(?,?,?,?,?,?,?,'IN_APP','DELIVERED',?,?)""",
            (
                normalized_audience, str(user_id or ""), str(event_type)[:80], normalized_severity,
                str(title)[:140], str(message)[:500], str(action_route)[:120], str(dedupe_key)[:180], utc_now(),
            ),
        )
        if hasattr(self.platform, "delivery"):
            notification = connection.execute("SELECT * FROM notifications WHERE dedupe_key=?", (str(dedupe_key)[:180],)).fetchone()
            if notification:
                self.platform.delivery.queue_notification(connection, dict(notification))

    def list_user_notifications(self, user_id: str, limit: int = 50) -> dict:
        limit = max(1, min(int(limit), 100))
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM notifications WHERE audience='USER' AND user_id=? ORDER BY id DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
            unread = connection.execute(
                "SELECT COUNT(*) AS total FROM notifications WHERE audience='USER' AND user_id=? AND read_at=''",
                (user_id,),
            ).fetchone()["total"]
        return {"results": [self._notification_dict(row) for row in rows], "unread": int(unread or 0)}

    def ingest_monitoring_alerts(self, payload: dict) -> dict:
        alerts = payload.get("alerts") if isinstance(payload.get("alerts"), list) else []
        accepted = 0
        with self.connect() as connection:
            for alert in alerts[:100]:
                if not isinstance(alert, dict):
                    continue
                labels = alert.get("labels") if isinstance(alert.get("labels"), dict) else {}
                annotations = alert.get("annotations") if isinstance(alert.get("annotations"), dict) else {}
                name = str(labels.get("alertname") or "Monitoring alert")[:100]
                status = str(alert.get("status") or payload.get("status") or "firing").upper()
                severity = "CRITICAL" if str(labels.get("severity") or "").lower() == "critical" else "WARNING"
                title = str(annotations.get("summary") or name)[:140]
                message = str(annotations.get("description") or f"{name} is {status.lower()}.")[:500]
                fingerprint = str(alert.get("fingerprint") or f"{name}:{status}")[:100]
                self.notify(
                    connection, audience="ADMIN", event_type="MONITORING_ALERT", severity=severity,
                    title=title, message=message, action_route="#operations",
                    dedupe_key=f"monitor:{fingerprint}:{status}",
                )
                accepted += 1
        return {"accepted": accepted}

    def mark_notification_read(self, user_id: str, notification_id: int) -> dict:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM notifications WHERE id=? AND audience='USER' AND user_id=?",
                (int(notification_id), user_id),
            ).fetchone()
            if not row:
                raise LookupError("Notification not found.")
            if not row["read_at"]:
                connection.execute("UPDATE notifications SET read_at=? WHERE id=?", (utc_now(), int(notification_id)))
            updated = connection.execute("SELECT * FROM notifications WHERE id=?", (int(notification_id),)).fetchone()
        return self._notification_dict(updated)

    def mark_all_notifications_read(self, user_id: str) -> dict:
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE notifications SET read_at=? WHERE audience='USER' AND user_id=? AND read_at=''",
                (utc_now(), user_id),
            )
        return {"updated": int(cursor.rowcount)}

    @staticmethod
    def _incident_dict(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"], "reference": row["reference"], "source": row["source"],
            "severity": row["severity"], "status": row["status"], "title": row["title"],
            "description": row["description"], "occurrence_count": row["occurrence_count"],
            "first_seen_at": row["first_seen_at"], "last_seen_at": row["last_seen_at"],
            "acknowledged_at": row["acknowledged_at"], "acknowledged_by": row["acknowledged_by"],
            "resolved_at": row["resolved_at"], "resolved_by": row["resolved_by"],
            "resolution_note": row["resolution_note"],
        }

    def _upsert_incident(
        self,
        connection: sqlite3.Connection,
        *,
        source: str,
        fingerprint: str,
        severity: str,
        title: str,
        description: str,
    ) -> None:
        now = utc_now()
        row = connection.execute(
            """SELECT * FROM operations_incidents
            WHERE source=? AND fingerprint=? AND status!='RESOLVED' ORDER BY id DESC LIMIT 1""",
            (source, fingerprint),
        ).fetchone()
        if row:
            connection.execute(
                """UPDATE operations_incidents SET severity=?,title=?,description=?,
                occurrence_count=occurrence_count+1,last_seen_at=? WHERE id=?""",
                (severity, title[:180], description[:1000], now, row["id"]),
            )
            return
        reference = f"INC-{datetime.now(UTC).strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"
        connection.execute(
            """INSERT INTO operations_incidents
            (reference,source,fingerprint,severity,status,title,description,first_seen_at,last_seen_at)
            VALUES(?,?,?,?,'OPEN',?,?,?,?)""",
            (reference, source, fingerprint, severity, title[:180], description[:1000], now, now),
        )

    def _resolve_cleared_reconciliation_incidents(self, connection: sqlite3.Connection, active: set[str]) -> None:
        rows = connection.execute(
            "SELECT id,fingerprint FROM operations_incidents WHERE source='RECONCILIATION' AND status!='RESOLVED'"
        ).fetchall()
        now = utc_now()
        for row in rows:
            if row["fingerprint"] not in active:
                connection.execute(
                    """UPDATE operations_incidents SET status='RESOLVED',resolved_at=?,resolved_by='SYSTEM',
                    resolution_note='A later reconciliation confirmed that the condition cleared.' WHERE id=?""",
                    (now, row["id"]),
                )

    @staticmethod
    def _finding(code: str, severity: str, entity_type: str, entity_id: object, expected: object, actual: object, message: str) -> dict:
        fingerprint = f"{code}:{entity_type}:{entity_id}"
        return {
            "check_code": code, "severity": severity, "entity_type": entity_type,
            "entity_id": str(entity_id), "expected": str(expected), "actual": str(actual),
            "message": message, "fingerprint": fingerprint,
        }

    def run_reconciliation(self, actor: str) -> dict:
        reference = f"REC-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(2).upper()}"
        started = utc_now()
        findings: list[dict] = []
        check_count = 7
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")

            for row in connection.execute(
                """SELECT p.id,p.reference,p.request_type,p.amount_paise,p.status,
                COUNT(l.id) AS ledger_count,COALESCE(SUM(l.amount_paise),0) AS ledger_amount
                FROM payment_requests p LEFT JOIN wallet_ledger l ON l.request_id=p.id
                GROUP BY p.id"""
            ).fetchall():
                expected_count = 1 if row["status"] == "APPROVED" else 0
                if int(row["ledger_count"]) != expected_count:
                    findings.append(self._finding(
                        "PAYMENT_LEDGER_CARDINALITY", "CRITICAL", "PAYMENT_REQUEST", row["reference"],
                        expected_count, row["ledger_count"], "Payment decision and wallet ledger entry do not agree.",
                    ))
                if row["status"] == "APPROVED" and int(row["ledger_count"]) == 1:
                    expected_amount = int(row["amount_paise"]) * (-1 if row["request_type"] == "WITHDRAWAL" else 1)
                    if int(row["ledger_amount"]) != expected_amount:
                        findings.append(self._finding(
                            "PAYMENT_LEDGER_AMOUNT", "CRITICAL", "PAYMENT_REQUEST", row["reference"],
                            expected_amount, row["ledger_amount"], "Approved payment amount does not match its wallet ledger entry.",
                        ))

            for row in connection.execute(
                """SELECT b.id,b.ticket_ref,b.status,b.stake_paise,b.settlement_reference,
                SUM(CASE WHEN h.status='ACTIVE' THEN 1 ELSE 0 END) AS active_holds,
                COALESCE(SUM(CASE WHEN h.status='ACTIVE' THEN h.amount_paise ELSE 0 END),0) AS held_amount
                FROM cockfight_bets b LEFT JOIN wallet_holds h ON h.bet_id=b.id GROUP BY b.id"""
            ).fetchall():
                expected_holds = 1 if row["status"] == "PENDING" else 0
                if int(row["active_holds"] or 0) != expected_holds:
                    findings.append(self._finding(
                        "BET_HOLD_STATE", "CRITICAL", "BET", row["ticket_ref"], expected_holds,
                        row["active_holds"], "Bet state and active wallet hold do not agree.",
                    ))
                if row["status"] == "PENDING" and int(row["held_amount"] or 0) != int(row["stake_paise"]):
                    findings.append(self._finding(
                        "BET_HOLD_AMOUNT", "CRITICAL", "BET", row["ticket_ref"], row["stake_paise"],
                        row["held_amount"], "Pending bet stake does not match its wallet hold.",
                    ))
                if row["status"] != "PENDING" and row["settlement_reference"]:
                    ledger = connection.execute(
                        "SELECT COUNT(*) AS total FROM account_ledger WHERE reference=?", (row["settlement_reference"],)
                    ).fetchone()["total"]
                    if int(ledger or 0) != 1:
                        findings.append(self._finding(
                            "BET_SETTLEMENT_LEDGER", "CRITICAL", "BET", row["ticket_ref"], 1, ledger,
                            "Settled bet is missing its unique account ledger entry.",
                        ))

            for row in connection.execute(
                """SELECT w.user_id,w.balance_paise,
                COALESCE((SELECT SUM(amount_paise) FROM wallet_holds h WHERE h.user_id=w.user_id AND h.status='ACTIVE'),0) AS bet_holds,
                COALESCE((SELECT SUM(amount_paise) FROM payment_requests p WHERE p.user_id=w.user_id AND p.request_type='WITHDRAWAL' AND p.status='PENDING'),0) AS withdrawal_holds
                FROM user_wallets w"""
            ).fetchall():
                available = int(row["balance_paise"]) - int(row["bet_holds"]) - int(row["withdrawal_holds"])
                if available < 0:
                    findings.append(self._finding(
                        "NEGATIVE_AVAILABLE_BALANCE", "CRITICAL", "USER", row["user_id"], ">= 0", available,
                        "Wallet holds exceed the player's authoritative balance.",
                    ))

            integrity = str(connection.execute("PRAGMA quick_check").fetchone()[0])
            if integrity.lower() != "ok":
                findings.append(self._finding(
                    "SQLITE_INTEGRITY", "CRITICAL", "DATABASE", "payments", "ok", integrity,
                    "SQLite quick-check reported an integrity failure.",
                ))

            critical = sum(item["severity"] == "CRITICAL" for item in findings)
            warning = sum(item["severity"] == "WARNING" for item in findings)
            status = "FAILED" if critical else "WARNING" if warning else "PASS"
            completed = utc_now()
            summary = {
                "database_integrity": integrity, "checks": check_count,
                "critical": critical, "warnings": warning, "finding_count": len(findings),
            }
            cursor = connection.execute(
                """INSERT INTO reconciliation_runs
                (reference,status,critical_count,warning_count,check_count,initiated_by,summary_json,started_at,completed_at)
                VALUES(?,?,?,?,?,?,?,?,?)""",
                (reference, status, critical, warning, check_count, actor, json.dumps(summary), started, completed),
            )
            run_id = cursor.lastrowid
            active_fingerprints = set()
            for item in findings:
                active_fingerprints.add(item["fingerprint"])
                connection.execute(
                    """INSERT INTO reconciliation_findings
                    (run_id,check_code,severity,entity_type,entity_id,expected,actual,message,fingerprint,created_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (run_id, item["check_code"], item["severity"], item["entity_type"], item["entity_id"], item["expected"], item["actual"], item["message"], item["fingerprint"], completed),
                )
                self._upsert_incident(
                    connection, source="RECONCILIATION", fingerprint=item["fingerprint"], severity=item["severity"],
                    title=item["check_code"].replace("_", " ").title(), description=item["message"],
                )
            self._resolve_cleared_reconciliation_incidents(connection, active_fingerprints)
            self.platform._audit(connection, "Operations", "Financial reconciliation completed", reference, f"{status} · {len(findings)} findings")
            self.notify(
                connection, audience="ADMIN", event_type="RECONCILIATION_COMPLETED",
                severity="SUCCESS" if status == "PASS" else "CRITICAL", title=f"Reconciliation {status.lower()}",
                message=f"{reference} completed with {len(findings)} finding(s).",
                action_route="#operations", dedupe_key=f"admin:reconciliation:{reference}",
            )
        return self.reconciliation_run(run_id)

    @staticmethod
    def _run_dict(row: sqlite3.Row, findings: list[sqlite3.Row] | None = None) -> dict:
        return {
            "id": row["id"], "reference": row["reference"], "status": row["status"],
            "critical_count": row["critical_count"], "warning_count": row["warning_count"],
            "check_count": row["check_count"], "initiated_by": row["initiated_by"],
            "summary": json.loads(row["summary_json"] or "{}"), "started_at": row["started_at"],
            "completed_at": row["completed_at"],
            "findings": [dict(item) for item in findings or []],
        }

    def reconciliation_run(self, run_id: int) -> dict:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM reconciliation_runs WHERE id=?", (int(run_id),)).fetchone()
            if not row:
                raise LookupError("Reconciliation run not found.")
            findings = connection.execute(
                """SELECT id,check_code,severity,entity_type,entity_id,expected,actual,message,created_at
                FROM reconciliation_findings WHERE run_id=? ORDER BY severity,id""", (int(run_id),)
            ).fetchall()
        return self._run_dict(row, findings)

    @staticmethod
    def _backup_dict(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"], "reference": row["reference"], "status": row["status"],
            "size_bytes": row["size_bytes"], "sha256": row["sha256"],
            "contents": json.loads(row["contents_json"] or "{}"), "created_by": row["created_by"],
            "created_at": row["created_at"], "completed_at": row["completed_at"],
            "verified_at": row["verified_at"], "failure_reason": row["failure_reason"],
            "download_url": f"/api/admin/operations/backups/{row['id']}/download/" if row["status"] == "COMPLETED" else "",
        }

    def create_backup(self, actor: str) -> dict:
        now = utc_now()
        reference = f"BKP-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(2).upper()}"
        filename = f"{reference.lower()}.tar.gz"
        target = (self.backup_dir / filename).resolve()
        if target.parent != self.backup_dir:
            raise ValueError("Invalid backup target.")
        archive_tmp = (self.backup_dir / f".{filename}.tmp").resolve()
        database_name = "database/payments.sqlite3" if self.platform.database.backend == "sqlite" else "database/roosterrun.dump"
        database_tmp = (self.backup_dir / f".{reference.lower()}.database.tmp").resolve()
        with self.connect() as connection:
            cursor = connection.execute(
                """INSERT INTO backup_records(reference,filename,status,created_by,created_at)
                VALUES(?,?,'CREATING',?,?)""", (reference, filename, actor, now)
            )
            backup_id = cursor.lastrowid
        try:
            if self.platform.database.backend == "sqlite":
                source = sqlite3.connect(self.platform.db_path, timeout=30)
                destination = sqlite3.connect(database_tmp)
                try:
                    source.backup(destination)
                    integrity = str(destination.execute("PRAGMA integrity_check").fetchone()[0])
                    if integrity.lower() != "ok":
                        raise RuntimeError(f"Backup database integrity check failed: {integrity}")
                finally:
                    destination.close()
                    source.close()
            else:
                completed_dump = subprocess.run(
                    ["pg_dump", "--format=custom", "--no-owner", "--file", str(database_tmp), self.platform.database.database_url],
                    capture_output=True, text=True, timeout=300, check=False,
                )
                if completed_dump.returncode != 0:
                    raise RuntimeError(f"PostgreSQL backup failed: {completed_dump.stderr.strip()[:300]}")
                verified_dump = subprocess.run(
                    ["pg_restore", "--list", str(database_tmp)], capture_output=True, text=True, timeout=60, check=False,
                )
                if verified_dump.returncode != 0 or "TABLE" not in verified_dump.stdout:
                    raise RuntimeError("PostgreSQL backup verification failed.")
                integrity = "ok"

            upload_files = [path for path in self.platform.upload_dir.rglob("*") if path.is_file()]
            identity_dir = (self.platform.data_dir / "private" / "identity").resolve()
            identity_files = [path for path in identity_dir.rglob("*") if path.is_file()] if identity_dir.is_dir() else []
            payment_dir = self.platform.private_payment_dir.resolve()
            payment_files = [path for path in payment_dir.rglob("*") if path.is_file()] if payment_dir.is_dir() else []
            manifest = {
                "reference": reference, "created_at": now, "database_integrity": integrity,
                "database": database_name, "database_backend": self.platform.database.backend, "upload_files": len(upload_files),
                "identity_files": len(identity_files), "payment_evidence_files": len(payment_files),
                "restore_exposed_in_ui": False,
            }
            with tarfile.open(archive_tmp, "w:gz") as archive:
                archive.add(database_tmp, arcname=database_name, recursive=False)
                for path in upload_files:
                    archive.add(path, arcname=f"uploads/{path.relative_to(self.platform.upload_dir).as_posix()}", recursive=False)
                for path in identity_files:
                    archive.add(path, arcname=f"private/identity/{path.relative_to(identity_dir).as_posix()}", recursive=False)
                for path in payment_files:
                    archive.add(path, arcname=f"private/payments/{path.relative_to(payment_dir).as_posix()}", recursive=False)
                raw_manifest = json.dumps(manifest, indent=2).encode("utf-8")
                info = tarfile.TarInfo("manifest.json")
                info.size = len(raw_manifest)
                info.mtime = int(datetime.now(UTC).timestamp())
                archive.addfile(info, io.BytesIO(raw_manifest))
            archive_tmp.replace(target)
            digest = hashlib.sha256()
            with target.open("rb") as handle:
                while chunk := handle.read(1024 * 1024):
                    digest.update(chunk)
            with tarfile.open(target, "r:gz") as verify:
                names = set(verify.getnames())
                if {database_name, "manifest.json"} - names:
                    raise RuntimeError("Backup archive verification failed.")
            completed = utc_now()
            with self.connect() as connection:
                connection.execute(
                    """UPDATE backup_records SET status='COMPLETED',size_bytes=?,sha256=?,contents_json=?,
                    completed_at=?,verified_at=? WHERE id=?""",
                    (target.stat().st_size, digest.hexdigest(), json.dumps(manifest), completed, completed, backup_id),
                )
                self.platform._audit(connection, "Operations", "Private backup created", reference, f"Verified · {target.stat().st_size} bytes")
                self.notify(
                    connection, audience="ADMIN", event_type="BACKUP_COMPLETED", severity="SUCCESS",
                    title="Private backup verified", message=f"{reference} passed archive and database integrity checks.",
                    action_route="#operations", dedupe_key=f"admin:backup:{reference}",
                )
        except Exception as error:
            archive_tmp.unlink(missing_ok=True)
            target.unlink(missing_ok=True)
            with self.connect() as connection:
                connection.execute(
                    "UPDATE backup_records SET status='FAILED',failure_reason=?,completed_at=? WHERE id=?",
                    (str(error)[:500], utc_now(), backup_id),
                )
                self._upsert_incident(
                    connection, source="BACKUP", fingerprint="backup-creation", severity="CRITICAL",
                    title="Backup creation failed", description=str(error),
                )
                self.platform._audit(connection, "Operations", "Private backup failed", reference, str(error))
            raise
        finally:
            database_tmp.unlink(missing_ok=True)
            archive_tmp.unlink(missing_ok=True)
        return self.backup_record(backup_id)

    def backup_record(self, backup_id: int) -> dict:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM backup_records WHERE id=?", (int(backup_id),)).fetchone()
        if not row:
            raise LookupError("Backup record not found.")
        return self._backup_dict(row)

    def backup_file(self, backup_id: int) -> Path:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM backup_records WHERE id=? AND status='COMPLETED'", (int(backup_id),)).fetchone()
        if not row:
            raise LookupError("Completed backup not found.")
        target = (self.backup_dir / row["filename"]).resolve()
        if target.parent != self.backup_dir or not target.is_file():
            raise LookupError("Backup archive is unavailable.")
        checksum = hashlib.sha256()
        with target.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                checksum.update(chunk)
        digest = checksum.hexdigest()
        if digest != row["sha256"]:
            raise RuntimeError("Backup checksum verification failed.")
        return target

    def update_incident(self, incident_id: int, status: object, note: object, actor: str) -> dict:
        normalized = str(status or "").upper()
        if normalized not in INCIDENT_STATES - {"OPEN"}:
            raise ValueError("Choose acknowledged or resolved.")
        resolution_note = str(note or "").strip()
        if normalized == "RESOLVED" and len(resolution_note) < 3:
            raise ValueError("Enter a resolution note.")
        now = utc_now()
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM operations_incidents WHERE id=?", (int(incident_id),)).fetchone()
            if not row:
                raise LookupError("Incident not found.")
            if row["status"] == "RESOLVED":
                return self._incident_dict(row)
            if normalized == "ACKNOWLEDGED":
                connection.execute(
                    "UPDATE operations_incidents SET status='ACKNOWLEDGED',acknowledged_at=?,acknowledged_by=? WHERE id=?",
                    (now, actor, int(incident_id)),
                )
            else:
                connection.execute(
                    """UPDATE operations_incidents SET status='RESOLVED',resolved_at=?,resolved_by=?,
                    resolution_note=? WHERE id=?""", (now, actor, resolution_note[:500], int(incident_id))
                )
            self.platform._audit(connection, "Operations", f"Incident {normalized.lower()}", row["reference"], resolution_note)
            updated = connection.execute("SELECT * FROM operations_incidents WHERE id=?", (int(incident_id),)).fetchone()
        return self._incident_dict(updated)

    def overview(self) -> dict:
        with self.connect() as connection:
            database_integrity = str(connection.execute("PRAGMA quick_check").fetchone()[0])
            incidents = connection.execute(
                "SELECT * FROM operations_incidents ORDER BY CASE status WHEN 'OPEN' THEN 0 WHEN 'ACKNOWLEDGED' THEN 1 ELSE 2 END,last_seen_at DESC LIMIT 50"
            ).fetchall()
            latest_run = connection.execute("SELECT * FROM reconciliation_runs ORDER BY id DESC LIMIT 1").fetchone()
            latest_findings = connection.execute(
                "SELECT * FROM reconciliation_findings WHERE run_id=? ORDER BY severity,id",
                (latest_run["id"],),
            ).fetchall() if latest_run else []
            backups = connection.execute("SELECT * FROM backup_records ORDER BY id DESC LIMIT 20").fetchall()
            admin_notifications = connection.execute(
                "SELECT * FROM notifications WHERE audience='ADMIN' ORDER BY id DESC LIMIT 30"
            ).fetchall()
            unread_admin = connection.execute(
                "SELECT COUNT(*) AS total FROM notifications WHERE audience='ADMIN' AND read_at=''"
            ).fetchone()["total"]
        return {
            "checked_at": utc_now(), "database": {"status": "ok" if database_integrity.lower() == "ok" else "failed", "integrity": database_integrity},
            "cockfight": self.platform.cockfight.health(), "streaming": self.platform.streaming.health(),
            "compliance": self.platform.compliance.health(),
            "incidents": [self._incident_dict(row) for row in incidents],
            "open_incidents": sum(row["status"] != "RESOLVED" for row in incidents),
            "latest_reconciliation": self._run_dict(latest_run, latest_findings) if latest_run else None,
            "backups": [self._backup_dict(row) for row in backups],
            "notifications": [self._notification_dict(row) for row in admin_notifications],
            "unread_admin_notifications": int(unread_admin or 0),
            "external_delivery": {**self.platform.delivery.health(), "in_app": "ACTIVE"},
        }
