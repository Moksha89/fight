"""Financial reporting and review-first anomaly intelligence for RoosterRun."""

from __future__ import annotations

import csv
import io
import json
import secrets
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone


UTC = timezone.utc
SEVERITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
STATUSES = {"OPEN", "REVIEWING", "CLEARED", "CONFIRMED"}
DEFAULT_POLICY = {
    "large_withdrawal_rupees": 100000,
    "rapid_cashout_minutes": 120,
    "rapid_cashout_percent": 75,
    "rejected_payments_24h": 3,
    "rejected_risk_checks_15m": 3,
    "betting_velocity_5m": 6,
    "betting_velocity_stake_rupees": 20000,
    "shared_beneficiary_users": 2,
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def rupees(paise: object) -> float:
    return round(int(paise or 0) / 100, 2)


class IntelligenceEngine:
    """Read-only analytics plus durable, human-reviewed anomaly cases."""

    def __init__(self, platform_service):
        self.platform = platform_service
        self._initialize()

    def connect(self) -> sqlite3.Connection:
        return self.platform.connect()

    def _initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS intelligence_scans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reference TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL CHECK(status IN ('COMPLETED','FAILED')),
                    rule_count INTEGER NOT NULL DEFAULT 0,
                    alert_count INTEGER NOT NULL DEFAULT 0,
                    new_alert_count INTEGER NOT NULL DEFAULT 0,
                    summary_json TEXT NOT NULL DEFAULT '{}',
                    initiated_by TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS intelligence_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reference TEXT NOT NULL UNIQUE,
                    fingerprint TEXT NOT NULL UNIQUE,
                    user_id TEXT NOT NULL DEFAULT '',
                    alert_type TEXT NOT NULL,
                    severity TEXT NOT NULL CHECK(severity IN ('LOW','MEDIUM','HIGH','CRITICAL')),
                    score INTEGER NOT NULL CHECK(score BETWEEN 0 AND 100),
                    status TEXT NOT NULL DEFAULT 'OPEN' CHECK(status IN ('OPEN','REVIEWING','CLEARED','CONFIRMED')),
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    evidence_json TEXT NOT NULL DEFAULT '{}',
                    linked_type TEXT NOT NULL DEFAULT '',
                    linked_reference TEXT NOT NULL DEFAULT '',
                    assigned_admin TEXT NOT NULL DEFAULT '',
                    resolution_note TEXT NOT NULL DEFAULT '',
                    detected_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    reviewed_at TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_intelligence_alerts_queue
                ON intelligence_alerts(status,severity,score DESC,detected_at DESC);
                CREATE INDEX IF NOT EXISTS idx_intelligence_alerts_user
                ON intelligence_alerts(user_id,detected_at DESC);
                CREATE INDEX IF NOT EXISTS idx_intelligence_scans_completed
                ON intelligence_scans(completed_at DESC);
                """
            )
            connection.execute(
                "INSERT OR IGNORE INTO admin_settings(setting_key,setting_value,updated_at) VALUES('intelligence',?,?)",
                (json.dumps(DEFAULT_POLICY), utc_now()),
            )
            connection.execute("PRAGMA optimize")

    def policy(self) -> dict:
        with self.connect() as connection:
            row = connection.execute("SELECT setting_value FROM admin_settings WHERE setting_key='intelligence'").fetchone()
        saved = json.loads(row["setting_value"] or "{}") if row else {}
        return {**DEFAULT_POLICY, **saved}

    def save_policy(self, payload: dict) -> dict:
        ranges = {
            "large_withdrawal_rupees": (500, 10_000_000),
            "rapid_cashout_minutes": (5, 1440),
            "rapid_cashout_percent": (10, 100),
            "rejected_payments_24h": (2, 50),
            "rejected_risk_checks_15m": (2, 100),
            "betting_velocity_5m": (2, 100),
            "betting_velocity_stake_rupees": (100, 10_000_000),
            "shared_beneficiary_users": (2, 20),
        }
        current = self.policy()
        for key, (minimum, maximum) in ranges.items():
            if key not in payload:
                continue
            try:
                value = int(payload[key])
            except (TypeError, ValueError):
                raise ValueError(f"{key.replace('_',' ').capitalize()} must be a whole number.") from None
            if value < minimum or value > maximum:
                raise ValueError(f"{key.replace('_',' ').capitalize()} must be between {minimum} and {maximum}.")
            current[key] = value
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                "UPDATE admin_settings SET setting_value=?,updated_at=? WHERE setting_key='intelligence'",
                (json.dumps(current), now),
            )
            self.platform._audit(connection, "Intelligence", "Detection policy updated", "Financial intelligence", json.dumps(current, sort_keys=True))
        return current

    @staticmethod
    def _alert_dict(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"], "reference": row["reference"], "user_id": row["user_id"],
            "alert_type": row["alert_type"], "severity": row["severity"], "score": row["score"],
            "status": row["status"], "title": row["title"], "description": row["description"],
            "evidence": json.loads(row["evidence_json"] or "{}"), "linked_type": row["linked_type"],
            "linked_reference": row["linked_reference"], "assigned_admin": row["assigned_admin"],
            "resolution_note": row["resolution_note"], "detected_at": row["detected_at"],
            "updated_at": row["updated_at"], "reviewed_at": row["reviewed_at"],
        }

    def list_alerts(self, status: str = "") -> dict:
        normalized = str(status or "").upper()
        values: list[object] = []
        where = ""
        if normalized:
            if normalized not in STATUSES:
                raise ValueError("Choose a valid intelligence status.")
            where = "WHERE status=?"
            values.append(normalized)
        with self.connect() as connection:
            rows = connection.execute(
                f"""SELECT * FROM intelligence_alerts {where}
                ORDER BY CASE status WHEN 'OPEN' THEN 0 WHEN 'REVIEWING' THEN 1 ELSE 2 END,
                CASE severity WHEN 'CRITICAL' THEN 0 WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 ELSE 3 END,
                score DESC,id DESC LIMIT 300""", values,
            ).fetchall()
            totals = connection.execute(
                """SELECT COUNT(*) AS total,
                SUM(CASE WHEN status IN ('OPEN','REVIEWING') THEN 1 ELSE 0 END) AS active,
                SUM(CASE WHEN status='OPEN' THEN 1 ELSE 0 END) AS unassigned,
                SUM(CASE WHEN status IN ('OPEN','REVIEWING') AND severity IN ('HIGH','CRITICAL') THEN 1 ELSE 0 END) AS high_risk
                FROM intelligence_alerts"""
            ).fetchone()
        return {"results": [self._alert_dict(row) for row in rows], "summary": {key: int(totals[key] or 0) for key in ("total", "active", "unassigned", "high_risk")}}

    def _upsert_alert(self, connection: sqlite3.Connection, *, fingerprint: str, user_id: str, alert_type: str,
                      severity: str, score: int, title: str, description: str, evidence: dict,
                      linked_type: str = "", linked_reference: str = "") -> bool:
        if severity not in SEVERITIES:
            raise ValueError("Invalid intelligence severity.")
        now = utc_now()
        reference = f"RISK-{datetime.now(UTC).strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"
        cursor = connection.execute(
            """INSERT OR IGNORE INTO intelligence_alerts
            (reference,fingerprint,user_id,alert_type,severity,score,status,title,description,evidence_json,linked_type,linked_reference,detected_at,updated_at)
            VALUES(?,?,?,?,?,?,'OPEN',?,?,?,?,?,?,?)""",
            (reference, fingerprint, user_id, alert_type, severity, score, title, description,
             json.dumps(evidence, sort_keys=True), linked_type, linked_reference, now, now),
        )
        if cursor.rowcount:
            self.platform.operations.notify(
                connection, audience="ADMIN", event_type="INTELLIGENCE_ALERT", severity="CRITICAL" if severity == "CRITICAL" else "WARNING",
                title=title, message=f"{reference}: {description}", action_route="#intelligence",
                dedupe_key=f"admin:intelligence:{fingerprint}",
            )
            return True
        connection.execute(
            """UPDATE intelligence_alerts SET severity=?,score=?,title=?,description=?,evidence_json=?,updated_at=?
            WHERE fingerprint=? AND status IN ('OPEN','REVIEWING')""",
            (severity, score, title, description, json.dumps(evidence, sort_keys=True), now, fingerprint),
        )
        return False

    def scan(self, actor: str) -> dict:
        policy = self.policy()
        now_dt = datetime.now(UTC)
        started = now_dt.isoformat(timespec="seconds")
        reference = f"SCAN-{now_dt.strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(2).upper()}"
        detected = 0
        new_alerts = 0
        by_rule: dict[str, int] = defaultdict(int)
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")

            withdrawals = connection.execute(
                "SELECT * FROM payment_requests WHERE request_type='WITHDRAWAL' AND status='PENDING' ORDER BY id"
            ).fetchall()
            large_threshold = int(policy["large_withdrawal_rupees"]) * 100
            for row in withdrawals:
                if row["amount_paise"] >= large_threshold:
                    detected += 1;by_rule["LARGE_WITHDRAWAL"] += 1
                    new_alerts += self._upsert_alert(connection, fingerprint=f"large-withdrawal:{row['id']}", user_id=row["user_id"],
                        alert_type="LARGE_WITHDRAWAL", severity="HIGH", score=70, title="Large pending withdrawal",
                        description=f"A pending withdrawal of ₹{rupees(row['amount_paise']):,.2f} requires enhanced review.",
                        evidence={"amount": rupees(row["amount_paise"]), "threshold": policy["large_withdrawal_rupees"], "created_at": row["created_at"]},
                        linked_type="PAYMENT", linked_reference=row["reference"])

                cutoff = (datetime.fromisoformat(row["created_at"]).astimezone(UTC) - timedelta(minutes=int(policy["rapid_cashout_minutes"]))).isoformat(timespec="seconds")
                deposit = connection.execute(
                    """SELECT * FROM payment_requests WHERE user_id=? AND request_type='DEPOSIT' AND status='APPROVED'
                    AND reviewed_at>=? AND reviewed_at<=? ORDER BY reviewed_at DESC LIMIT 1""",
                    (row["user_id"], cutoff, row["created_at"]),
                ).fetchone()
                if deposit and row["amount_paise"] * 100 >= deposit["amount_paise"] * int(policy["rapid_cashout_percent"]):
                    detected += 1;by_rule["RAPID_CASH_OUT"] += 1
                    new_alerts += self._upsert_alert(connection, fingerprint=f"rapid-cashout:{row['id']}:{deposit['id']}", user_id=row["user_id"],
                        alert_type="RAPID_CASH_OUT", severity="CRITICAL", score=90, title="Rapid deposit-to-withdrawal movement",
                        description="A withdrawal followed a recently approved deposit and represents a large share of that deposit.",
                        evidence={"withdrawal": row["reference"], "withdrawal_amount": rupees(row["amount_paise"]), "deposit": deposit["reference"], "deposit_amount": rupees(deposit["amount_paise"]), "window_minutes": policy["rapid_cashout_minutes"]},
                        linked_type="PAYMENT", linked_reference=row["reference"])

            payment_cutoff = (now_dt - timedelta(hours=24)).isoformat(timespec="seconds")
            rejected = connection.execute(
                """SELECT user_id,COUNT(*) AS total,MAX(updated_at) AS latest FROM payment_requests
                WHERE status='REJECTED' AND updated_at>=? GROUP BY user_id HAVING COUNT(*)>=?""",
                (payment_cutoff, int(policy["rejected_payments_24h"])),
            ).fetchall()
            for row in rejected:
                detected += 1;by_rule["REPEATED_PAYMENT_REJECTIONS"] += 1
                new_alerts += self._upsert_alert(connection, fingerprint=f"payment-rejections:{row['user_id']}:{now_dt.date()}", user_id=row["user_id"],
                    alert_type="REPEATED_PAYMENT_REJECTIONS", severity="MEDIUM", score=55, title="Repeated rejected payment requests",
                    description=f"{row['total']} payment requests were rejected during the last 24 hours.",
                    evidence={"rejections": row["total"], "window_hours": 24, "latest": row["latest"]})

            risk_cutoff = (now_dt - timedelta(minutes=15)).isoformat(timespec="seconds")
            risk_rejections = connection.execute(
                """SELECT user_id,COUNT(*) AS total,MAX(created_at) AS latest FROM risk_decisions
                WHERE decision='REJECT' AND created_at>=? GROUP BY user_id HAVING COUNT(*)>=?""",
                (risk_cutoff, int(policy["rejected_risk_checks_15m"])),
            ).fetchall()
            for row in risk_rejections:
                detected += 1;by_rule["RISK_CHECK_VELOCITY"] += 1
                new_alerts += self._upsert_alert(connection, fingerprint=f"risk-rejections:{row['user_id']}:{now_dt.strftime('%Y%m%d%H%M')[:11]}", user_id=row["user_id"],
                    alert_type="RISK_CHECK_VELOCITY", severity="HIGH", score=75, title="Repeated rejected bet attempts",
                    description=f"{row['total']} risk checks were rejected during the last 15 minutes.",
                    evidence={"rejections": row["total"], "window_minutes": 15, "latest": row["latest"]})

            bet_cutoff = (now_dt - timedelta(minutes=5)).isoformat(timespec="seconds")
            velocity = connection.execute(
                """SELECT user_id,COUNT(*) AS total,COALESCE(SUM(stake_paise),0) AS stake,MAX(created_at) AS latest
                FROM cockfight_bets WHERE created_at>=? GROUP BY user_id HAVING COUNT(*)>=? AND SUM(stake_paise)>=?""",
                (bet_cutoff, int(policy["betting_velocity_5m"]), int(policy["betting_velocity_stake_rupees"]) * 100),
            ).fetchall()
            for row in velocity:
                detected += 1;by_rule["BETTING_VELOCITY"] += 1
                new_alerts += self._upsert_alert(connection, fingerprint=f"bet-velocity:{row['user_id']}:{now_dt.strftime('%Y%m%d%H%M')[:11]}", user_id=row["user_id"],
                    alert_type="BETTING_VELOCITY", severity="HIGH", score=72, title="High short-window betting activity",
                    description=f"{row['total']} bets totaling ₹{rupees(row['stake']):,.2f} were placed during the last five minutes.",
                    evidence={"bets": row["total"], "stake": rupees(row["stake"]), "window_minutes": 5, "latest": row["latest"]})

            beneficiary_users: dict[str, set[str]] = defaultdict(set)
            beneficiary_refs: dict[str, list[str]] = defaultdict(list)
            beneficiary_cutoff = (now_dt - timedelta(days=30)).isoformat(timespec="seconds")
            for row in connection.execute("SELECT user_id,reference,beneficiary FROM payment_requests WHERE request_type='WITHDRAWAL' AND created_at>=?", (beneficiary_cutoff,)).fetchall():
                data = json.loads(row["beneficiary"] or "{}")
                key = str(data.get("upi_id") or data.get("account_number") or "").strip().lower()
                if key:
                    beneficiary_users[key].add(row["user_id"]);beneficiary_refs[key].append(row["reference"])
            for key, users in beneficiary_users.items():
                if len(users) < int(policy["shared_beneficiary_users"]):
                    continue
                detected += 1;by_rule["SHARED_BENEFICIARY"] += 1
                masked = f"••••{key[-4:]}" if len(key) >= 4 else "masked"
                new_alerts += self._upsert_alert(connection, fingerprint=f"shared-beneficiary:{key}", user_id=sorted(users)[0],
                    alert_type="SHARED_BENEFICIARY", severity="CRITICAL", score=95, title="Beneficiary shared across player accounts",
                    description=f"One withdrawal beneficiary is used by {len(users)} player accounts.",
                    evidence={"beneficiary": masked, "users": sorted(users), "payment_references": beneficiary_refs[key][-20:]}, linked_type="BENEFICIARY", linked_reference=masked)

            summary = {"detected": detected, "new_alerts": new_alerts, "by_rule": dict(by_rule)}
            completed = utc_now()
            cursor = connection.execute(
                """INSERT INTO intelligence_scans(reference,status,rule_count,alert_count,new_alert_count,summary_json,initiated_by,started_at,completed_at)
                VALUES(?,'COMPLETED',?,?,?,?,?,?,?)""",
                (reference, 6, detected, new_alerts, json.dumps(summary, sort_keys=True), actor, started, completed),
            )
            self.platform._audit(connection, "Intelligence", "Detection scan completed", reference, f"{detected} signals · {new_alerts} new alerts")
            return {"id": cursor.lastrowid, "reference": reference, "status": "COMPLETED", "rule_count": 6, "alert_count": detected, "new_alert_count": new_alerts, "summary": summary, "initiated_by": actor, "started_at": started, "completed_at": completed}

    def update_alert(self, alert_id: int, payload: dict, actor: str) -> dict:
        status = str(payload.get("status") or "").upper()
        if status not in STATUSES:
            raise ValueError("Choose a valid review status.")
        assigned = str(payload.get("assigned_admin") or actor).strip()[:100]
        note = " ".join(str(payload.get("resolution_note") or "").strip().split())[:1000]
        if status in {"CLEARED", "CONFIRMED"} and len(note) < 5:
            raise ValueError("Record a clear review reason before closing an intelligence alert.")
        now = utc_now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM intelligence_alerts WHERE id=?", (int(alert_id),)).fetchone()
            if not row:
                raise LookupError("Intelligence alert not found.")
            reviewed = now if status in {"CLEARED", "CONFIRMED"} else ""
            connection.execute(
                "UPDATE intelligence_alerts SET status=?,assigned_admin=?,resolution_note=?,reviewed_at=?,updated_at=? WHERE id=?",
                (status, assigned, note, reviewed, now, alert_id),
            )
            self.platform._audit(connection, "Intelligence", "Alert reviewed", row["reference"], f"{status} · {assigned} · {note}")
            updated = connection.execute("SELECT * FROM intelligence_alerts WHERE id=?", (int(alert_id),)).fetchone()
            return self._alert_dict(updated)

    def overview(self) -> dict:
        today = datetime.now(UTC).date()
        dates = [(today - timedelta(days=offset)).isoformat() for offset in range(13, -1, -1)]
        daily = {date: {"date": date, "deposits": 0.0, "withdrawals": 0.0, "stakes": 0.0, "payouts": 0.0} for date in dates}
        with self.connect() as connection:
            wallet = connection.execute("SELECT COALESCE(SUM(balance_paise),0) AS balance,COUNT(*) AS users FROM user_wallets").fetchone()
            withdrawal_holds = connection.execute("SELECT COALESCE(SUM(amount_paise),0) AS amount FROM payment_requests WHERE request_type='WITHDRAWAL' AND status='PENDING'").fetchone()["amount"]
            bet_holds = connection.execute("SELECT COALESCE(SUM(amount_paise),0) AS amount FROM wallet_holds WHERE status='ACTIVE'").fetchone()["amount"]
            payments = {kind: {status: {"count": 0, "amount": 0.0} for status in ("PENDING", "APPROVED", "REJECTED")} for kind in ("DEPOSIT", "WITHDRAWAL")}
            for row in connection.execute("SELECT request_type,status,COUNT(*) AS total,COALESCE(SUM(amount_paise),0) AS amount FROM payment_requests GROUP BY request_type,status").fetchall():
                payments[row["request_type"]][row["status"]] = {"count": int(row["total"]), "amount": rupees(row["amount"])}
            bets = connection.execute(
                """SELECT COUNT(*) AS total,COALESCE(SUM(stake_paise),0) AS stakes,
                COALESCE(SUM(payout_paise),0) AS payouts,
                COALESCE(SUM(CASE WHEN status='PENDING' THEN potential_return_paise ELSE 0 END),0) AS open_liability,
                SUM(CASE WHEN status='PENDING' THEN 1 ELSE 0 END) AS pending FROM cockfight_bets"""
            ).fetchone()
            for row in connection.execute("SELECT date(reviewed_at) AS day,request_type,COALESCE(SUM(amount_paise),0) AS amount FROM payment_requests WHERE status='APPROVED' AND reviewed_at!='' AND date(reviewed_at)>=? GROUP BY day,request_type", (dates[0],)).fetchall():
                if row["day"] in daily:
                    daily[row["day"]]["deposits" if row["request_type"] == "DEPOSIT" else "withdrawals"] = rupees(row["amount"])
            for row in connection.execute("SELECT date(created_at) AS day,COALESCE(SUM(stake_paise),0) AS stakes,COALESCE(SUM(payout_paise),0) AS payouts FROM cockfight_bets WHERE date(created_at)>=? GROUP BY day", (dates[0],)).fetchall():
                if row["day"] in daily:
                    daily[row["day"]]["stakes"] = rupees(row["stakes"]);daily[row["day"]]["payouts"] = rupees(row["payouts"])
            scan = connection.execute("SELECT * FROM intelligence_scans ORDER BY id DESC LIMIT 1").fetchone()
        alerts = self.list_alerts()["summary"]
        balance = int(wallet["balance"] or 0)
        available = max(0, balance - int(withdrawal_holds or 0) - int(bet_holds or 0))
        return {
            "generated_at": utc_now(),
            "funds": {"wallet_balance": rupees(balance), "available": rupees(available), "withdrawal_holds": rupees(withdrawal_holds), "bet_holds": rupees(bet_holds), "users": int(wallet["users"] or 0)},
            "payments": payments,
            "betting": {"tickets": int(bets["total"] or 0), "pending": int(bets["pending"] or 0), "stakes": rupees(bets["stakes"]), "payouts": rupees(bets["payouts"]), "gross_result": rupees(int(bets["stakes"] or 0) - int(bets["payouts"] or 0)), "open_liability": rupees(bets["open_liability"])},
            "alerts": alerts,
            "daily": list(daily.values()),
            "latest_scan": None if not scan else {"reference": scan["reference"], "status": scan["status"], "alert_count": scan["alert_count"], "new_alert_count": scan["new_alert_count"], "initiated_by": scan["initiated_by"], "completed_at": scan["completed_at"]},
            "policy": self.policy(),
        }

    def export_csv(self) -> bytes:
        overview = self.overview()
        alerts = self.list_alerts()["results"]
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(["RoosterRun financial intelligence export", overview["generated_at"]])
        writer.writerow([])
        writer.writerow(["Metric", "Value INR"])
        for label, value in (("Wallet balance", overview["funds"]["wallet_balance"]), ("Available funds", overview["funds"]["available"]), ("Withdrawal holds", overview["funds"]["withdrawal_holds"]), ("Bet holds", overview["funds"]["bet_holds"]), ("Bet stakes", overview["betting"]["stakes"]), ("Bet payouts", overview["betting"]["payouts"]), ("Gross result", overview["betting"]["gross_result"]), ("Open liability", overview["betting"]["open_liability"])):
            writer.writerow([label, f"{value:.2f}"])
        writer.writerow([])
        writer.writerow(["Alert reference", "Status", "Severity", "Score", "Player", "Type", "Title", "Linked record", "Assigned", "Resolution", "Detected"])
        for alert in alerts:
            writer.writerow([alert["reference"], alert["status"], alert["severity"], alert["score"], alert["user_id"], alert["alert_type"], alert["title"], alert["linked_reference"], alert["assigned_admin"], alert["resolution_note"], alert["detected_at"]])
        return output.getvalue().encode("utf-8-sig")

    def health(self) -> dict:
        with self.connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS total,SUM(CASE WHEN status IN ('OPEN','REVIEWING') THEN 1 ELSE 0 END) AS active FROM intelligence_alerts").fetchone()
            last_scan = connection.execute("SELECT completed_at FROM intelligence_scans ORDER BY id DESC LIMIT 1").fetchone()
        return {"status": "ok", "alerts": int(row["total"] or 0), "active": int(row["active"] or 0), "last_scan_at": last_scan["completed_at"] if last_scan else ""}
