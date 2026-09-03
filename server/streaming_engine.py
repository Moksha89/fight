"""Durable streaming control plane for RoosterRun cockfight broadcasts.

The media plane (SRS or another WHIP/WHEP server) moves audio and video. This
module owns the security and operations around that plane: short-lived
publisher sessions, mobile pairing, playback routing, health samples, expiry,
and ordered engine events.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.parse import parse_qs
from urllib.parse import quote
from urllib import request as urlrequest


UTC = timezone.utc
ACTIVE_STATES = {"CREATED", "PAIRED", "READY", "LIVE", "DEGRADED"}
TERMINAL_STATES = {"STOPPED", "FAILED", "EXPIRED"}


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def parse_time(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def secret_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def bounded_number(value: object, minimum: float, maximum: float, default: float = 0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return round(max(minimum, min(maximum, number)), 2)


class StreamingEngine:
    """Streaming session, authorization, playback, and health engine."""

    def __init__(self, platform_service):
        self.platform = platform_service
        self.whip_base = os.environ.get("ROOSTERRUN_WHIP_BASE_URL", "").strip().rstrip("/")
        self.whep_base = os.environ.get("ROOSTERRUN_WHEP_BASE_URL", "").strip().rstrip("/")
        self.hls_base = os.environ.get("ROOSTERRUN_HLS_BASE_URL", "").strip().rstrip("/")
        self.recording_base = os.environ.get("ROOSTERRUN_RECORDING_BASE_URL", "").strip().rstrip("/")
        self.recording_extension = os.environ.get("ROOSTERRUN_RECORDING_EXTENSION", "flv").strip().lower()
        if self.recording_extension not in {"flv", "mp4"}:
            raise RuntimeError("ROOSTERRUN_RECORDING_EXTENSION must be flv or mp4.")
        self.hook_secret = os.environ.get("ROOSTERRUN_SRS_HOOK_SECRET", "").strip()
        self.previous_hook_secret = os.environ.get("ROOSTERRUN_SRS_HOOK_SECRET_PREVIOUS", "").strip()
        self.media_health_url = os.environ.get("ROOSTERRUN_SRS_API_URL", "").strip()
        self.media_plane_reachable = not bool(self.media_health_url)
        self.last_media_probe_at = ""
        self.media_probe_failures = 0
        self._stop_event = threading.Event()
        self._monitor: threading.Thread | None = None
        self._initialize()

    def connect(self) -> sqlite3.Connection:
        return self.platform.connect()

    @property
    def media_plane_configured(self) -> bool:
        return bool(self.whip_base and self.whep_base and self.hook_secret)

    def _initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS stream_sessions (
                    id TEXT PRIMARY KEY,
                    game_id INTEGER NOT NULL REFERENCES admin_games(id),
                    source_type TEXT NOT NULL CHECK(source_type IN ('CAMERA','MOBILE','OBS')),
                    status TEXT NOT NULL DEFAULT 'CREATED' CHECK(status IN ('CREATED','PAIRED','READY','LIVE','DEGRADED','STOPPED','FAILED','EXPIRED')),
                    stream_key TEXT NOT NULL UNIQUE,
                    publisher_token_hash TEXT NOT NULL,
                    media_ticket_hash TEXT NOT NULL DEFAULT '',
                    media_ticket_expires_at TEXT NOT NULL DEFAULT '',
                    pairing_code_hash TEXT NOT NULL,
                    pairing_attempts INTEGER NOT NULL DEFAULT 0,
                    pairing_expires_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    playback_type TEXT NOT NULL DEFAULT 'WHEP',
                    playback_url TEXT NOT NULL DEFAULT '',
                    hls_url TEXT NOT NULL DEFAULT '',
                    recording_enabled INTEGER NOT NULL DEFAULT 0 CHECK(recording_enabled IN (0,1)),
                    recording_url TEXT NOT NULL DEFAULT '',
                    client_label TEXT NOT NULL DEFAULT '',
                    started_at TEXT NOT NULL DEFAULT '',
                    last_heartbeat_at TEXT NOT NULL DEFAULT '',
                    stopped_at TEXT NOT NULL DEFAULT '',
                    failure_reason TEXT NOT NULL DEFAULT '',
                    created_by TEXT NOT NULL DEFAULT 'ADMIN',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS stream_health_samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL REFERENCES stream_sessions(id),
                    sequence INTEGER NOT NULL,
                    connection_state TEXT NOT NULL,
                    bitrate_kbps REAL NOT NULL DEFAULT 0,
                    fps REAL NOT NULL DEFAULT 0,
                    width INTEGER NOT NULL DEFAULT 0,
                    height INTEGER NOT NULL DEFAULT 0,
                    rtt_ms REAL NOT NULL DEFAULT 0,
                    packet_loss_percent REAL NOT NULL DEFAULT 0,
                    network_type TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    UNIQUE(session_id, sequence)
                );

                CREATE INDEX IF NOT EXISTS idx_stream_sessions_game_created
                ON stream_sessions(game_id, created_at DESC);

                CREATE INDEX IF NOT EXISTS idx_stream_sessions_active
                ON stream_sessions(status, updated_at DESC)
                WHERE status IN ('CREATED','PAIRED','READY','LIVE','DEGRADED');

                CREATE INDEX IF NOT EXISTS idx_stream_health_session_sequence
                ON stream_health_samples(session_id, sequence DESC);
                """
            )
            session_columns = {row["name"] for row in connection.execute("PRAGMA table_info(stream_sessions)").fetchall()}
            for column in ("media_ticket_hash", "media_ticket_expires_at"):
                if column not in session_columns:
                    connection.execute(f"ALTER TABLE stream_sessions ADD COLUMN {column} TEXT NOT NULL DEFAULT ''")
            connection.execute("PRAGMA optimize")

    def start_monitor(self) -> None:
        if self._monitor and self._monitor.is_alive():
            return
        self._stop_event.clear()

        def run() -> None:
            self.probe_media_plane()
            while not self._stop_event.wait(5.0):
                try:
                    self.probe_media_plane()
                    self.expire_stale_sessions()
                except Exception:
                    continue

        self._monitor = threading.Thread(target=run, name="roosterrun-stream-monitor", daemon=True)
        self._monitor.start()

    def probe_media_plane(self) -> bool:
        if not self.media_health_url:
            self.media_plane_reachable = True
            return True
        try:
            with urlrequest.urlopen(self.media_health_url, timeout=3) as response:
                healthy = 200 <= response.status < 300
        except Exception:
            healthy = False
        self.media_plane_reachable = healthy
        self.last_media_probe_at = utc_now()
        self.media_probe_failures = 0 if healthy else self.media_probe_failures + 1
        return healthy

    def stop_monitor(self) -> None:
        self._stop_event.set()
        if self._monitor and self._monitor.is_alive():
            self._monitor.join(timeout=2)

    def _media_url(self, base: str, action: str, stream_key: str, extra: dict | None = None) -> str:
        if not base:
            return ""
        parameters = {"app": "live", "stream": stream_key, **(extra or {})}
        return f"{base}/rtc/v1/{action}/?{urlencode(parameters)}"

    def _hls_url(self, stream_key: str) -> str:
        return f"{self.hls_base}/live/{stream_key}.m3u8" if self.hls_base else ""

    @staticmethod
    def _outbox(connection: sqlite3.Connection, event_type: str, session_id: str, version: int, payload: dict) -> None:
        connection.execute(
            "INSERT INTO engine_events(event_type,aggregate_type,aggregate_id,aggregate_version,payload_json,created_at) VALUES(?,?,?,?,?,?)",
            (event_type, "STREAM", session_id, version, json.dumps(payload), utc_now()),
        )

    @staticmethod
    def _session_dict(row: sqlite3.Row, latest_health: sqlite3.Row | None = None) -> dict:
        health = dict(latest_health) if latest_health else None
        if health:
            health.pop("id", None)
            health.pop("session_id", None)
        return {
            "id": row["id"], "game_id": row["game_id"], "source_type": row["source_type"], "status": row["status"],
            "playback_type": row["playback_type"], "playback_url": row["playback_url"], "hls_url": row["hls_url"],
            "recording_enabled": bool(row["recording_enabled"]), "recording_url": row["recording_url"],
            "client_label": row["client_label"], "started_at": row["started_at"],
            "last_heartbeat_at": row["last_heartbeat_at"], "stopped_at": row["stopped_at"],
            "failure_reason": row["failure_reason"], "expires_at": row["expires_at"],
            "created_at": row["created_at"], "updated_at": row["updated_at"], "health": health,
        }

    def _row_with_health(self, connection: sqlite3.Connection, session_id: str) -> tuple[sqlite3.Row, sqlite3.Row | None]:
        row = connection.execute("SELECT * FROM stream_sessions WHERE id=?", (session_id,)).fetchone()
        if not row:
            raise LookupError("Broadcast session not found.")
        sample = connection.execute(
            "SELECT * FROM stream_health_samples WHERE session_id=? ORDER BY sequence DESC LIMIT 1", (session_id,)
        ).fetchone()
        return row, sample

    def create_session(self, game_id: int, payload: dict, actor: str = "ADMIN") -> dict:
        source_type = str(payload.get("source_type") or "CAMERA").upper()
        if source_type not in {"CAMERA", "MOBILE", "OBS"}:
            raise ValueError("Choose camera, mobile, or OBS as the broadcast source.")
        client_label = " ".join(str(payload.get("client_label") or "Arena camera").split())[:80]
        recording_enabled = bool(payload.get("recording_enabled", True))
        session_id = "str_" + secrets.token_urlsafe(15).replace("-", "").replace("_", "")
        publisher_token = secrets.token_urlsafe(32)
        pairing_code = secrets.token_hex(6).upper()
        stream_key = f"cf-{int(game_id)}-{secrets.token_hex(12)}"
        now_dt = datetime.now(UTC)
        now = now_dt.isoformat(timespec="seconds")
        pairing_expires = (now_dt + timedelta(minutes=10)).isoformat(timespec="seconds")
        expires = (now_dt + timedelta(hours=12)).isoformat(timespec="seconds")
        playback_url = self._media_url(self.whep_base, "whep", stream_key)
        hls_url = self._hls_url(stream_key)
        recording_url = ""
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            game = connection.execute("SELECT * FROM admin_games WHERE id=?", (int(game_id),)).fetchone()
            if not game:
                raise LookupError("Game not found.")
            if game["status"] in {"SETTLED", "CANCELLED"}:
                raise ValueError("A finished match cannot start a new broadcast.")
            previous = connection.execute(
                "SELECT * FROM stream_sessions WHERE game_id=? AND status IN ('CREATED','PAIRED','READY','LIVE','DEGRADED') ORDER BY created_at DESC LIMIT 1",
                (int(game_id),),
            ).fetchone()
            if previous:
                connection.execute(
                    "UPDATE stream_sessions SET status='STOPPED',stopped_at=?,failure_reason='Replaced by a new operator session',updated_at=? WHERE id=?",
                    (now, now, previous["id"]),
                )
                self._outbox(connection, "STREAM_STOPPED", previous["id"], 1, {"game_id": game_id, "reason": "Replaced by a new operator session"})
            connection.execute(
                """INSERT INTO stream_sessions
                (id,game_id,source_type,status,stream_key,publisher_token_hash,pairing_code_hash,pairing_expires_at,expires_at,playback_type,playback_url,hls_url,recording_enabled,recording_url,client_label,created_by,created_at,updated_at)
                VALUES(?,?,?,'CREATED',?,?,?,?,?,'WHEP',?,?,?,?,?,?,?,?)""",
                (session_id, int(game_id), source_type, stream_key, secret_hash(publisher_token), secret_hash(pairing_code), pairing_expires, expires,
                 playback_url, hls_url, 1 if recording_enabled else 0, recording_url, client_label, actor, now, now),
            )
            if playback_url:
                connection.execute(
                    "UPDATE admin_games SET stream_type='WHEP',stream_url=?,updated_at=? WHERE id=?",
                    (playback_url, now, int(game_id)),
                )
            self._outbox(connection, "STREAM_SESSION_CREATED", session_id, 1, {"game_id": game_id, "source_type": source_type, "configured": self.media_plane_configured})
            self.platform._audit(connection, "Streaming", "Broadcast session created", game["title"], f"{source_type} · {session_id}")
            row = connection.execute("SELECT * FROM stream_sessions WHERE id=?", (session_id,)).fetchone()
        result = self._session_dict(row)
        result.update({
            "publisher_token": publisher_token,
            "pairing_code": pairing_code,
            "pairing_expires_at": pairing_expires,
            "studio_url": f"/broadcast/?session={session_id}",
            "media_plane_configured": self.media_plane_configured,
        })
        return result

    def pair_mobile(self, session_id: object, pairing_code: object) -> dict:
        session_id = str(session_id or "").strip()
        supplied_code = str(pairing_code or "").strip().upper().replace("-", "")
        if not session_id or not supplied_code:
            raise ValueError("Enter the broadcast session and pairing code.")
        publisher_token = secrets.token_urlsafe(32)
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM stream_sessions WHERE id=?", (session_id,)).fetchone()
            if not row:
                raise LookupError("Broadcast session not found.")
            if row["status"] not in ACTIVE_STATES:
                raise ValueError("This broadcast session is no longer active.")
            if parse_time(row["pairing_expires_at"]) <= datetime.now(UTC):
                raise ValueError("The pairing code has expired. Ask the administrator for a new session.")
            valid = hmac.compare_digest(row["pairing_code_hash"], secret_hash(supplied_code))
            if not valid:
                attempts = int(row["pairing_attempts"]) + 1
                status = "EXPIRED" if attempts >= 5 else row["status"]
                connection.execute(
                    "UPDATE stream_sessions SET pairing_attempts=?,status=?,updated_at=? WHERE id=?",
                    (attempts, status, utc_now(), session_id),
                )
                connection.commit()
                raise ValueError("The pairing code is incorrect.")
            now = utc_now()
            connection.execute(
                "UPDATE stream_sessions SET status='PAIRED',publisher_token_hash=?,pairing_code_hash='',updated_at=? WHERE id=?",
                (secret_hash(publisher_token), now, session_id),
            )
            self._outbox(connection, "STREAM_PAIRED", session_id, 2, {"game_id": row["game_id"]})
        return {"session_id": session_id, "publisher_token": publisher_token, "expires_at": row["expires_at"]}

    def rotate_credentials(self, session_id: str, actor: str = "ADMIN") -> dict:
        publisher_token = secrets.token_urlsafe(32)
        pairing_code = secrets.token_hex(6).upper()
        now_dt = datetime.now(UTC)
        now = now_dt.isoformat(timespec="seconds")
        pairing_expires = (now_dt + timedelta(minutes=10)).isoformat(timespec="seconds")
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM stream_sessions WHERE id=?", (session_id,)).fetchone()
            if not row:
                raise LookupError("Broadcast session not found.")
            if row["status"] == "LIVE":
                raise ValueError("Stop the live publisher before rotating its credentials.")
            if row["status"] in TERMINAL_STATES:
                raise ValueError("This broadcast session has ended. Create a new session.")
            connection.execute(
                """UPDATE stream_sessions SET status='CREATED',publisher_token_hash=?,pairing_code_hash=?,
                pairing_attempts=0,pairing_expires_at=?,updated_at=? WHERE id=?""",
                (secret_hash(publisher_token), secret_hash(pairing_code), pairing_expires, now, session_id),
            )
            self._outbox(connection, "STREAM_CREDENTIALS_ROTATED", session_id, 4, {"game_id": row["game_id"]})
            game = connection.execute("SELECT title FROM admin_games WHERE id=?", (row["game_id"],)).fetchone()
            self.platform._audit(connection, "Streaming", "Broadcast credentials rotated", game["title"] if game else str(row["game_id"]), session_id)
            updated = connection.execute("SELECT * FROM stream_sessions WHERE id=?", (session_id,)).fetchone()
        result = self._session_dict(updated)
        result.update({
            "publisher_token": publisher_token, "pairing_code": pairing_code,
            "pairing_expires_at": pairing_expires, "studio_url": f"/broadcast/?session={session_id}",
            "media_plane_configured": self.media_plane_configured,
        })
        return result

    def _authorize(self, connection: sqlite3.Connection, session_id: str, publisher_token: str) -> sqlite3.Row:
        row = connection.execute("SELECT * FROM stream_sessions WHERE id=?", (session_id,)).fetchone()
        if not row:
            raise LookupError("Broadcast session not found.")
        supplied = secret_hash(str(publisher_token or ""))
        if not publisher_token or not hmac.compare_digest(row["publisher_token_hash"], supplied):
            raise PermissionError("Broadcast authorization is invalid.")
        if row["status"] in TERMINAL_STATES or parse_time(row["expires_at"]) <= datetime.now(UTC):
            raise ValueError("This broadcast session has ended or expired.")
        return row

    def issue_ticket(self, session_id: str, publisher_token: str) -> dict:
        media_ticket = secrets.token_urlsafe(24)
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._authorize(connection, session_id, publisher_token)
            if not self.media_plane_configured:
                raise ValueError("The WHIP/WHEP media server is not configured yet. Camera preview is available, but live publishing is disabled.")
            now = utc_now()
            media_ticket_expires = (datetime.now(UTC) + timedelta(seconds=90)).isoformat(timespec="seconds")
            connection.execute(
                "UPDATE stream_sessions SET status='READY',media_ticket_hash=?,media_ticket_expires_at=?,updated_at=? WHERE id=?",
                (secret_hash(media_ticket), media_ticket_expires, now, session_id),
            )
            self._outbox(connection, "STREAM_READY", session_id, 3, {"game_id": row["game_id"]})
            updated = connection.execute("SELECT * FROM stream_sessions WHERE id=?", (session_id,)).fetchone()
        return {
            "session": self._session_dict(updated),
            "whip_url": self._media_url(self.whip_base, "whip", row["stream_key"], {"session": session_id, "ticket": media_ticket}),
            "playback_url": row["playback_url"], "expires_at": row["expires_at"],
        }

    def _hook_authorized(self, supplied_secret: str) -> bool:
        return bool(
            supplied_secret and any(
                candidate and hmac.compare_digest(candidate, supplied_secret)
                for candidate in (self.hook_secret, self.previous_hook_secret)
            )
        )

    def authorize_media_publish(self, payload: dict, supplied_secret: str) -> dict:
        """Validate the one-use token SRS sends in its on_publish hook."""
        if not self._hook_authorized(supplied_secret):
            return {"code": 403, "message": "Media hook authorization rejected"}
        stream_key = str(payload.get("stream") or "").strip()
        parameters = parse_qs(str(payload.get("param") or "").lstrip("?"))
        session_id = (parameters.get("session") or [""])[0]
        media_ticket = (parameters.get("ticket") or [""])[0]
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM stream_sessions WHERE id=? AND stream_key=?", (session_id, stream_key)).fetchone()
            valid = bool(
                row and media_ticket and row["media_ticket_hash"] and
                hmac.compare_digest(row["media_ticket_hash"], secret_hash(media_ticket)) and
                row["media_ticket_expires_at"] and parse_time(row["media_ticket_expires_at"]) > datetime.now(UTC) and
                row["status"] in ACTIVE_STATES
            )
            if not valid:
                return {"code": 403, "message": "Publishing ticket rejected"}
            now = utc_now()
            connection.execute(
                "UPDATE stream_sessions SET media_ticket_hash='',media_ticket_expires_at='',updated_at=? WHERE id=?",
                (now, session_id),
            )
            self._outbox(connection, "STREAM_MEDIA_AUTHORIZED", session_id, 5, {"game_id": row["game_id"]})
        return {"code": 0, "message": "Publishing authorized"}

    def media_unpublish(self, payload: dict, supplied_secret: str) -> dict:
        if not self._hook_authorized(supplied_secret):
            return {"code": 403, "message": "Media hook authorization rejected"}
        stream_key = str(payload.get("stream") or "").strip()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM stream_sessions WHERE stream_key=? AND status IN ('READY','LIVE','DEGRADED') ORDER BY created_at DESC LIMIT 1",
                (stream_key,),
            ).fetchone()
            if row:
                now = utc_now()
                connection.execute(
                    "UPDATE stream_sessions SET status='DEGRADED',failure_reason='Media server reported publisher disconnect',updated_at=? WHERE id=?",
                    (now, row["id"]),
                )
                self._outbox(connection, "STREAM_DEGRADED", row["id"], 1, {"game_id": row["game_id"], "reason": "Publisher disconnected"})
        return {"code": 0, "message": "Unpublish recorded"}

    def recording_ready(self, payload: dict, supplied_secret: str) -> dict:
        """Persist the public recording URL reported by SRS's on_dvr hook."""
        if not self._hook_authorized(supplied_secret):
            return {"code": 403, "message": "Media hook authorization rejected"}
        stream_key = str(payload.get("stream") or "").strip()
        raw_file = str(payload.get("file") or "").replace("\\", "/").strip()
        marker = "/objs/nginx/html/"
        relative = raw_file.split(marker, 1)[1] if marker in raw_file else raw_file.lstrip("./")
        if not stream_key or not relative.startswith("recordings/") or ".." in relative.split("/"):
            return {"code": 400, "message": "Recording path rejected"}
        encoded_path = "/".join(quote(part, safe="-_.") for part in relative.split("/") if part)
        recording_url = f"{self.recording_base}/{encoded_path.removeprefix('recordings/')}" if self.recording_base else ""
        if not recording_url:
            return {"code": 503, "message": "Recording delivery is not configured"}
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM stream_sessions WHERE stream_key=? ORDER BY created_at DESC LIMIT 1", (stream_key,)
            ).fetchone()
            if not row:
                return {"code": 404, "message": "Broadcast session not found"}
            now = utc_now()
            connection.execute("UPDATE stream_sessions SET recording_url=?,updated_at=? WHERE id=?", (recording_url, now, row["id"]))
            self._outbox(connection, "STREAM_RECORDING_READY", row["id"], 1, {"game_id": row["game_id"], "recording_url": recording_url})
        return {"code": 0, "message": "Recording registered", "recording_url": recording_url}

    def heartbeat(self, session_id: str, publisher_token: str, payload: dict) -> dict:
        connection_state = str(payload.get("connection_state") or "connected").strip().lower()[:30]
        bitrate = bounded_number(payload.get("bitrate_kbps"), 0, 100_000)
        fps = bounded_number(payload.get("fps"), 0, 120)
        width = int(bounded_number(payload.get("width"), 0, 7680))
        height = int(bounded_number(payload.get("height"), 0, 4320))
        rtt = bounded_number(payload.get("rtt_ms"), 0, 60_000)
        loss = bounded_number(payload.get("packet_loss_percent"), 0, 100)
        network_type = str(payload.get("network_type") or "").strip()[:30]
        degraded = connection_state not in {"connected", "completed", "live"} or loss >= 8 or rtt >= 1200
        status = "DEGRADED" if degraded else "LIVE"
        now = utc_now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._authorize(connection, session_id, publisher_token)
            previous = row["status"]
            sequence = int(connection.execute(
                "SELECT COALESCE(MAX(sequence),0)+1 AS sequence FROM stream_health_samples WHERE session_id=?", (session_id,)
            ).fetchone()["sequence"])
            connection.execute(
                """INSERT INTO stream_health_samples
                (session_id,sequence,connection_state,bitrate_kbps,fps,width,height,rtt_ms,packet_loss_percent,network_type,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (session_id, sequence, connection_state, bitrate, fps, width, height, rtt, loss, network_type, now),
            )
            started_at = row["started_at"] or now
            connection.execute(
                "UPDATE stream_sessions SET status=?,started_at=?,last_heartbeat_at=?,updated_at=? WHERE id=?",
                (status, started_at, now, now, session_id),
            )
            connection.execute(
                "UPDATE admin_games SET stream_type='WHEP',stream_url=?,updated_at=? WHERE id=?",
                (row["playback_url"], now, row["game_id"]),
            )
            event_type = "STREAM_LIVE" if previous not in {"LIVE", "DEGRADED"} else ("STREAM_DEGRADED" if status == "DEGRADED" and previous != "DEGRADED" else "STREAM_HEALTH_UPDATED")
            self._outbox(connection, event_type, session_id, sequence, {"game_id": row["game_id"], "status": status, "bitrate_kbps": bitrate, "rtt_ms": rtt, "packet_loss_percent": loss})
            updated, sample = self._row_with_health(connection, session_id)
        return self._session_dict(updated, sample)

    def stop_session(self, session_id: str, actor: str = "PUBLISHER", publisher_token: str = "", reason: str = "") -> dict:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM stream_sessions WHERE id=?", (session_id,)).fetchone()
            if not row:
                raise LookupError("Broadcast session not found.")
            if actor != "ADMIN":
                row = self._authorize(connection, session_id, publisher_token)
            if row["status"] in TERMINAL_STATES:
                latest, sample = self._row_with_health(connection, session_id)
                return self._session_dict(latest, sample)
            now = utc_now()
            failure_reason = " ".join(str(reason or "Operator ended stream").split())[:180]
            connection.execute(
                "UPDATE stream_sessions SET status='STOPPED',stopped_at=?,failure_reason=?,updated_at=? WHERE id=?",
                (now, failure_reason, now, session_id),
            )
            connection.execute(
                "UPDATE admin_games SET stream_type='OFFLINE',stream_url='',updated_at=? WHERE id=? AND stream_url=?",
                (now, row["game_id"], row["playback_url"]),
            )
            self._outbox(connection, "STREAM_STOPPED", session_id, 1, {"game_id": row["game_id"], "reason": failure_reason})
            if actor == "ADMIN":
                game = connection.execute("SELECT title FROM admin_games WHERE id=?", (row["game_id"],)).fetchone()
                self.platform._audit(connection, "Streaming", "Broadcast stopped", game["title"] if game else str(row["game_id"]), failure_reason)
            updated, sample = self._row_with_health(connection, session_id)
        return self._session_dict(updated, sample)

    def expire_stale_sessions(self) -> int:
        now_dt = datetime.now(UTC)
        changed = 0
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                "SELECT * FROM stream_sessions WHERE status IN ('CREATED','PAIRED','READY','LIVE','DEGRADED')"
            ).fetchall()
            for row in rows:
                status = row["status"]
                next_status = ""
                reason = ""
                if parse_time(row["expires_at"]) <= now_dt:
                    next_status, reason = "EXPIRED", "Broadcast authorization expired"
                elif status in {"LIVE", "DEGRADED"} and row["last_heartbeat_at"]:
                    age = (now_dt - parse_time(row["last_heartbeat_at"])).total_seconds()
                    if age >= 60:
                        next_status, reason = "FAILED", "Publisher heartbeat was lost"
                    elif age >= 15 and status != "DEGRADED":
                        next_status, reason = "DEGRADED", "Publisher heartbeat is delayed"
                if not next_status:
                    continue
                now = now_dt.isoformat(timespec="seconds")
                connection.execute(
                    "UPDATE stream_sessions SET status=?,failure_reason=?,stopped_at=CASE WHEN ? IN ('FAILED','EXPIRED') THEN ? ELSE stopped_at END,updated_at=? WHERE id=?",
                    (next_status, reason, next_status, now, now, row["id"]),
                )
                if next_status in {"FAILED", "EXPIRED"}:
                    connection.execute(
                        "UPDATE admin_games SET stream_type='OFFLINE',stream_url='',updated_at=? WHERE id=? AND stream_url=?",
                        (now, row["game_id"], row["playback_url"]),
                    )
                self._outbox(connection, f"STREAM_{next_status}", row["id"], 1, {"game_id": row["game_id"], "reason": reason})
                changed += 1
        return changed

    def list_sessions(self, game_id: int | None = None, limit: int = 100) -> list[dict]:
        limit = max(1, min(int(limit), 200))
        query = "SELECT * FROM stream_sessions"
        parameters: list[object] = []
        if game_id is not None:
            query += " WHERE game_id=?"
            parameters.append(int(game_id))
        query += " ORDER BY created_at DESC LIMIT ?"
        parameters.append(limit)
        with self.connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
            results = []
            for row in rows:
                sample = connection.execute(
                    "SELECT * FROM stream_health_samples WHERE session_id=? ORDER BY sequence DESC LIMIT 1", (row["id"],)
                ).fetchone()
                results.append(self._session_dict(row, sample))
        return results

    @staticmethod
    def _public_stream(row: sqlite3.Row, sample: sqlite3.Row | None = None) -> dict:
        health = None
        if sample:
            health = {
                "connection_state": sample["connection_state"], "bitrate_kbps": sample["bitrate_kbps"],
                "fps": sample["fps"], "width": sample["width"], "height": sample["height"],
            }
        return {
            "game_id": row["game_id"], "status": row["status"], "playback_type": row["playback_type"],
            "playback_url": row["playback_url"], "hls_url": row["hls_url"], "started_at": row["started_at"],
            "last_heartbeat_at": row["last_heartbeat_at"], "health": health,
        }

    def current_stream(self, game_id: int | None = None) -> dict:
        with self.connect() as connection:
            if game_id is None:
                game = connection.execute("SELECT id FROM admin_games WHERE featured=1 ORDER BY id DESC LIMIT 1").fetchone()
                if not game:
                    raise LookupError("No featured match is available.")
                game_id = int(game["id"])
            row = connection.execute(
                "SELECT * FROM stream_sessions WHERE game_id=? AND status IN ('READY','LIVE','DEGRADED') ORDER BY created_at DESC LIMIT 1",
                (int(game_id),),
            ).fetchone()
            if not row:
                return {"game_id": int(game_id), "status": "OFFLINE", "playback_type": "OFFLINE", "playback_url": ""}
            sample = connection.execute(
                "SELECT * FROM stream_health_samples WHERE session_id=? ORDER BY sequence DESC LIMIT 1", (row["id"],)
            ).fetchone()
            return self._public_stream(row, sample)

    def health(self) -> dict:
        self.expire_stale_sessions()
        with self.connect() as connection:
            counts = connection.execute(
                """SELECT COUNT(*) AS total,
                SUM(CASE WHEN status='LIVE' THEN 1 ELSE 0 END) AS live,
                SUM(CASE WHEN status='DEGRADED' THEN 1 ELSE 0 END) AS degraded,
                SUM(CASE WHEN status IN ('CREATED','PAIRED','READY') THEN 1 ELSE 0 END) AS preparing,
                MAX(last_heartbeat_at) AS last_heartbeat FROM stream_sessions"""
            ).fetchone()
            recordings = connection.execute("SELECT COUNT(*) AS total FROM stream_sessions WHERE recording_url<>''").fetchone()["total"]
        return {
            "status": "ok" if self.media_plane_configured else "configuration_required",
            "media_plane_configured": self.media_plane_configured,
            "monitor_running": bool(self._monitor and self._monitor.is_alive()),
            "sessions": int(counts["total"] or 0), "live": int(counts["live"] or 0),
            "degraded": int(counts["degraded"] or 0), "preparing": int(counts["preparing"] or 0),
            "last_heartbeat_at": counts["last_heartbeat"] or "",
            "recording_configured": bool(self.recording_base), "recordings": int(recordings or 0),
            "media_plane_reachable": self.media_plane_reachable,
            "last_media_probe_at": self.last_media_probe_at,
            "media_probe_failures": self.media_probe_failures,
        }
