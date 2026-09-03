"""Authoritative cockfight domain engines for RoosterRun.

The implementation deliberately keeps the engines in one deployable process
while preserving hard module boundaries in the data model: match state, odds,
risk decisions, quotes, bets, wallet holds, settlement ledger, and events are
all durable and independently auditable. The same contracts can later move to
PostgreSQL/Redis workers without changing the browser API.
"""

from __future__ import annotations

import json
import secrets
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


UTC = timezone.utc
TERMINAL_BET_STATES = {"WON", "LOST", "REFUNDED", "VOID"}
OUTCOME_ALIASES = {
    1: "RED", 2: "BLUE", 3: "DRAW", 4: "CANCELLED",
    "1": "RED", "2": "BLUE", "3": "DRAW", "4": "CANCELLED",
    "RED": "RED", "MERON": "RED", "BLUE": "BLUE", "WALA": "BLUE",
    "DRAW": "DRAW", "TIE": "DRAW", "CANCELLED": "CANCELLED", "CANCELED": "CANCELLED",
}
OUTCOME_NUMBERS = {"RED": 1, "BLUE": 2, "DRAW": 3, "CANCELLED": 4}
ALLOWED_TRANSITIONS = {
    "DRAFT": {"SCHEDULED", "CANCELLED"},
    "SCHEDULED": {"BETTING_OPEN", "BETTING_CLOSED", "CANCELLED"},
    "BETTING_OPEN": {"BETTING_CLOSED", "CANCELLED"},
    "BETTING_CLOSED": {"LIVE", "CANCELLED"},
    "LIVE": {"AWAITING_RESULT", "CANCELLED"},
    "AWAITING_RESULT": {"SETTLED", "CANCELLED"},
    "SETTLED": set(),
    "CANCELLED": set(),
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def parse_timestamp(value: object, label: str = "Timestamp") -> datetime:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label} is required.")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"{label} must be a valid date and time.") from None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def timestamp(value: object, label: str = "Timestamp") -> str:
    return parse_timestamp(value, label).isoformat(timespec="seconds")


def to_paise(value: object, minimum: int = 10, maximum: int = 500_000) -> int:
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        raise ValueError("Enter a valid stake amount.") from None
    paise = int(amount * 100)
    if paise < minimum * 100 or paise > maximum * 100:
        raise ValueError(f"Stake must be between ₹{minimum:,} and ₹{maximum:,}.")
    return paise


def rupees(paise: int) -> float:
    return round(int(paise or 0) / 100, 2)


def outcome(value: object, allow_cancelled: bool = False) -> str:
    normalized = OUTCOME_ALIASES.get(value, OUTCOME_ALIASES.get(str(value or "").strip().upper()))
    if not normalized or (normalized == "CANCELLED" and not allow_cancelled):
        raise ValueError("Choose Red, Blue, or Draw.")
    return normalized


class CockfightEngine:
    """Coordinates the match, odds, risk, betting, wallet, and settlement engines."""

    def __init__(self, platform_service):
        self.platform = platform_service
        self._stop_event = threading.Event()
        self._scheduler: threading.Thread | None = None
        self._initialize()

    def connect(self) -> sqlite3.Connection:
        return self.platform.connect()

    def _initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS engine_match_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_id INTEGER NOT NULL REFERENCES admin_games(id),
                    sequence INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    previous_status TEXT NOT NULL DEFAULT '',
                    new_status TEXT NOT NULL DEFAULT '',
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    actor TEXT NOT NULL DEFAULT 'SYSTEM',
                    created_at TEXT NOT NULL,
                    UNIQUE(game_id, sequence)
                );

                CREATE TABLE IF NOT EXISTS odds_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_id INTEGER NOT NULL REFERENCES admin_games(id),
                    version INTEGER NOT NULL,
                    team_a_odds REAL NOT NULL,
                    draw_odds REAL NOT NULL,
                    team_b_odds REAL NOT NULL,
                    market_status TEXT NOT NULL DEFAULT 'OPEN' CHECK(market_status IN ('OPEN','SUSPENDED')),
                    reason TEXT NOT NULL DEFAULT '',
                    created_by TEXT NOT NULL DEFAULT 'SYSTEM',
                    created_at TEXT NOT NULL,
                    UNIQUE(game_id, version)
                );

                CREATE TABLE IF NOT EXISTS bet_quotes (
                    quote_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES user_wallets(user_id),
                    game_id INTEGER NOT NULL REFERENCES admin_games(id),
                    outcome TEXT NOT NULL CHECK(outcome IN ('RED','BLUE','DRAW')),
                    stake_paise INTEGER NOT NULL CHECK(stake_paise > 0),
                    accepted_odds REAL NOT NULL,
                    potential_return_paise INTEGER NOT NULL CHECK(potential_return_paise >= stake_paise),
                    odds_version INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'OPEN' CHECK(status IN ('OPEN','CONSUMED','EXPIRED','REJECTED')),
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    consumed_at TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS cockfight_bets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_ref TEXT NOT NULL UNIQUE,
                    quote_id TEXT NOT NULL UNIQUE REFERENCES bet_quotes(quote_id),
                    user_id TEXT NOT NULL REFERENCES user_wallets(user_id),
                    game_id INTEGER NOT NULL REFERENCES admin_games(id),
                    outcome TEXT NOT NULL CHECK(outcome IN ('RED','BLUE','DRAW')),
                    stake_paise INTEGER NOT NULL CHECK(stake_paise > 0),
                    accepted_odds REAL NOT NULL,
                    potential_return_paise INTEGER NOT NULL,
                    odds_version INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING','WON','LOST','REFUNDED','VOID')),
                    payout_paise INTEGER NOT NULL DEFAULT 0,
                    settlement_reference TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    settled_at TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS wallet_holds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL REFERENCES user_wallets(user_id),
                    bet_id INTEGER NOT NULL UNIQUE REFERENCES cockfight_bets(id),
                    amount_paise INTEGER NOT NULL CHECK(amount_paise > 0),
                    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','RELEASED','CONSUMED')),
                    created_at TEXT NOT NULL,
                    released_at TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS account_ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL REFERENCES user_wallets(user_id),
                    reference TEXT NOT NULL UNIQUE,
                    entry_type TEXT NOT NULL CHECK(entry_type IN ('BET_WIN','BET_LOSS','BET_REFUND','ADJUSTMENT')),
                    amount_paise INTEGER NOT NULL,
                    balance_after_paise INTEGER NOT NULL CHECK(balance_after_paise >= 0),
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS risk_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    game_id INTEGER NOT NULL,
                    quote_id TEXT NOT NULL DEFAULT '',
                    decision TEXT NOT NULL CHECK(decision IN ('PASS','REJECT')),
                    reason TEXT NOT NULL DEFAULT '',
                    metrics_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS engine_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    aggregate_type TEXT NOT NULL,
                    aggregate_id TEXT NOT NULL,
                    aggregate_version INTEGER NOT NULL DEFAULT 0,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_engine_match_events_game_sequence
                ON engine_match_events(game_id, sequence DESC);
                CREATE INDEX IF NOT EXISTS idx_odds_snapshots_game_version
                ON odds_snapshots(game_id, version DESC);
                CREATE INDEX IF NOT EXISTS idx_bet_quotes_user_created
                ON bet_quotes(user_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_cockfight_bets_user_created
                ON cockfight_bets(user_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_cockfight_bets_game_status
                ON cockfight_bets(game_id, status);
                CREATE INDEX IF NOT EXISTS idx_wallet_holds_user_status
                ON wallet_holds(user_id, status);
                CREATE INDEX IF NOT EXISTS idx_risk_decisions_game_created
                ON risk_decisions(game_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_engine_events_id
                ON engine_events(id);
                """
            )
            now = utc_now()
            default_policy = {
                "minimum_stake": 10,
                "maximum_stake": 50_000,
                "maximum_user_exposure": 200_000,
                "maximum_match_pool": 2_000_000,
                "maximum_outcome_liability": 1_000_000,
                "maximum_bets_per_minute": 8,
                "quote_ttl_seconds": 15,
            }
            connection.execute(
                "INSERT OR IGNORE INTO admin_settings(setting_key,setting_value,updated_at) VALUES('risk',?,?)",
                (json.dumps(default_policy), now),
            )
            games = connection.execute("SELECT * FROM admin_games").fetchall()
            for game in games:
                self._ensure_odds_snapshot(connection, game, "SYSTEM")
            connection.execute("PRAGMA optimize")

    def start_scheduler(self) -> None:
        if self._scheduler and self._scheduler.is_alive():
            return
        self._stop_event.clear()

        def run() -> None:
            while not self._stop_event.wait(1.0):
                try:
                    self.advance_due_matches()
                    self.expire_quotes()
                except Exception:
                    # A failed tick must never terminate future scheduling.
                    continue

        self._scheduler = threading.Thread(target=run, name="roosterrun-match-scheduler", daemon=True)
        self._scheduler.start()

    def stop_scheduler(self) -> None:
        self._stop_event.set()
        if self._scheduler and self._scheduler.is_alive():
            self._scheduler.join(timeout=2)

    def risk_policy(self, connection: sqlite3.Connection | None = None) -> dict:
        owns_connection = connection is None
        if owns_connection:
            connection = self.connect()
        try:
            row = connection.execute("SELECT setting_value FROM admin_settings WHERE setting_key='risk'").fetchone()
            return json.loads(row["setting_value"] or "{}") if row else {}
        finally:
            if owns_connection:
                connection.close()

    def update_risk_policy(self, payload: dict) -> dict:
        current = self.risk_policy()
        policy = dict(current)
        numeric = {
            "minimum_stake": (1, 100_000),
            "maximum_stake": (10, 5_000_000),
            "maximum_user_exposure": (10, 20_000_000),
            "maximum_match_pool": (100, 100_000_000),
            "maximum_outcome_liability": (100, 100_000_000),
            "maximum_bets_per_minute": (1, 200),
            "quote_ttl_seconds": (5, 60),
        }
        for key, (minimum, maximum) in numeric.items():
            try:
                value = int(payload.get(key, current.get(key, minimum)))
            except (TypeError, ValueError):
                raise ValueError(f"{key.replace('_', ' ').title()} must be a number.") from None
            if value < minimum or value > maximum:
                raise ValueError(f"{key.replace('_', ' ').title()} is outside the allowed range.")
            policy[key] = value
        if policy["minimum_stake"] > policy["maximum_stake"]:
            raise ValueError("Minimum stake cannot exceed maximum stake.")
        with self.connect() as connection:
            connection.execute(
                "UPDATE admin_settings SET setting_value=?,updated_at=? WHERE setting_key='risk'",
                (json.dumps(policy), utc_now()),
            )
            self._outbox(connection, "RISK_POLICY_UPDATED", "RISK", "GLOBAL", 1, policy)
            self.platform._audit(connection, "Risk", "Risk policy updated", "Global limits", ", ".join(policy.keys()))
        return policy

    @staticmethod
    def _game_dict(row: sqlite3.Row) -> dict:
        return dict(row)

    def _ensure_odds_snapshot(self, connection: sqlite3.Connection, game: sqlite3.Row | dict, actor: str) -> sqlite3.Row:
        game_id = game["id"]
        latest = connection.execute(
            "SELECT * FROM odds_snapshots WHERE game_id=? ORDER BY version DESC LIMIT 1", (game_id,)
        ).fetchone()
        values = (round(float(game["team_a_odds"]), 2), round(float(game["draw_odds"]), 2), round(float(game["team_b_odds"]), 2))
        market_status = "OPEN" if str(game["status"]) == "BETTING_OPEN" else "SUSPENDED"
        if latest and values == (latest["team_a_odds"], latest["draw_odds"], latest["team_b_odds"]) and latest["market_status"] == market_status:
            return latest
        version = int(latest["version"] if latest else 0) + 1
        connection.execute(
            """INSERT INTO odds_snapshots(game_id,version,team_a_odds,draw_odds,team_b_odds,market_status,reason,created_by,created_at)
            VALUES(?,?,?,?,?,?,?,?,?)""",
            (game_id, version, *values, market_status, "Game odds synchronized", actor, utc_now()),
        )
        return connection.execute(
            "SELECT * FROM odds_snapshots WHERE game_id=? AND version=?", (game_id, version)
        ).fetchone()

    def sync_game(self, game_id: int, actor: str = "ADMIN", previous_status: str = "") -> dict:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            game = connection.execute("SELECT * FROM admin_games WHERE id=?", (game_id,)).fetchone()
            if not game:
                raise LookupError("Game not found.")
            odds = self._ensure_odds_snapshot(connection, game, actor)
            current_status = game["status"]
            event_type = "GAME_STATE_CHANGED" if previous_status and previous_status != current_status else "GAME_CONFIGURATION_UPDATED"
            self._record_match_event(connection, game_id, event_type, previous_status, current_status, {"odds_version": odds["version"]}, actor)
            return {"game": dict(game), "odds": self._odds_dict(odds)}

    @staticmethod
    def _odds_dict(row: sqlite3.Row) -> dict:
        return {
            "game_id": row["game_id"], "version": row["version"], "team_a_odds": row["team_a_odds"],
            "draw_odds": row["draw_odds"], "team_b_odds": row["team_b_odds"],
            "market_status": row["market_status"], "reason": row["reason"], "created_at": row["created_at"],
        }

    def current_odds(self, game_id: int | None = None) -> dict:
        self.advance_due_matches()
        with self.connect() as connection:
            if game_id is None:
                game = connection.execute(
                    "SELECT * FROM admin_games WHERE featured=1 ORDER BY id DESC LIMIT 1"
                ).fetchone() or connection.execute("SELECT * FROM admin_games ORDER BY id DESC LIMIT 1").fetchone()
                if not game:
                    raise LookupError("No game is available.")
                game_id = game["id"]
            row = connection.execute(
                "SELECT * FROM odds_snapshots WHERE game_id=? ORDER BY version DESC LIMIT 1", (game_id,)
            ).fetchone()
            if not row:
                raise LookupError("Odds are not available for this game.")
            return self._odds_dict(row)

    def publish_odds(self, game_id: int, payload: dict, actor: str = "ADMIN") -> dict:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            game = connection.execute("SELECT * FROM admin_games WHERE id=?", (game_id,)).fetchone()
            if not game:
                raise LookupError("Game not found.")
            values = []
            for key in ("team_a_odds", "draw_odds", "team_b_odds"):
                try:
                    value = round(float(payload.get(key, game[key])), 2)
                except (TypeError, ValueError):
                    raise ValueError("Enter valid decimal odds.") from None
                if value < 1.01 or value > 100:
                    raise ValueError("Odds must be between 1.01 and 100.")
                values.append(value)
            status = str(payload.get("market_status") or "OPEN").upper()
            if status not in {"OPEN", "SUSPENDED"}:
                raise ValueError("Invalid market status.")
            if status == "OPEN" and game["status"] != "BETTING_OPEN":
                raise ValueError("Odds can open only while the match is accepting bets.")
            latest = connection.execute("SELECT COALESCE(MAX(version),0) AS version FROM odds_snapshots WHERE game_id=?", (game_id,)).fetchone()
            version = int(latest["version"]) + 1
            reason = str(payload.get("reason") or "Administrator odds update").strip()[:180]
            connection.execute(
                """INSERT INTO odds_snapshots(game_id,version,team_a_odds,draw_odds,team_b_odds,market_status,reason,created_by,created_at)
                VALUES(?,?,?,?,?,?,?,?,?)""",
                (game_id, version, *values, status, reason, actor, utc_now()),
            )
            connection.execute(
                "UPDATE admin_games SET team_a_odds=?,draw_odds=?,team_b_odds=?,updated_at=? WHERE id=?",
                (*values, utc_now(), game_id),
            )
            row = connection.execute("SELECT * FROM odds_snapshots WHERE game_id=? AND version=?", (game_id, version)).fetchone()
            data = self._odds_dict(row)
            self._record_match_event(connection, game_id, "ODDS_PUBLISHED", game["status"], game["status"], data, actor)
            self.platform._audit(connection, "Odds", "Odds published", game["title"], f"Version {version} · {status}")
            return data

    def _record_match_event(
        self, connection: sqlite3.Connection, game_id: int, event_type: str, previous: str,
        new: str, payload: dict, actor: str,
    ) -> None:
        row = connection.execute("SELECT COALESCE(MAX(sequence),0) AS sequence FROM engine_match_events WHERE game_id=?", (game_id,)).fetchone()
        sequence = int(row["sequence"]) + 1
        now = utc_now()
        connection.execute(
            """INSERT INTO engine_match_events(game_id,sequence,event_type,previous_status,new_status,payload_json,actor,created_at)
            VALUES(?,?,?,?,?,?,?,?)""",
            (game_id, sequence, event_type, previous or "", new or "", json.dumps(payload), actor, now),
        )
        self._outbox(connection, event_type, "MATCH", str(game_id), sequence, {"game_id": game_id, "previous_status": previous, "status": new, **payload})

    @staticmethod
    def _outbox(connection: sqlite3.Connection, event_type: str, aggregate_type: str, aggregate_id: str, version: int, payload: dict) -> None:
        connection.execute(
            "INSERT INTO engine_events(event_type,aggregate_type,aggregate_id,aggregate_version,payload_json,created_at) VALUES(?,?,?,?,?,?)",
            (event_type, aggregate_type, aggregate_id, version, json.dumps(payload), utc_now()),
        )

    def transition_game(self, game_id: int, new_status: str, actor: str = "ADMIN", reason: str = "") -> dict:
        target = str(new_status or "").upper()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            game = connection.execute("SELECT * FROM admin_games WHERE id=?", (game_id,)).fetchone()
            if not game:
                raise LookupError("Game not found.")
            previous = game["status"]
            if target == previous:
                return dict(game)
            if target not in ALLOWED_TRANSITIONS.get(previous, set()):
                raise ValueError(f"A match cannot move from {previous.replace('_',' ')} to {target.replace('_',' ')}.")
            now = utc_now()
            actual_start = now if target == "LIVE" else game["actual_start_at"]
            settled_at = now if target == "SETTLED" else game["settled_at"]
            connection.execute(
                "UPDATE admin_games SET status=?,actual_start_at=?,settled_at=?,state_version=state_version+1,updated_at=? WHERE id=?",
                (target, actual_start, settled_at, now, game_id),
            )
            if target in {"BETTING_OPEN", "BETTING_CLOSED"}:
                latest = connection.execute("SELECT * FROM odds_snapshots WHERE game_id=? ORDER BY version DESC LIMIT 1", (game_id,)).fetchone()
                desired_market = "OPEN" if target == "BETTING_OPEN" else "SUSPENDED"
                if latest and latest["market_status"] != desired_market:
                    self.publish_odds_in_transaction(connection, game, latest, desired_market, reason or f"Market {desired_market.lower()}", actor)
            self._record_match_event(connection, game_id, "GAME_STATE_CHANGED", previous, target, {"reason": reason}, actor)
            updated = connection.execute("SELECT * FROM admin_games WHERE id=?", (game_id,)).fetchone()
            return dict(updated)

    def publish_odds_in_transaction(self, connection: sqlite3.Connection, game: sqlite3.Row, latest: sqlite3.Row, market_status: str, reason: str, actor: str) -> sqlite3.Row:
        version = int(latest["version"]) + 1
        connection.execute(
            """INSERT INTO odds_snapshots(game_id,version,team_a_odds,draw_odds,team_b_odds,market_status,reason,created_by,created_at)
            VALUES(?,?,?,?,?,?,?,?,?)""",
            (game["id"], version, latest["team_a_odds"], latest["draw_odds"], latest["team_b_odds"], market_status, reason, actor, utc_now()),
        )
        return connection.execute("SELECT * FROM odds_snapshots WHERE game_id=? AND version=?", (game["id"], version)).fetchone()

    def advance_due_matches(self) -> list[dict]:
        changed: list[dict] = []
        now = datetime.now(UTC)
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM admin_games WHERE status IN ('SCHEDULED','BETTING_OPEN','BETTING_CLOSED') ORDER BY id"
            ).fetchall()
        for row in rows:
            current = dict(row)
            while True:
                status = current["status"]
                target = ""
                reason = ""
                try:
                    if status == "SCHEDULED" and parse_timestamp(current["betting_opens_at"], "Betting opens") <= now:
                        target, reason = "BETTING_OPEN", "Scheduled betting window opened"
                    elif status == "BETTING_OPEN" and parse_timestamp(current["betting_closes_at"], "Betting closes") <= now:
                        target, reason = "BETTING_CLOSED", "Scheduled betting window closed"
                    elif status == "BETTING_CLOSED" and parse_timestamp(current["scheduled_at"], "Scheduled start") <= now:
                        target, reason = "LIVE", "Scheduled match start reached"
                except ValueError:
                    break
                if not target:
                    break
                current = self.transition_game(int(current["id"]), target, "SCHEDULER", reason)
                changed.append(current)
        return changed

    def expire_quotes(self) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE bet_quotes SET status='EXPIRED' WHERE status='OPEN' AND expires_at<=?", (utc_now(),)
            )
            return cursor.rowcount

    def _wallet_snapshot(self, connection: sqlite3.Connection, user_id: str) -> dict:
        wallet = connection.execute("SELECT balance_paise FROM user_wallets WHERE user_id=?", (user_id,)).fetchone()
        if not wallet:
            raise LookupError("User wallet not found.")
        held_bets = connection.execute(
            "SELECT COALESCE(SUM(amount_paise),0) AS amount FROM wallet_holds WHERE user_id=? AND status='ACTIVE'", (user_id,)
        ).fetchone()["amount"]
        held_withdrawals = connection.execute(
            "SELECT COALESCE(SUM(amount_paise),0) AS amount FROM payment_requests WHERE user_id=? AND request_type='WITHDRAWAL' AND status='PENDING'", (user_id,)
        ).fetchone()["amount"]
        balance = int(wallet["balance_paise"])
        available = max(0, balance - int(held_bets) - int(held_withdrawals))
        return {
            "balance": rupees(balance), "available": rupees(available), "bet_exposure": rupees(held_bets),
            "pending_withdrawal": rupees(held_withdrawals),
        }

    def wallet(self, user_id: str) -> dict:
        self.platform.ensure_user(user_id)
        with self.connect() as connection:
            return self._wallet_snapshot(connection, user_id)

    def user_profile(self, user_id: str) -> dict:
        self.platform.ensure_user(user_id)
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM user_wallets WHERE user_id=?", (user_id,)).fetchone()
            wallet = self._wallet_snapshot(connection, user_id)
            return {
                "id": row["user_id"], "username": row["display_name"] or row["user_id"], "mobile": row["mobile"],
                "status": row["account_status"], "tier": row["vip_tier"], "wallet_balance": wallet["balance"],
                "available_balance": wallet["available"], "exposure": wallet["bet_exposure"],
            }

    def statement(self, user_id: str, limit: int = 100) -> list[dict]:
        limit = max(1, min(int(limit), 200))
        with self.connect() as connection:
            bet_rows = connection.execute(
                "SELECT reference,entry_type,amount_paise,balance_after_paise,metadata_json,created_at FROM account_ledger WHERE user_id=? ORDER BY id DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
            payment_rows = connection.execute(
                "SELECT id,entry_type,amount_paise,balance_after_paise,description,created_at FROM wallet_ledger WHERE user_id=? ORDER BY id DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        entries = [{
            "reference": row["reference"], "entry_type": row["entry_type"], "amount": rupees(row["amount_paise"]),
            "balance_after": rupees(row["balance_after_paise"]), "metadata": json.loads(row["metadata_json"] or "{}"),
            "description": row["entry_type"].replace("_", " ").title(), "created_at": row["created_at"],
        } for row in bet_rows]
        entries.extend({
            "reference": f"PAY-{row['id']}", "entry_type": row["entry_type"], "amount": rupees(row["amount_paise"]),
            "balance_after": rupees(row["balance_after_paise"]), "metadata": {}, "description": row["description"],
            "created_at": row["created_at"],
        } for row in payment_rows)
        return sorted(entries, key=lambda item: item["created_at"], reverse=True)[:limit]

    def _risk_check(self, connection: sqlite3.Connection, user_id: str, game_id: int, stake_paise: int, selected: str, potential_return_paise: int) -> tuple[bool, str, dict]:
        policy = self.risk_policy(connection)
        wallet = self._wallet_snapshot(connection, user_id)
        user_exposure = int(round(wallet["bet_exposure"] * 100))
        match_pool = int(connection.execute(
            "SELECT COALESCE(SUM(stake_paise),0) AS amount FROM cockfight_bets WHERE game_id=? AND status='PENDING'", (game_id,)
        ).fetchone()["amount"])
        outcome_liability = int(connection.execute(
            "SELECT COALESCE(SUM(potential_return_paise),0) AS amount FROM cockfight_bets WHERE game_id=? AND outcome=? AND status='PENDING'",
            (game_id, selected),
        ).fetchone()["amount"])
        one_minute_ago = (datetime.now(UTC) - timedelta(minutes=1)).isoformat(timespec="seconds")
        velocity = int(connection.execute(
            "SELECT COUNT(*) AS total FROM cockfight_bets WHERE user_id=? AND created_at>=?", (user_id, one_minute_ago)
        ).fetchone()["total"])
        metrics = {
            "available_paise": int(round(wallet["available"] * 100)), "user_exposure_paise": user_exposure,
            "match_pool_paise": match_pool, "outcome_liability_paise": outcome_liability,
            "bets_last_minute": velocity, "stake_paise": stake_paise,
        }
        checks = [
            (stake_paise <= metrics["available_paise"], "Insufficient available wallet balance."),
            (stake_paise <= int(policy["maximum_stake"]) * 100, "Stake exceeds the configured maximum."),
            (user_exposure + stake_paise <= int(policy["maximum_user_exposure"]) * 100, "User exposure limit reached."),
            (match_pool + stake_paise <= int(policy["maximum_match_pool"]) * 100, "Match pool limit reached."),
            (outcome_liability + potential_return_paise <= int(policy["maximum_outcome_liability"]) * 100, "Outcome liability limit reached."),
            (velocity < int(policy["maximum_bets_per_minute"]), "Betting velocity limit reached."),
        ]
        for passed, reason in checks:
            if not passed:
                return False, reason, metrics
        return True, "Risk checks passed.", metrics

    @staticmethod
    def _game_visible(connection, game) -> bool:
        if not game["visible"]:
            return False
        if not game["category_slug"]:
            return True
        category = connection.execute("SELECT kind, visible FROM game_categories WHERE slug=?", (game["category_slug"],)).fetchone()
        if not category:
            return True
        if category["kind"] == "CHINA_FEED":
            row = connection.execute("SELECT setting_value FROM admin_settings WHERE setting_key='china_feed'").fetchone()
            return bool(json.loads(row["setting_value"]).get("enabled")) if row else False
        return bool(category["visible"])

    def quote_bet(self, user_id: str, payload: dict) -> dict:
        self.advance_due_matches()
        self.platform.ensure_user(user_id)
        try:
            game_id = int(payload.get("matchId") or payload.get("match_id") or payload.get("game_id"))
        except (TypeError, ValueError):
            raise ValueError("Choose a valid match.") from None
        selected = outcome(payload.get("betTeam") or payload.get("bet_team") or payload.get("outcome"))
        policy = self.risk_policy()
        stake_paise = to_paise(payload.get("amount") or payload.get("stake"), int(policy["minimum_stake"]), int(policy["maximum_stake"]))
        self.platform.compliance.assert_allowed(user_id, "BET", stake_paise)
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            game = connection.execute("SELECT * FROM admin_games WHERE id=?", (game_id,)).fetchone()
            if not game:
                raise LookupError("Match not found.")
            if game["status"] != "BETTING_OPEN":
                raise ValueError("Betting is not open for this match.")
            if not self._game_visible(connection, game):
                raise ValueError("This match is not open to players.")
            odds = connection.execute("SELECT * FROM odds_snapshots WHERE game_id=? ORDER BY version DESC LIMIT 1", (game_id,)).fetchone()
            if not odds or odds["market_status"] != "OPEN":
                raise ValueError("This market is temporarily suspended.")
            accepted_odds = {"RED": odds["team_a_odds"], "DRAW": odds["draw_odds"], "BLUE": odds["team_b_odds"]}[selected]
            potential_return_paise = int((Decimal(stake_paise) * Decimal(str(accepted_odds))).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            passed, reason, metrics = self._risk_check(connection, user_id, game_id, stake_paise, selected, potential_return_paise)
            quote_id = f"Q-{secrets.token_hex(12).upper()}"
            connection.execute(
                "INSERT INTO risk_decisions(user_id,game_id,quote_id,decision,reason,metrics_json,created_at) VALUES(?,?,?,?,?,?,?)",
                (user_id, game_id, quote_id, "PASS" if passed else "REJECT", reason, json.dumps(metrics), utc_now()),
            )
            if not passed:
                connection.commit()
                raise ValueError(reason)
            now = datetime.now(UTC)
            expires = now + timedelta(seconds=int(policy["quote_ttl_seconds"]))
            connection.execute(
                """INSERT INTO bet_quotes(quote_id,user_id,game_id,outcome,stake_paise,accepted_odds,potential_return_paise,odds_version,status,expires_at,created_at)
                VALUES(?,?,?,?,?,?,?,?, 'OPEN',?,?)""",
                (quote_id, user_id, game_id, selected, stake_paise, accepted_odds, potential_return_paise, odds["version"], expires.isoformat(timespec="seconds"), now.isoformat(timespec="seconds")),
            )
            self._outbox(connection, "BET_QUOTE_ISSUED", "QUOTE", quote_id, 1, {"game_id": game_id, "odds_version": odds["version"], "expires_at": expires.isoformat(timespec="seconds")})
            return {
                "quote_id": quote_id, "match_id": game_id, "outcome": selected, "betTeam": OUTCOME_NUMBERS[selected],
                "stake": rupees(stake_paise), "odds": accepted_odds, "total_return": rupees(potential_return_paise),
                "odds_version": odds["version"], "expires_at": expires.isoformat(timespec="seconds"),
            }

    @staticmethod
    def _bet_dict(row: sqlite3.Row, title: str = "") -> dict:
        return {
            "id": row["ticket_ref"], "bet_id": row["id"], "match_id": row["game_id"], "match_title": title or f"Match {row['game_id']}",
            "outcome": row["outcome"], "bet_team": OUTCOME_NUMBERS[row["outcome"]], "team_name": row["outcome"].title(),
            "stake": rupees(row["stake_paise"]), "accepted_odds": row["accepted_odds"],
            "potential_return": rupees(row["potential_return_paise"]), "status": row["status"].lower(),
            "payout": rupees(row["payout_paise"]), "created_at": row["created_at"], "settled_at": row["settled_at"],
        }

    def place_bet(self, user_id: str, payload: dict) -> dict:
        self.advance_due_matches()
        quote_id = str(payload.get("quote_id") or "").strip()
        if not quote_id:
            raise ValueError("A valid server quote is required.")
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            quote = connection.execute("SELECT * FROM bet_quotes WHERE quote_id=?", (quote_id,)).fetchone()
            if not quote or quote["user_id"] != user_id:
                raise LookupError("Bet quote not found.")
            existing = connection.execute("SELECT b.*,g.title FROM cockfight_bets b JOIN admin_games g ON g.id=b.game_id WHERE b.quote_id=?", (quote_id,)).fetchone()
            if existing:
                result = self._bet_dict(existing, existing["title"])
                result["wallet"] = self._wallet_snapshot(connection, user_id)
                return result
            if quote["status"] != "OPEN":
                raise ValueError("This quote is no longer available.")
            self.platform.compliance.assert_allowed_in_transaction(connection, user_id, "BET", int(quote["stake_paise"]))
            if parse_timestamp(quote["expires_at"], "Quote expiry") <= datetime.now(UTC):
                connection.execute("UPDATE bet_quotes SET status='EXPIRED' WHERE quote_id=?", (quote_id,))
                raise ValueError("The quote expired. Request fresh odds.")
            game = connection.execute("SELECT * FROM admin_games WHERE id=?", (quote["game_id"],)).fetchone()
            if not game or game["status"] != "BETTING_OPEN":
                raise ValueError("Betting has closed for this match.")
            market = connection.execute("SELECT market_status FROM odds_snapshots WHERE game_id=? ORDER BY version DESC LIMIT 1", (quote["game_id"],)).fetchone()
            if not market or market["market_status"] != "OPEN":
                raise ValueError("This market is temporarily suspended.")
            passed, reason, metrics = self._risk_check(
                connection, user_id, quote["game_id"], quote["stake_paise"], quote["outcome"], quote["potential_return_paise"]
            )
            connection.execute(
                "INSERT INTO risk_decisions(user_id,game_id,quote_id,decision,reason,metrics_json,created_at) VALUES(?,?,?,?,?,?,?)",
                (user_id, quote["game_id"], quote_id, "PASS" if passed else "REJECT", reason, json.dumps(metrics), utc_now()),
            )
            if not passed:
                connection.commit()
                raise ValueError(reason)
            ticket_ref = f"BET-{datetime.now(UTC).strftime('%y%m%d')}-{secrets.token_hex(4).upper()}"
            now = utc_now()
            cursor = connection.execute(
                """INSERT INTO cockfight_bets(ticket_ref,quote_id,user_id,game_id,outcome,stake_paise,accepted_odds,potential_return_paise,odds_version,status,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,'PENDING',?)""",
                (ticket_ref, quote_id, user_id, quote["game_id"], quote["outcome"], quote["stake_paise"], quote["accepted_odds"], quote["potential_return_paise"], quote["odds_version"], now),
            )
            bet_id = cursor.lastrowid
            connection.execute(
                "INSERT INTO wallet_holds(user_id,bet_id,amount_paise,status,created_at) VALUES(?,?,?,'ACTIVE',?)",
                (user_id, bet_id, quote["stake_paise"], now),
            )
            connection.execute("UPDATE bet_quotes SET status='CONSUMED',consumed_at=? WHERE quote_id=?", (now, quote_id))
            self._outbox(connection, "BET_ACCEPTED", "BET", str(bet_id), 1, {"ticket_ref": ticket_ref, "game_id": quote["game_id"], "outcome": quote["outcome"], "stake": rupees(quote["stake_paise"])})
            row = connection.execute("SELECT * FROM cockfight_bets WHERE id=?", (bet_id,)).fetchone()
            result = self._bet_dict(row, game["title"])
            result["wallet"] = self._wallet_snapshot(connection, user_id)
            return result

    def list_bets(self, user_id: str) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT b.*,g.title FROM cockfight_bets b JOIN admin_games g ON g.id=b.game_id WHERE b.user_id=? ORDER BY b.id DESC",
                (user_id,),
            ).fetchall()
            return [self._bet_dict(row, row["title"]) for row in rows]

    def declare_result(self, game_id: int, result: object, actor: str = "ADMIN") -> dict:
        declared = outcome(result, allow_cancelled=True)
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            game = connection.execute("SELECT * FROM admin_games WHERE id=?", (game_id,)).fetchone()
            if not game:
                raise LookupError("Game not found.")
            if game["status"] == "SETTLED":
                if game["result"] == declared:
                    return dict(game)
                raise ValueError("A settled result is immutable.")
            if game["result"] == declared and game["status"] in {"AWAITING_RESULT", "CANCELLED"}:
                return dict(game)
            if game["status"] not in {"DRAFT", "SCHEDULED", "BETTING_OPEN", "BETTING_CLOSED", "LIVE", "AWAITING_RESULT"}:
                raise ValueError("The match is not available for result declaration or cancellation.")
            if declared != "CANCELLED" and game["status"] not in {"LIVE", "AWAITING_RESULT", "BETTING_CLOSED"}:
                raise ValueError("A winner can be declared only after betting has closed.")
            if game["result"] and game["result"] != declared:
                raise ValueError("A different result is already awaiting settlement.")
            previous = game["status"]
            now = utc_now()
            target = "CANCELLED" if declared == "CANCELLED" else "AWAITING_RESULT"
            if target == "CANCELLED":
                latest = connection.execute("SELECT * FROM odds_snapshots WHERE game_id=? ORDER BY version DESC LIMIT 1", (game_id,)).fetchone()
                if latest and latest["market_status"] != "SUSPENDED":
                    self.publish_odds_in_transaction(connection, game, latest, "SUSPENDED", "Match cancelled", actor)
            connection.execute(
                "UPDATE admin_games SET result=?,status=?,result_declared_at=?,state_version=state_version+1,updated_at=? WHERE id=?",
                (declared, target, now, now, game_id),
            )
            self._record_match_event(connection, game_id, "RESULT_DECLARED", previous, target, {"result": declared}, actor)
            self.platform._audit(connection, "Settlement", "Result declared", game["title"], declared)
            return dict(connection.execute("SELECT * FROM admin_games WHERE id=?", (game_id,)).fetchone())

    def settle_game(self, game_id: int, actor: str = "ADMIN") -> dict:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            game = connection.execute("SELECT * FROM admin_games WHERE id=?", (game_id,)).fetchone()
            if not game:
                raise LookupError("Game not found.")
            if game["status"] == "SETTLED":
                return self.settlement_summary_in_connection(connection, game_id)
            if not game["result"]:
                raise ValueError("Declare the official result before settlement.")
            if game["status"] not in {"AWAITING_RESULT", "CANCELLED"}:
                raise ValueError("The match is not ready for settlement.")
            bets = connection.execute("SELECT * FROM cockfight_bets WHERE game_id=? AND status='PENDING' ORDER BY id", (game_id,)).fetchall()
            now = utc_now()
            for bet in bets:
                wallet = connection.execute("SELECT balance_paise FROM user_wallets WHERE user_id=?", (bet["user_id"],)).fetchone()
                balance = int(wallet["balance_paise"])
                reference = f"BET:{bet['id']}:SETTLEMENT"
                if game["result"] == "CANCELLED":
                    status, payout, delta, entry_type, hold_status = "REFUNDED", bet["stake_paise"], 0, "BET_REFUND", "RELEASED"
                elif bet["outcome"] == game["result"]:
                    status, payout = "WON", bet["potential_return_paise"]
                    delta, entry_type, hold_status = payout - bet["stake_paise"], "BET_WIN", "RELEASED"
                else:
                    status, payout, delta, entry_type, hold_status = "LOST", 0, -bet["stake_paise"], "BET_LOSS", "CONSUMED"
                new_balance = balance + int(delta)
                if new_balance < 0:
                    raise RuntimeError("Wallet invariant failed during settlement.")
                connection.execute("UPDATE user_wallets SET balance_paise=?,updated_at=? WHERE user_id=?", (new_balance, now, bet["user_id"]))
                connection.execute(
                    "UPDATE cockfight_bets SET status=?,payout_paise=?,settlement_reference=?,settled_at=? WHERE id=?",
                    (status, payout, reference, now, bet["id"]),
                )
                connection.execute(
                    "UPDATE wallet_holds SET status=?,released_at=? WHERE bet_id=? AND status='ACTIVE'",
                    (hold_status, now, bet["id"]),
                )
                connection.execute(
                    "INSERT OR IGNORE INTO account_ledger(user_id,reference,entry_type,amount_paise,balance_after_paise,metadata_json,created_at) VALUES(?,?,?,?,?,?,?)",
                    (bet["user_id"], reference, entry_type, delta, new_balance, json.dumps({"game_id": game_id, "ticket_ref": bet["ticket_ref"], "result": game["result"]}), now),
                )
                self._outbox(connection, "BET_SETTLED", "BET", str(bet["id"]), 2, {"ticket_ref": bet["ticket_ref"], "status": status, "payout": rupees(payout)})
                self.platform.operations.notify(
                    connection, audience="USER", user_id=bet["user_id"], event_type="BET_SETTLED",
                    severity="SUCCESS" if status == "WON" else "INFO",
                    title=f"Ticket {status.lower()}",
                    message=f"{bet['ticket_ref']} settled as {status.lower()} for {game['title']}.",
                    action_route="#bets", dedupe_key=f"user:{bet['user_id']}:bet-settled:{bet['ticket_ref']}",
                )
            previous = game["status"]
            connection.execute(
                "UPDATE admin_games SET status='SETTLED',settled_at=?,state_version=state_version+1,updated_at=? WHERE id=?",
                (now, now, game_id),
            )
            self._record_match_event(connection, game_id, "MATCH_SETTLED", previous, "SETTLED", {"result": game["result"], "bets": len(bets)}, actor)
            self.platform._audit(connection, "Settlement", "Match settled", game["title"], f"{game['result']} · {len(bets)} bets")
            return self.settlement_summary_in_connection(connection, game_id)

    def settlement_summary_in_connection(self, connection: sqlite3.Connection, game_id: int) -> dict:
        game = connection.execute("SELECT * FROM admin_games WHERE id=?", (game_id,)).fetchone()
        totals = connection.execute(
            """SELECT COUNT(*) AS bets,COALESCE(SUM(stake_paise),0) AS stake,COALESCE(SUM(payout_paise),0) AS payout,
            SUM(CASE WHEN status='WON' THEN 1 ELSE 0 END) AS won,SUM(CASE WHEN status='LOST' THEN 1 ELSE 0 END) AS lost,
            SUM(CASE WHEN status='REFUNDED' THEN 1 ELSE 0 END) AS refunded FROM cockfight_bets WHERE game_id=?""",
            (game_id,),
        ).fetchone()
        return {
            "game_id": game_id, "status": game["status"], "result": game["result"], "settled_at": game["settled_at"],
            "bets": int(totals["bets"] or 0), "total_stake": rupees(totals["stake"]), "total_payout": rupees(totals["payout"]),
            "won": int(totals["won"] or 0), "lost": int(totals["lost"] or 0), "refunded": int(totals["refunded"] or 0),
        }

    def history(self, limit: int = 20) -> list[dict]:
        limit = max(1, min(int(limit), 100))
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM admin_games WHERE status IN ('SETTLED','CANCELLED') ORDER BY COALESCE(settled_at,result_declared_at,updated_at) DESC,id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [{
                "id": row["id"], "fightNumber": row["match_number"] or row["id"], "matchNumber": row["match_number"] or row["id"], "title": row["title"],
                "source": row["source"], "external_ref": row["external_ref"],
                "result": row["result"], "winTeam": OUTCOME_NUMBERS.get(row["result"], 4), "status": row["status"],
                "result_declared_at": row["result_declared_at"], "settled_at": row["settled_at"],
            } for row in rows]

    def events(self, after: int = 0, limit: int = 100) -> list[dict]:
        limit = max(1, min(int(limit), 200))
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM engine_events WHERE id>? ORDER BY id ASC LIMIT ?", (max(0, int(after)), limit)
            ).fetchall()
            return [{
                "id": row["id"], "event_type": row["event_type"], "aggregate_type": row["aggregate_type"],
                "aggregate_id": row["aggregate_id"], "version": row["aggregate_version"],
                "payload": json.loads(row["payload_json"] or "{}"), "created_at": row["created_at"],
            } for row in rows]

    def health(self) -> dict:
        with self.connect() as connection:
            pending_quotes = connection.execute("SELECT COUNT(*) AS total FROM bet_quotes WHERE status='OPEN'").fetchone()["total"]
            pending_bets = connection.execute("SELECT COUNT(*) AS total FROM cockfight_bets WHERE status='PENDING'").fetchone()["total"]
            last_event = connection.execute("SELECT COALESCE(MAX(id),0) AS id FROM engine_events").fetchone()["id"]
        return {
            "status": "ok", "scheduler": bool(self._scheduler and self._scheduler.is_alive()),
            "pending_quotes": int(pending_quotes), "pending_bets": int(pending_bets), "last_event_id": int(last_event),
        }
