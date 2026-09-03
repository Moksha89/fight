"""Player support and dispute case engine for RoosterRun."""

from __future__ import annotations

import json
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone


UTC = timezone.utc
CATEGORIES = {"PAYMENT", "BET", "STREAM", "ACCOUNT", "VERIFICATION", "RESPONSIBLE_PLAY", "OTHER"}
PRIORITIES = {"LOW": 48, "NORMAL": 24, "HIGH": 4, "URGENT": 1}
STATUSES = {"OPEN", "IN_REVIEW", "WAITING_FOR_PLAYER", "RESOLVED", "CLOSED"}
TRANSITIONS = {
    "OPEN": {"OPEN", "IN_REVIEW", "WAITING_FOR_PLAYER", "RESOLVED", "CLOSED"},
    "IN_REVIEW": {"IN_REVIEW", "WAITING_FOR_PLAYER", "RESOLVED", "CLOSED"},
    "WAITING_FOR_PLAYER": {"WAITING_FOR_PLAYER", "IN_REVIEW", "RESOLVED", "CLOSED"},
    "RESOLVED": {"RESOLVED", "IN_REVIEW", "CLOSED"},
    "CLOSED": {"CLOSED"},
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def clean(value: object, label: str, minimum: int, maximum: int) -> str:
    text = " ".join(str(value or "").strip().split())
    if len(text) < minimum or len(text) > maximum:
        raise ValueError(f"{label} must contain {minimum}–{maximum} characters.")
    return text


class SupportEngine:
    """Durable cases, messages, timelines, SLA priority, and ownership checks."""

    def __init__(self, platform_service):
        self.platform = platform_service
        self._initialize()

    def connect(self) -> sqlite3.Connection:
        return self.platform.connect()

    def _initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS support_tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reference TEXT NOT NULL UNIQUE,
                    user_id TEXT NOT NULL REFERENCES user_wallets(user_id),
                    category TEXT NOT NULL CHECK(category IN ('PAYMENT','BET','STREAM','ACCOUNT','VERIFICATION','RESPONSIBLE_PLAY','OTHER')),
                    subject TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'OPEN' CHECK(status IN ('OPEN','IN_REVIEW','WAITING_FOR_PLAYER','RESOLVED','CLOSED')),
                    priority TEXT NOT NULL DEFAULT 'NORMAL' CHECK(priority IN ('LOW','NORMAL','HIGH','URGENT')),
                    linked_payment_id INTEGER REFERENCES payment_requests(id),
                    linked_bet_id INTEGER REFERENCES cockfight_bets(id),
                    assigned_admin TEXT NOT NULL DEFAULT '',
                    resolution_summary TEXT NOT NULL DEFAULT '',
                    sla_due_at TEXT NOT NULL,
                    first_response_at TEXT NOT NULL DEFAULT '',
                    resolved_at TEXT NOT NULL DEFAULT '',
                    closed_at TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS support_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id INTEGER NOT NULL REFERENCES support_tickets(id),
                    author_type TEXT NOT NULL CHECK(author_type IN ('USER','ADMIN','SYSTEM')),
                    author_id TEXT NOT NULL,
                    visibility TEXT NOT NULL DEFAULT 'PUBLIC' CHECK(visibility IN ('PUBLIC','INTERNAL')),
                    body TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS support_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id INTEGER NOT NULL REFERENCES support_tickets(id),
                    event_type TEXT NOT NULL,
                    previous_value TEXT NOT NULL DEFAULT '',
                    new_value TEXT NOT NULL DEFAULT '',
                    actor TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_support_tickets_user_updated
                ON support_tickets(user_id,updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_support_tickets_queue
                ON support_tickets(status,priority,sla_due_at);
                CREATE INDEX IF NOT EXISTS idx_support_tickets_payment
                ON support_tickets(linked_payment_id) WHERE linked_payment_id IS NOT NULL;
                CREATE INDEX IF NOT EXISTS idx_support_tickets_bet
                ON support_tickets(linked_bet_id) WHERE linked_bet_id IS NOT NULL;
                CREATE INDEX IF NOT EXISTS idx_support_messages_ticket_created
                ON support_messages(ticket_id,created_at,id);
                CREATE INDEX IF NOT EXISTS idx_support_events_ticket_created
                ON support_events(ticket_id,created_at,id);
                """
            )
            connection.execute("PRAGMA optimize")

    @staticmethod
    def _due(priority: str, base: datetime | None = None) -> str:
        return ((base or datetime.now(UTC)) + timedelta(hours=PRIORITIES[priority])).isoformat(timespec="seconds")

    @staticmethod
    def _event(connection: sqlite3.Connection, ticket_id: int, event_type: str, previous: str, new: str, actor: str, metadata: dict | None = None) -> None:
        connection.execute(
            """INSERT INTO support_events(ticket_id,event_type,previous_value,new_value,actor,metadata_json,created_at)
            VALUES(?,?,?,?,?,?,?)""",
            (ticket_id, event_type, previous, new, actor, json.dumps(metadata or {}), utc_now()),
        )

    @staticmethod
    def _message_dict(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"], "author_type": row["author_type"], "author_id": row["author_id"],
            "visibility": row["visibility"], "body": row["body"], "created_at": row["created_at"],
        }

    def _ticket_dict(self, connection: sqlite3.Connection, row: sqlite3.Row, admin: bool = False) -> dict:
        visibility = "" if admin else " AND visibility='PUBLIC'"
        messages = connection.execute(
            f"SELECT * FROM support_messages WHERE ticket_id=?{visibility} ORDER BY id ASC", (row["id"],)
        ).fetchall()
        payment = connection.execute(
            "SELECT reference FROM payment_requests WHERE id=?", (row["linked_payment_id"],)
        ).fetchone() if row["linked_payment_id"] else None
        bet = connection.execute(
            "SELECT ticket_ref FROM cockfight_bets WHERE id=?", (row["linked_bet_id"],)
        ).fetchone() if row["linked_bet_id"] else None
        due = datetime.fromisoformat(row["sla_due_at"])
        if due.tzinfo is None:
            due = due.replace(tzinfo=UTC)
        return {
            "id": row["id"], "reference": row["reference"], "user_id": row["user_id"],
            "category": row["category"], "subject": row["subject"], "status": row["status"],
            "priority": row["priority"], "linked_payment_reference": payment["reference"] if payment else "",
            "linked_bet_reference": bet["ticket_ref"] if bet else "", "assigned_admin": row["assigned_admin"],
            "resolution_summary": row["resolution_summary"], "sla_due_at": row["sla_due_at"],
            "sla_overdue": row["status"] not in {"RESOLVED", "CLOSED"} and due < datetime.now(UTC),
            "first_response_at": row["first_response_at"], "resolved_at": row["resolved_at"],
            "closed_at": row["closed_at"], "created_at": row["created_at"], "updated_at": row["updated_at"],
            "messages": [self._message_dict(message) for message in messages],
        }

    def list_user(self, user_id: str) -> list[dict]:
        self.platform.ensure_user(user_id)
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM support_tickets WHERE user_id=? ORDER BY updated_at DESC,id DESC LIMIT 100", (user_id,)
            ).fetchall()
            return [self._ticket_dict(connection, row, False) for row in rows]

    def list_admin(self, status: str = "") -> dict:
        normalized = str(status or "").upper()
        values: list[object] = []
        where = ""
        if normalized:
            if normalized not in STATUSES:
                raise ValueError("Invalid ticket status.")
            where = "WHERE t.status=?"
            values.append(normalized)
        with self.connect() as connection:
            rows = connection.execute(
                f"""SELECT t.* FROM support_tickets t {where}
                ORDER BY CASE t.status WHEN 'OPEN' THEN 0 WHEN 'IN_REVIEW' THEN 1 WHEN 'WAITING_FOR_PLAYER' THEN 2 ELSE 3 END,
                CASE t.priority WHEN 'URGENT' THEN 0 WHEN 'HIGH' THEN 1 WHEN 'NORMAL' THEN 2 ELSE 3 END,t.sla_due_at ASC,t.id DESC LIMIT 200""",
                values,
            ).fetchall()
            results = [self._ticket_dict(connection, row, True) for row in rows]
            totals = connection.execute(
                """SELECT COUNT(*) AS total,
                SUM(CASE WHEN status IN ('OPEN','IN_REVIEW','WAITING_FOR_PLAYER') THEN 1 ELSE 0 END) AS active,
                SUM(CASE WHEN status='OPEN' THEN 1 ELSE 0 END) AS unassigned,
                SUM(CASE WHEN status NOT IN ('RESOLVED','CLOSED') AND sla_due_at<? THEN 1 ELSE 0 END) AS overdue
                FROM support_tickets""", (utc_now(),)
            ).fetchone()
        return {
            "results": results,
            "summary": {"total": int(totals["total"] or 0), "active": int(totals["active"] or 0), "unassigned": int(totals["unassigned"] or 0), "overdue": int(totals["overdue"] or 0)},
        }

    def create(self, user_id: str, payload: dict) -> dict:
        self.platform.ensure_user(user_id)
        category = str(payload.get("category") or "OTHER").upper()
        if category not in CATEGORIES:
            raise ValueError("Choose a valid support category.")
        subject = clean(payload.get("subject"), "Subject", 5, 120)
        body = clean(payload.get("message"), "Message", 10, 1500)
        payment_reference = str(payload.get("payment_reference") or "").strip().upper()
        bet_reference = str(payload.get("bet_reference") or "").strip().upper()
        if payment_reference and bet_reference:
            raise ValueError("Link either one payment or one bet, not both.")
        now = utc_now()
        reference = f"SUP-{datetime.now(UTC).strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            active = connection.execute(
                "SELECT COUNT(*) AS total FROM support_tickets WHERE user_id=? AND status NOT IN ('RESOLVED','CLOSED')", (user_id,)
            ).fetchone()["total"]
            if int(active or 0) >= 5:
                raise ValueError("You already have five active support tickets. Reply to an existing case or wait for a resolution.")
            payment_id = None
            if payment_reference:
                payment = connection.execute(
                    "SELECT id FROM payment_requests WHERE user_id=? AND UPPER(reference)=?", (user_id, payment_reference)
                ).fetchone()
                if not payment:
                    raise ValueError("The payment reference does not belong to this account.")
                payment_id = payment["id"]
            bet_id = None
            if bet_reference:
                bet = connection.execute(
                    "SELECT id FROM cockfight_bets WHERE user_id=? AND UPPER(ticket_ref)=?", (user_id, bet_reference)
                ).fetchone()
                if not bet:
                    raise ValueError("The bet reference does not belong to this account.")
                bet_id = bet["id"]
            cursor = connection.execute(
                """INSERT INTO support_tickets
                (reference,user_id,category,subject,status,priority,linked_payment_id,linked_bet_id,sla_due_at,created_at,updated_at)
                VALUES(?,?,?,?,'OPEN','NORMAL',?,?,?,?,?)""",
                (reference, user_id, category, subject, payment_id, bet_id, self._due("NORMAL"), now, now),
            )
            ticket_id = cursor.lastrowid
            connection.execute(
                "INSERT INTO support_messages(ticket_id,author_type,author_id,visibility,body,created_at) VALUES(?,'USER',?,'PUBLIC',?,?)",
                (ticket_id, user_id, body, now),
            )
            self._event(connection, ticket_id, "TICKET_CREATED", "", "OPEN", user_id, {"category": category})
            self.platform.operations.notify(
                connection, audience="USER", user_id=user_id, event_type="SUPPORT_TICKET_CREATED", severity="INFO",
                title="Support request opened", message=f"{reference} was sent to the support team.", action_route="#profile",
                dedupe_key=f"user:{user_id}:support-created:{reference}",
            )
            self.platform.operations.notify(
                connection, audience="ADMIN", event_type="SUPPORT_REVIEW_REQUIRED", severity="WARNING",
                title="New support case", message=f"{reference}: {subject}", action_route="#support",
                dedupe_key=f"admin:support-created:{reference}",
            )
            self.platform._audit(connection, "Support", "Ticket created", reference, f"{category} · {user_id}")
            row = connection.execute("SELECT * FROM support_tickets WHERE id=?", (ticket_id,)).fetchone()
            return self._ticket_dict(connection, row, False)

    def user_reply(self, user_id: str, ticket_id: int, body: object) -> dict:
        message = clean(body, "Reply", 2, 1500)
        now = utc_now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM support_tickets WHERE id=? AND user_id=?", (int(ticket_id), user_id)).fetchone()
            if not row:
                raise LookupError("Support ticket not found.")
            if row["status"] == "CLOSED":
                raise ValueError("This ticket is closed. Open a new support request if you still need help.")
            new_status = "OPEN" if row["status"] == "RESOLVED" else "IN_REVIEW"
            connection.execute(
                "INSERT INTO support_messages(ticket_id,author_type,author_id,visibility,body,created_at) VALUES(?,'USER',?,'PUBLIC',?,?)",
                (ticket_id, user_id, message, now),
            )
            connection.execute("UPDATE support_tickets SET status=?,updated_at=?,resolved_at='' WHERE id=?", (new_status, now, ticket_id))
            self._event(connection, ticket_id, "PLAYER_REPLIED", row["status"], new_status, user_id)
            self.platform.operations.notify(
                connection, audience="ADMIN", event_type="SUPPORT_PLAYER_REPLY", severity="INFO",
                title="Player replied to support", message=f"{row['reference']} has a new player reply.", action_route="#support",
                dedupe_key=f"admin:support-player-reply:{ticket_id}:{now}",
            )
            updated = connection.execute("SELECT * FROM support_tickets WHERE id=?", (ticket_id,)).fetchone()
            return self._ticket_dict(connection, updated, False)

    def admin_reply(self, ticket_id: int, body: object, actor: str, internal: bool = False) -> dict:
        message = clean(body, "Message", 2, 1500)
        visibility = "INTERNAL" if internal else "PUBLIC"
        now = utc_now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM support_tickets WHERE id=?", (int(ticket_id),)).fetchone()
            if not row:
                raise LookupError("Support ticket not found.")
            if row["status"] == "CLOSED":
                raise ValueError("Closed tickets cannot receive new messages.")
            connection.execute(
                "INSERT INTO support_messages(ticket_id,author_type,author_id,visibility,body,created_at) VALUES(?,'ADMIN',?,?,?,?)",
                (ticket_id, actor, visibility, message, now),
            )
            first_response = row["first_response_at"] or (now if not internal else "")
            new_status = row["status"] if internal else "WAITING_FOR_PLAYER"
            connection.execute(
                "UPDATE support_tickets SET status=?,first_response_at=?,assigned_admin=?,updated_at=? WHERE id=?",
                (new_status, first_response, row["assigned_admin"] or actor, now, ticket_id),
            )
            self._event(connection, ticket_id, "INTERNAL_NOTE" if internal else "ADMIN_REPLIED", row["status"], new_status, actor)
            if not internal:
                self.platform.operations.notify(
                    connection, audience="USER", user_id=row["user_id"], event_type="SUPPORT_ADMIN_REPLY", severity="INFO",
                    title="Support replied", message=f"{row['reference']} has a new response.", action_route="#profile",
                    dedupe_key=f"user:{row['user_id']}:support-admin-reply:{ticket_id}:{now}",
                )
            self.platform._audit(connection, "Support", "Internal note added" if internal else "Player reply sent", row["reference"], actor)
            updated = connection.execute("SELECT * FROM support_tickets WHERE id=?", (ticket_id,)).fetchone()
            return self._ticket_dict(connection, updated, True)

    def admin_update(self, ticket_id: int, payload: dict, actor: str) -> dict:
        status = str(payload.get("status") or "").upper()
        priority = str(payload.get("priority") or "").upper()
        assigned = str(payload.get("assigned_admin") or actor).strip()[:100]
        resolution = str(payload.get("resolution_summary") or "").strip()
        if status not in STATUSES or priority not in PRIORITIES:
            raise ValueError("Choose a valid status and priority.")
        if status in {"RESOLVED", "CLOSED"}:
            resolution = clean(resolution, "Resolution summary", 3, 500)
        now = utc_now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM support_tickets WHERE id=?", (int(ticket_id),)).fetchone()
            if not row:
                raise LookupError("Support ticket not found.")
            if status not in TRANSITIONS[row["status"]]:
                raise ValueError(f"A {row['status'].lower().replace('_',' ')} ticket cannot move to {status.lower().replace('_',' ')}.")
            created = datetime.fromisoformat(row["created_at"])
            if created.tzinfo is None:
                created = created.replace(tzinfo=UTC)
            resolved_at = now if status == "RESOLVED" else row["resolved_at"] if status != "IN_REVIEW" else ""
            closed_at = now if status == "CLOSED" else row["closed_at"]
            connection.execute(
                """UPDATE support_tickets SET status=?,priority=?,assigned_admin=?,resolution_summary=?,sla_due_at=?,
                resolved_at=?,closed_at=?,updated_at=? WHERE id=?""",
                (status, priority, assigned, resolution, self._due(priority, created), resolved_at, closed_at, now, ticket_id),
            )
            if row["status"] != status:
                self._event(connection, ticket_id, "STATUS_CHANGED", row["status"], status, actor)
            if row["priority"] != priority:
                self._event(connection, ticket_id, "PRIORITY_CHANGED", row["priority"], priority, actor)
            self.platform._audit(connection, "Support", "Ticket updated", row["reference"], f"{status} · {priority} · {assigned}")
            if row["status"] != status:
                self.platform.operations.notify(
                    connection, audience="USER", user_id=row["user_id"], event_type="SUPPORT_STATUS_CHANGED",
                    severity="SUCCESS" if status in {"RESOLVED", "CLOSED"} else "INFO",
                    title=f"Support case {status.lower().replace('_',' ')}",
                    message=f"{row['reference']} is now {status.lower().replace('_',' ')}." + (f" {resolution}" if resolution else ""),
                    action_route="#profile", dedupe_key=f"user:{row['user_id']}:support-status:{ticket_id}:{status}:{now}",
                )
            updated = connection.execute("SELECT * FROM support_tickets WHERE id=?", (ticket_id,)).fetchone()
            return self._ticket_dict(connection, updated, True)

    def health(self) -> dict:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT COUNT(*) AS total,
                SUM(CASE WHEN status NOT IN ('RESOLVED','CLOSED') THEN 1 ELSE 0 END) AS active,
                SUM(CASE WHEN status NOT IN ('RESOLVED','CLOSED') AND sla_due_at<? THEN 1 ELSE 0 END) AS overdue
                FROM support_tickets""", (utc_now(),)
            ).fetchone()
        return {"status": "ok", "tickets": int(row["total"] or 0), "active": int(row["active"] or 0), "overdue": int(row["overdue"] or 0)}
