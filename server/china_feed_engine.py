"""China 24/7 automatic cockfight feed.

Polls the upstream match service, mirrors each upstream fight into a local
``admin_games`` row (source ``CHINA_FEED``), drives the normal match lifecycle
from the upstream betting flag, and declares/settles results through the
authoritative ``CockfightEngine`` so wallets, ledgers, and notifications are
handled exactly like a manually operated match. Missed results are recovered
from the upstream history endpoint.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from cockfight_engine import OUTCOME_ALIASES, utc_now

UTC = timezone.utc
SETTING_KEY = "china_feed"
SOURCE = "CHINA_FEED"
CATEGORY_SLUG = "china-24-7"
DEFAULT_INFO_URL = "https://api.cockfightbet.xyz/api/cf/game/info?gameId=10001"
DEFAULT_HISTORY_URL = "https://api.cockfightbet.cc/api/cf/game/task/history?pageNum=1&pageSize=10"
DEFAULT_SETTINGS = {
    "enabled": False,
    "info_url": DEFAULT_INFO_URL,
    "history_url": DEFAULT_HISTORY_URL,
    "poll_seconds": 3,
    "request_timeout_seconds": 8,
    "arena": "China 24/7 Arena",
    "title_prefix": "China 24/7",
    "team_a_name": "Meron",
    "team_b_name": "Wala",
    "team_a_odds": 1.85,
    "draw_odds": 6.0,
    "team_b_odds": 1.85,
    "stream_url_override": "",
    "thumbnail_url": "",
    "feature_current_match": True,
    "suspend_after_failures": 3,
}
NUMERIC_LIMITS = {
    "poll_seconds": (2, 60),
    "request_timeout_seconds": (3, 30),
    "suspend_after_failures": (1, 20),
}
ODDS_KEYS = ("team_a_odds", "draw_odds", "team_b_odds")
ACTIVE_STATUSES = ("SCHEDULED", "BETTING_OPEN", "BETTING_CLOSED", "LIVE", "AWAITING_RESULT")


class FeedError(RuntimeError):
    """Raised when the upstream feed cannot be read or parsed."""


def _http_url(value: object, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{label} must be an http(s) URL.")
    return text


def fetch_json(url: str, timeout: int) -> dict:
    """Fetch and decode a JSON document; split out so tests can stub it."""
    request = urllib.request.Request(url, headers={"User-Agent": "RoosterRun/1.0", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(2 * 1024 * 1024)
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise FeedError(f"Feed request failed: {error}") from error
    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise FeedError("Feed returned invalid JSON.") from error
    if not isinstance(data, dict):
        raise FeedError("Feed returned an unexpected document.")
    return data


class ChinaFeedEngine:
    def __init__(self, platform_service, fetcher=fetch_json):
        self.platform = platform_service
        self.fetch = fetcher
        self._stop_event = threading.Event()
        self._worker: threading.Thread | None = None
        self._lock = threading.Lock()
        self._initialize()
        self._refresh_frame_origins()

    def _refresh_frame_origins(self) -> None:
        settings = self.settings()
        state = self.state()
        origins = set()
        for url in (settings.get("stream_url_override", ""), state.get("live_url", "")):
            parsed = urlparse(str(url or ""))
            if parsed.scheme in {"http", "https"} and parsed.netloc:
                origins.add(f"{parsed.scheme}://{parsed.netloc}")
        self.frame_origins = sorted(origins)

    # ------------------------------------------------------------------ setup
    def connect(self) -> sqlite3.Connection:
        return self.platform.connect()

    @property
    def cockfight(self):
        return self.platform.cockfight

    def _initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS china_feed_state (
                    id INTEGER PRIMARY KEY,
                    current_ref_id TEXT NOT NULL DEFAULT '',
                    current_game_id INTEGER,
                    match_number TEXT NOT NULL DEFAULT '',
                    allow_betting INTEGER NOT NULL DEFAULT 0,
                    live_url TEXT NOT NULL DEFAULT '',
                    last_polled_at TEXT NOT NULL DEFAULT '',
                    last_success_at TEXT NOT NULL DEFAULT '',
                    last_error TEXT NOT NULL DEFAULT '',
                    consecutive_failures INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS china_feed_matches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ref_id TEXT NOT NULL UNIQUE,
                    match_number TEXT NOT NULL DEFAULT '',
                    game_id INTEGER NOT NULL,
                    live_url TEXT NOT NULL DEFAULT '',
                    win_team INTEGER NOT NULL DEFAULT 0,
                    result_source TEXT NOT NULL DEFAULT '',
                    betting_opened_at TEXT NOT NULL DEFAULT '',
                    betting_closed_at TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS china_feed_matches_game_idx ON china_feed_matches(game_id);
                """
            )
            game_columns = {row["name"] for row in connection.execute("PRAGMA table_info(admin_games)").fetchall()}
            for column, definition in {
                "source": "TEXT NOT NULL DEFAULT 'MANUAL'",
                "external_ref": "TEXT NOT NULL DEFAULT ''",
                "match_number": "TEXT NOT NULL DEFAULT ''",
            }.items():
                if column not in game_columns:
                    connection.execute(f"ALTER TABLE admin_games ADD COLUMN {column} {definition}")
            connection.execute(
                "INSERT OR IGNORE INTO china_feed_state(id,updated_at) VALUES(1,?)", (utc_now(),)
            )
            connection.execute(
                "INSERT OR IGNORE INTO admin_settings(setting_key,setting_value,updated_at) VALUES(?,?,?)",
                (SETTING_KEY, json.dumps(DEFAULT_SETTINGS), utc_now()),
            )

    # --------------------------------------------------------------- settings
    def settings(self, connection: sqlite3.Connection | None = None) -> dict:
        owns = connection is None
        if owns:
            connection = self.connect()
        try:
            row = connection.execute("SELECT setting_value FROM admin_settings WHERE setting_key=?", (SETTING_KEY,)).fetchone()
        finally:
            if owns:
                connection.close()
        stored = json.loads(row["setting_value"] or "{}") if row else {}
        return {**DEFAULT_SETTINGS, **stored}

    def update_settings(self, payload: dict, actor: str = "ADMIN") -> dict:
        current = self.settings()
        updated = dict(current)
        for key in ("enabled", "feature_current_match"):
            if key in payload:
                updated[key] = bool(payload[key]) if not isinstance(payload[key], str) else payload[key].strip().lower() in {"1", "true", "yes", "on"}
        for key, (minimum, maximum) in NUMERIC_LIMITS.items():
            if key in payload:
                try:
                    value = int(payload[key])
                except (TypeError, ValueError):
                    raise ValueError(f"{key.replace('_', ' ').title()} must be a number.") from None
                if value < minimum or value > maximum:
                    raise ValueError(f"{key.replace('_', ' ').title()} must be between {minimum} and {maximum}.")
                updated[key] = value
        for key in ODDS_KEYS:
            if key in payload:
                try:
                    value = round(float(payload[key]), 2)
                except (TypeError, ValueError):
                    raise ValueError("Enter valid decimal odds.") from None
                if value < 1.01 or value > 100:
                    raise ValueError("Odds must be between 1.01 and 100.")
                updated[key] = value
        for key, label, maximum in (
            ("arena", "Arena", 60), ("title_prefix", "Title prefix", 40),
            ("team_a_name", "Red corner name", 50), ("team_b_name", "Blue corner name", 50),
        ):
            if key in payload:
                text = str(payload[key] or "").strip()
                if not text or len(text) > maximum:
                    raise ValueError(f"{label} must be 1-{maximum} characters.")
                updated[key] = text
        for key, label in (("info_url", "Match info URL"), ("history_url", "History URL"), ("stream_url_override", "Stream override URL"), ("thumbnail_url", "Thumbnail URL")):
            if key in payload:
                updated[key] = _http_url(payload[key], label)
        if not updated["info_url"] or not updated["history_url"]:
            raise ValueError("Match info and history URLs are required.")
        with self.connect() as connection:
            connection.execute(
                "UPDATE admin_settings SET setting_value=?,updated_at=? WHERE setting_key=?",
                (json.dumps(updated), utc_now(), SETTING_KEY),
            )
            self.platform._audit(connection, "China 24/7", "Feed settings updated", "Auto-match feed", "enabled" if updated["enabled"] else "disabled")
        if current["enabled"] and not updated["enabled"]:
            self._disable_current_match("Feed disabled by administrator")
        self._refresh_frame_origins()
        return updated

    # ------------------------------------------------------------------ state
    def state(self, connection: sqlite3.Connection | None = None) -> dict:
        owns = connection is None
        if owns:
            connection = self.connect()
        try:
            row = connection.execute("SELECT * FROM china_feed_state WHERE id=1").fetchone()
        finally:
            if owns:
                connection.close()
        data = dict(row) if row else {}
        data["allow_betting"] = bool(data.get("allow_betting"))
        return data

    def _update_state(self, connection: sqlite3.Connection, **fields) -> None:
        fields["updated_at"] = utc_now()
        assignments = ",".join(f"{key}=?" for key in fields)
        connection.execute(f"UPDATE china_feed_state SET {assignments} WHERE id=1", tuple(fields.values()))

    def _current_game(self, connection: sqlite3.Connection) -> sqlite3.Row | None:
        state = connection.execute("SELECT current_game_id FROM china_feed_state WHERE id=1").fetchone()
        if not state or not state["current_game_id"]:
            return None
        return connection.execute("SELECT * FROM admin_games WHERE id=?", (state["current_game_id"],)).fetchone()

    def current(self) -> dict:
        """Public view used by the player: feed status plus the active mirrored match."""
        settings = self.settings()
        with self.connect() as connection:
            state = self.state(connection)
            game = self._current_game(connection)
            feed_match = None
            if game:
                feed_match = connection.execute("SELECT * FROM china_feed_matches WHERE game_id=?", (game["id"],)).fetchone()
        stale = self._is_stale(state, settings)
        return {
            "enabled": bool(settings["enabled"]),
            "healthy": bool(settings["enabled"]) and not stale and state.get("consecutive_failures", 0) < settings["suspend_after_failures"],
            "match_number": state.get("match_number", ""),
            "ref_id": state.get("current_ref_id", ""),
            "allow_betting": state.get("allow_betting", False),
            "live_url": self._playback_url(settings, state.get("live_url", "")),
            "last_success_at": state.get("last_success_at", ""),
            "last_error": state.get("last_error", ""),
            "match": self.platform.game_to_dict(game) if game else None,
            "feed_match": dict(feed_match) if feed_match else None,
        }

    def admin_view(self) -> dict:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT m.*, g.status AS game_status, g.result AS game_result, g.title AS game_title
                FROM china_feed_matches m LEFT JOIN admin_games g ON g.id=m.game_id
                ORDER BY m.id DESC LIMIT 30"""
            ).fetchall()
        return {
            "settings": self.settings(),
            "state": self.state(),
            "current": self.current(),
            "worker": bool(self._worker and self._worker.is_alive()),
            "recent_matches": [dict(row) for row in rows],
        }

    @staticmethod
    def _is_stale(state: dict, settings: dict) -> bool:
        last = str(state.get("last_success_at") or "")
        if not last:
            return True
        try:
            parsed = datetime.fromisoformat(last.replace("Z", "+00:00"))
        except ValueError:
            return True
        return datetime.now(UTC) - parsed > timedelta(seconds=max(30, settings["poll_seconds"] * 6))

    @staticmethod
    def _playback_url(settings: dict, live_url: str) -> str:
        return settings.get("stream_url_override") or live_url or ""

    # ----------------------------------------------------------------- worker
    def start_worker(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        self._stop_event.clear()

        def run() -> None:
            while not self._stop_event.is_set():
                try:
                    settings = self.settings()
                    if settings["enabled"]:
                        self.poll_once(settings)
                    interval = settings["poll_seconds"]
                except Exception:
                    interval = DEFAULT_SETTINGS["poll_seconds"]
                self._stop_event.wait(interval)

        self._worker = threading.Thread(target=run, name="roosterrun-china-feed", daemon=True)
        self._worker.start()

    def stop_worker(self) -> None:
        self._stop_event.set()
        if self._worker and self._worker.is_alive():
            self._worker.join(timeout=3)

    # ------------------------------------------------------------------- poll
    def poll_once(self, settings: dict | None = None, force: bool = False) -> dict:
        """One synchronous feed tick. Safe to call from the worker, the admin API, or tests."""
        settings = settings or self.settings()
        if not settings["enabled"] and not force:
            return {"skipped": "disabled"}
        with self._lock:
            return self._poll_locked(settings)

    def _poll_locked(self, settings: dict) -> dict:
        now = utc_now()
        try:
            payload = self.fetch(settings["info_url"], settings["request_timeout_seconds"])
            data = payload.get("resultData") if isinstance(payload.get("resultData"), dict) else None
            if not payload.get("success", True) or not data or not data.get("id"):
                raise FeedError("Feed did not include a current match.")
        except FeedError as error:
            return self._record_failure(settings, str(error), now)

        ref_id = str(data.get("id"))
        match_number = str(data.get("taskNum") or "")
        allow_betting = bool(data.get("allowBetting"))
        live_url = str(data.get("liveUrl") or "")
        win_team = self._win_team(data.get("winTeam"))
        last_issue = data.get("lastIssueInfo") if isinstance(data.get("lastIssueInfo"), dict) else {}
        actions: list[str] = []

        if last_issue.get("id") and self._win_team(last_issue.get("winTeam")):
            if self._apply_result(str(last_issue["id"]), self._win_team(last_issue.get("winTeam")), "CURRENT"):
                actions.append(f"settled {last_issue['id']}")

        with self.connect() as connection:
            state = self.state(connection)
        if state.get("current_ref_id") != ref_id:
            self._recover_missed_results(settings)
            game_id = self._open_match(settings, ref_id, match_number, live_url, allow_betting)
            actions.append(f"opened {ref_id} as game {game_id}")
        else:
            changed = self._sync_current(settings, ref_id, allow_betting, live_url)
            actions.extend(changed)

        if win_team:
            if self._apply_result(ref_id, win_team, "CURRENT"):
                actions.append(f"settled {ref_id}")

        with self.connect() as connection:
            self._update_state(
                connection, current_ref_id=ref_id, match_number=match_number, allow_betting=1 if allow_betting else 0,
                live_url=live_url, last_polled_at=now, last_success_at=now, last_error="", consecutive_failures=0,
            )
        self._refresh_frame_origins()
        return {"ref_id": ref_id, "match_number": match_number, "allow_betting": allow_betting, "actions": actions}

    def _record_failure(self, settings: dict, message: str, now: str) -> dict:
        with self.connect() as connection:
            state = self.state(connection)
            failures = int(state.get("consecutive_failures", 0)) + 1
            self._update_state(connection, last_polled_at=now, last_error=message[:300], consecutive_failures=failures)
            game = self._current_game(connection)
        suspended = False
        if game and failures >= settings["suspend_after_failures"] and game["status"] == "BETTING_OPEN":
            self.cockfight.transition_game(int(game["id"]), "BETTING_CLOSED", SOURCE, "Upstream feed unavailable; market suspended")
            suspended = True
        return {"error": message, "consecutive_failures": failures, "market_suspended": suspended}

    @staticmethod
    def _win_team(value: object) -> int:
        try:
            number = int(value or 0)
        except (TypeError, ValueError):
            return 0
        return number if number in (1, 2, 3, 4) else 0

    # --------------------------------------------------------------- lifecycle
    def _open_match(self, settings: dict, ref_id: str, match_number: str, live_url: str, allow_betting: bool) -> int:
        now_dt = datetime.now(UTC)
        now = now_dt.isoformat(timespec="seconds")
        far = (now_dt + timedelta(days=365)).isoformat(timespec="seconds")
        title = f"{settings['title_prefix']} · Match #{match_number or ref_id}"
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute("SELECT game_id FROM china_feed_matches WHERE ref_id=?", (ref_id,)).fetchone()
            if existing:
                game_id = int(existing["game_id"])
            else:
                if settings["feature_current_match"]:
                    connection.execute("UPDATE admin_games SET featured=0 WHERE featured=1")
                cursor = connection.execute(
                    """INSERT INTO admin_games(title,arena,status,betting_opens_at,scheduled_at,betting_closes_at,team_a_name,team_a_odds,draw_odds,team_b_name,team_b_odds,
                    stream_type,stream_url,thumbnail_url,result,featured,source,external_ref,match_number,category_slug,visible,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        title, settings["arena"], "SCHEDULED", now, far, far,
                        settings["team_a_name"], settings["team_a_odds"], settings["draw_odds"], settings["team_b_name"], settings["team_b_odds"],
                        "IFRAME", self._playback_url(settings, live_url), settings["thumbnail_url"], "",
                        1 if settings["feature_current_match"] else 0, SOURCE, ref_id, match_number, CATEGORY_SLUG, 1, now, now,
                    ),
                )
                game_id = int(cursor.lastrowid)
                connection.execute(
                    "INSERT INTO china_feed_matches(ref_id,match_number,game_id,live_url,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                    (ref_id, match_number, game_id, live_url, now, now),
                )
                self.platform._audit(connection, "China 24/7", "Match mirrored", title, f"Upstream {ref_id}")
            self._update_state(connection, current_ref_id=ref_id, current_game_id=game_id, match_number=match_number)
        self.cockfight.sync_game(game_id, SOURCE, "")
        if allow_betting:
            self._transition(game_id, "BETTING_OPEN", "Upstream betting open")
            with self.connect() as connection:
                connection.execute("UPDATE china_feed_matches SET betting_opened_at=?,updated_at=? WHERE ref_id=?", (now, now, ref_id))
                connection.execute("UPDATE admin_games SET betting_opens_at=? WHERE id=?", (now, game_id))
        else:
            self._transition(game_id, "BETTING_CLOSED", "Upstream betting closed")
            self._transition(game_id, "LIVE", "Upstream fight in progress")
            with self.connect() as connection:
                connection.execute("UPDATE china_feed_matches SET betting_closed_at=?,updated_at=? WHERE ref_id=?", (now, now, ref_id))
                connection.execute("UPDATE admin_games SET betting_closes_at=?,scheduled_at=? WHERE id=?", (now, now, game_id))
        return game_id

    def _sync_current(self, settings: dict, ref_id: str, allow_betting: bool, live_url: str) -> list[str]:
        changes: list[str] = []
        with self.connect() as connection:
            game = self._current_game(connection)
            if not game:
                return changes
            playback = self._playback_url(settings, live_url)
            if playback and playback != game["stream_url"]:
                connection.execute("UPDATE admin_games SET stream_url=?,updated_at=? WHERE id=?", (playback, utc_now(), game["id"]))
                connection.execute("UPDATE china_feed_matches SET live_url=?,updated_at=? WHERE ref_id=?", (live_url, utc_now(), ref_id))
                changes.append("stream updated")
            status = game["status"]
            game_id = int(game["id"])
        now = utc_now()
        if status == "SCHEDULED" and allow_betting:
            self._transition(game_id, "BETTING_OPEN", "Upstream betting open")
            with self.connect() as connection:
                connection.execute("UPDATE china_feed_matches SET betting_opened_at=?,updated_at=? WHERE ref_id=?", (now, now, ref_id))
            changes.append("betting opened")
        elif status == "BETTING_OPEN" and not allow_betting:
            self._transition(game_id, "BETTING_CLOSED", "Upstream betting closed")
            self._transition(game_id, "LIVE", "Upstream fight in progress")
            with self.connect() as connection:
                connection.execute("UPDATE china_feed_matches SET betting_closed_at=?,updated_at=? WHERE ref_id=?", (now, now, ref_id))
                connection.execute("UPDATE admin_games SET betting_closes_at=?,scheduled_at=? WHERE id=?", (now, now, game_id))
            changes.append("betting closed")
        return changes

    def _transition(self, game_id: int, target: str, reason: str) -> None:
        try:
            self.cockfight.transition_game(game_id, target, SOURCE, reason)
        except ValueError:
            # Already past this state (e.g. result arrived first); the lifecycle guard wins.
            pass

    def _apply_result(self, ref_id: str, win_team: int, source: str) -> bool:
        with self.connect() as connection:
            feed_match = connection.execute("SELECT * FROM china_feed_matches WHERE ref_id=?", (ref_id,)).fetchone()
            if not feed_match:
                return False
            game = connection.execute("SELECT * FROM admin_games WHERE id=?", (feed_match["game_id"],)).fetchone()
            if not game:
                return False
            if game["status"] in {"SETTLED", "CANCELLED"}:
                if feed_match["win_team"] == 0:
                    connection.execute("UPDATE china_feed_matches SET win_team=?,result_source=?,updated_at=? WHERE ref_id=?", (win_team, source, utc_now(), ref_id))
                return False
            game_id = int(game["id"])
            status = game["status"]
        result = OUTCOME_ALIASES[win_team]
        if result != "CANCELLED":
            if status in {"SCHEDULED", "BETTING_OPEN"}:
                self._transition(game_id, "BETTING_CLOSED", "Upstream result received")
            if status in {"SCHEDULED", "BETTING_OPEN", "BETTING_CLOSED"}:
                self._transition(game_id, "LIVE", "Upstream result received")
        try:
            self.cockfight.declare_result(game_id, result, SOURCE)
            self.cockfight.settle_game(game_id, SOURCE)
        except ValueError as error:
            with self.connect() as connection:
                self._update_state(connection, last_error=f"Result for {ref_id} rejected: {error}"[:300])
            return False
        with self.connect() as connection:
            connection.execute(
                "UPDATE china_feed_matches SET win_team=?,result_source=?,updated_at=? WHERE ref_id=?",
                (win_team, source, utc_now(), ref_id),
            )
        return True

    def _recover_missed_results(self, settings: dict) -> int:
        with self.connect() as connection:
            unresolved = connection.execute(
                """SELECT m.ref_id FROM china_feed_matches m JOIN admin_games g ON g.id=m.game_id
                WHERE m.win_team=0 AND g.status NOT IN ('SETTLED','CANCELLED')"""
            ).fetchall()
        if not unresolved:
            return 0
        try:
            payload = self.fetch(settings["history_url"], settings["request_timeout_seconds"])
        except FeedError:
            return 0
        result_data = payload.get("resultData") if isinstance(payload.get("resultData"), dict) else {}
        history = {}
        for item in result_data.get("list", []) or []:
            if isinstance(item, dict) and item.get("id"):
                history[str(item["id"])] = self._win_team(item.get("winTeam"))
        newest_ref = max((int(ref) for ref in history if ref.isdigit()), default=0)
        recovered = 0
        for row in unresolved:
            ref_id = str(row["ref_id"])
            win_team = history.get(ref_id, 0)
            if not win_team and ref_id.isdigit() and 0 < int(ref_id) < newest_ref and ref_id != self.state().get("current_ref_id"):
                # Upstream skipped this match entirely (later matches already resolved): void and refund.
                win_team = 4
            if win_team and self._apply_result(ref_id, win_team, "HISTORY" if history.get(ref_id) else "VOIDED"):
                recovered += 1
        return recovered

    def recover(self) -> int:
        return self._recover_missed_results(self.settings())

    def _disable_current_match(self, reason: str) -> None:
        with self.connect() as connection:
            game = self._current_game(connection)
        if game and game["status"] in ACTIVE_STATUSES and not game["result"]:
            self.cockfight.declare_result(int(game["id"]), "CANCELLED", SOURCE)
            self.cockfight.settle_game(int(game["id"]), SOURCE)
        with self.connect() as connection:
            self._update_state(connection, current_ref_id="", current_game_id=None, match_number="", allow_betting=0, last_error=reason)

    def health(self) -> dict:
        settings = self.settings()
        state = self.state()
        return {
            "status": "ok" if not settings["enabled"] or (state.get("consecutive_failures", 0) < settings["suspend_after_failures"] and not self._is_stale(state, settings)) else "attention",
            "enabled": bool(settings["enabled"]),
            "worker": bool(self._worker and self._worker.is_alive()),
            "current_ref_id": state.get("current_ref_id", ""),
            "match_number": state.get("match_number", ""),
            "allow_betting": state.get("allow_betting", False),
            "consecutive_failures": int(state.get("consecutive_failures", 0)),
            "last_success_at": state.get("last_success_at", ""),
            "last_error": state.get("last_error", ""),
        }
