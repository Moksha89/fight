"""RoosterRun application server with a durable manual-payments workflow.

This server intentionally uses only the Python standard library so the checked
out repository can be tested immediately. It serves the web clients, stores
domain records in SQLite, and separates public media from private evidence.

Preview admin access is accepted only from the loopback interface and only when
the browser sends X-Preview-Admin: 1. Production deployments use named staff
accounts, role checks, MFA, and server-side sessions.
"""

from __future__ import annotations

import argparse
import base64
import contextvars
import hashlib
import ipaddress
import json
import mimetypes
import os
import random
import re
import secrets
import signal
import sqlite3
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from http.cookies import SimpleCookie
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from auth_engine import AuthenticationEngine, AuthenticationError, RateLimitError
from china_feed_engine import ChinaFeedEngine
from cockfight_engine import CockfightEngine, parse_timestamp, timestamp
from compliance_engine import ComplianceEngine
from database import Database
from delivery_engine import DeliveryEngine
from intelligence_engine import IntelligenceEngine
from operations_engine import OperationsEngine
from observability import Metrics, StructuredLogger
from runtime_config import database_url_from_env, load_secret_files, secret_rotation_status, validate_runtime_secrets
from streaming_engine import StreamingEngine
from support_engine import SupportEngine


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = PROJECT_ROOT / "web"
DEFAULT_DATA_DIR = PROJECT_ROOT / "var" / "manual_payments"
MAX_JSON_BYTES = 4 * 1024 * 1024
MAX_IMAGE_BYTES = 2_500_000
MAX_MEDIA_IMAGE_BYTES = 5 * 1024 * 1024
MAX_MEDIA_VIDEO_BYTES = 250 * 1024 * 1024
USER_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_.@-]{3,80}$")
UTR_PATTERN = re.compile(r"^[A-Za-z0-9-]{6,35}$")
IFSC_PATTERN = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
UPI_PATTERN = re.compile(r"^[A-Za-z0-9._-]{2,}@[A-Za-z0-9.-]{2,}$")
ACCOUNT_NUMBER_PATTERN = re.compile(r"^[0-9]{8,22}$")
USER_SESSION_COOKIE = "rr_user_session"
USER_CSRF_COOKIE = "rr_user_csrf"
ADMIN_SESSION_COOKIE = "rr_admin_session"
ADMIN_CSRF_COOKIE = "rr_admin_csrf"
CHINA_CATEGORY_SLUG = "china-24-7"
OPERATING_MODES = {"SOCIAL_PREVIEW", "APPROVAL_DEMO", "REAL_MONEY"}
OPERATING_MODE_LABELS = {
    "SOCIAL_PREVIEW": "Social preview",
    "APPROVAL_DEMO": "Approval demo · demo credits only",
    "REAL_MONEY": "Real money · live wallets",
}
AUDIT_CONTEXT = contextvars.ContextVar(
    "roosterrun_audit_context",
    default={"actor_id": "SYSTEM", "actor_role": "SYSTEM", "request_id": "", "ip_address": ""},
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def money_to_paise(value: object, minimum: int, maximum: int) -> int:
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        raise ValueError("Enter a valid amount.") from None
    paise = int(amount * 100)
    if paise < minimum * 100 or paise > maximum * 100:
        raise ValueError(f"Amount must be between ₹{minimum:,} and ₹{maximum:,}.")
    return paise


def paise_to_rupees(value: int) -> float:
    return round(int(value or 0) / 100, 2)


def clean_text(value: object, label: str, minimum: int = 1, maximum: int = 120) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if len(text) < minimum or len(text) > maximum:
        raise ValueError(f"{label} must contain {minimum}–{maximum} characters.")
    return text


def clean_media_url(value: object, label: str = "Media URL") -> str:
    """Accept a secure remote URL or one of this server's media paths."""
    media_url = str(value or "").strip()
    if not media_url:
        return ""
    if len(media_url) > 1000:
        raise ValueError(f"{label} is too long.")
    if media_url.startswith(("/uploads/", "/static/")):
        return media_url
    parsed = urlparse(media_url)
    if parsed.scheme.lower() == "https" and parsed.netloc:
        return media_url
    if parsed.scheme.lower() == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}:
        return media_url
    raise ValueError(f"{label} must use HTTPS or a saved upload.")


class PaymentService:
    def __init__(self, data_dir: Path, preview_mode: bool = False):
        self.data_dir = data_dir.resolve()
        self.preview_mode = preview_mode
        requested_mode = os.environ.get("ROOSTERRUN_OPERATING_MODE", "REAL_MONEY").strip().upper()
        if requested_mode not in OPERATING_MODES:
            raise RuntimeError("ROOSTERRUN_OPERATING_MODE must be SOCIAL_PREVIEW, APPROVAL_DEMO, or REAL_MONEY.")
        self.operating_mode = "SOCIAL_PREVIEW" if preview_mode else requested_mode
        demo_balance = os.environ.get("ROOSTERRUN_DEMO_STARTING_BALANCE", "12450").strip()
        try:
            demo_amount = Decimal(demo_balance).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        except (InvalidOperation, ValueError):
            raise RuntimeError("ROOSTERRUN_DEMO_STARTING_BALANCE must be a valid amount.") from None
        if demo_amount < 0 or demo_amount > Decimal("1000000"):
            raise RuntimeError("ROOSTERRUN_DEMO_STARTING_BALANCE must be between 0 and 1,000,000.")
        self.initial_wallet_balance_paise = int(demo_amount * 100) if self.operating_mode == "APPROVAL_DEMO" else 0
        self.upload_dir = self.data_dir / "uploads"
        self.private_payment_dir = self.data_dir / "private" / "payments"
        self.db_path = self.data_dir / "payments.sqlite3"
        self.database = Database(self.db_path, database_url_from_env())
        self.logger = StructuredLogger()
        self.metrics = Metrics()
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.private_payment_dir.mkdir(parents=True, exist_ok=True)
        self._initialize()
        self._migrate_private_payment_evidence()
        self.auth = AuthenticationEngine(self, preview_mode)
        self.compliance = ComplianceEngine(self)
        self.cockfight = CockfightEngine(self)
        self.streaming = StreamingEngine(self)
        self.operations = OperationsEngine(self)
        self.delivery = DeliveryEngine(self)
        self.support = SupportEngine(self)
        self.intelligence = IntelligenceEngine(self)
        self.china_feed = ChinaFeedEngine(self)

    def connect(self) -> sqlite3.Connection:
        return self.database.connect()

    def _migrate_private_payment_evidence(self) -> None:
        """Move legacy payment proofs out of the publicly served upload tree."""
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT deposit_proof_filename,payout_proof_filename FROM payment_requests"
            ).fetchall()
        filenames = {
            str(row[column] or "")
            for row in rows
            for column in ("deposit_proof_filename", "payout_proof_filename")
            if row[column]
        }
        for filename in filenames:
            if Path(filename).name != filename:
                continue
            source = (self.upload_dir / filename).resolve()
            target = (self.private_payment_dir / filename).resolve()
            if self.upload_dir not in source.parents or self.private_payment_dir not in target.parents:
                continue
            if not source.is_file():
                continue
            if target.exists():
                # A completed prior migration wins; remove the remaining public
                # duplicate without replacing the protected evidence file.
                source.unlink()
            else:
                source.replace(target)
            try:
                target.chmod(0o600)
            except OSError:
                # Windows and some mounted volumes do not expose POSIX modes.
                pass

    def _initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS user_wallets (
                    user_id TEXT PRIMARY KEY,
                    balance_paise INTEGER NOT NULL DEFAULT 0 CHECK(balance_paise >= 0),
                    display_name TEXT NOT NULL DEFAULT '',
                    mobile TEXT NOT NULL DEFAULT '',
                    account_status TEXT NOT NULL DEFAULT 'ACTIVE',
                    vip_tier TEXT NOT NULL DEFAULT 'Standard',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS payment_accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    label TEXT NOT NULL,
                    account_type TEXT NOT NULL CHECK(account_type IN ('UPI','BANK')),
                    upi_id TEXT NOT NULL DEFAULT '',
                    account_holder TEXT NOT NULL DEFAULT '',
                    bank_name TEXT NOT NULL DEFAULT '',
                    account_number TEXT NOT NULL DEFAULT '',
                    ifsc TEXT NOT NULL DEFAULT '',
                    qr_filename TEXT NOT NULL DEFAULT '',
                    qr_external_url TEXT NOT NULL DEFAULT '',
                    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS payment_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reference TEXT NOT NULL UNIQUE,
                    user_id TEXT NOT NULL REFERENCES user_wallets(user_id),
                    request_type TEXT NOT NULL CHECK(request_type IN ('DEPOSIT','WITHDRAWAL')),
                    amount_paise INTEGER NOT NULL CHECK(amount_paise > 0),
                    status TEXT NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING','APPROVED','REJECTED')),
                    account_id INTEGER REFERENCES payment_accounts(id),
                    account_snapshot TEXT NOT NULL DEFAULT '{}',
                    user_utr TEXT NOT NULL DEFAULT '',
                    deposit_proof_filename TEXT NOT NULL DEFAULT '',
                    beneficiary TEXT NOT NULL DEFAULT '{}',
                    admin_note TEXT NOT NULL DEFAULT '',
                    payout_utr TEXT NOT NULL DEFAULT '',
                    payout_proof_filename TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    reviewed_at TEXT NOT NULL DEFAULT ''
                );

                CREATE UNIQUE INDEX IF NOT EXISTS payment_requests_deposit_utr_unique
                ON payment_requests(user_utr)
                WHERE request_type = 'DEPOSIT' AND user_utr <> '';

                CREATE INDEX IF NOT EXISTS payment_requests_user_created_idx
                ON payment_requests(user_id, created_at DESC);

                CREATE INDEX IF NOT EXISTS payment_requests_status_created_idx
                ON payment_requests(status, created_at ASC);

                CREATE TABLE IF NOT EXISTS wallet_ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL REFERENCES user_wallets(user_id),
                    request_id INTEGER NOT NULL REFERENCES payment_requests(id),
                    entry_type TEXT NOT NULL CHECK(entry_type IN ('DEPOSIT','WITHDRAWAL')),
                    amount_paise INTEGER NOT NULL,
                    balance_after_paise INTEGER NOT NULL CHECK(balance_after_paise >= 0),
                    description TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(request_id, entry_type)
                );

                CREATE TABLE IF NOT EXISTS admin_games (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    arena TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'SCHEDULED',
                    betting_opens_at TEXT NOT NULL DEFAULT '',
                    scheduled_at TEXT NOT NULL,
                    betting_closes_at TEXT NOT NULL,
                    team_a_name TEXT NOT NULL DEFAULT 'Red',
                    team_a_odds REAL NOT NULL DEFAULT 2.45,
                    draw_odds REAL NOT NULL DEFAULT 8.75,
                    team_b_name TEXT NOT NULL DEFAULT 'Blue',
                    team_b_odds REAL NOT NULL DEFAULT 2.45,
                    stream_type TEXT NOT NULL DEFAULT 'OFFLINE',
                    stream_url TEXT NOT NULL DEFAULT '',
                    thumbnail_url TEXT NOT NULL DEFAULT '',
                    result TEXT NOT NULL DEFAULT '',
                    featured INTEGER NOT NULL DEFAULT 0,
                    actual_start_at TEXT NOT NULL DEFAULT '',
                    result_declared_at TEXT NOT NULL DEFAULT '',
                    settled_at TEXT NOT NULL DEFAULT '',
                    state_version INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS game_categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    slug TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    kind TEXT NOT NULL DEFAULT 'CUSTOM',
                    visible INTEGER NOT NULL DEFAULT 1,
                    sort_order INTEGER NOT NULL DEFAULT 100,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS admin_banners (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    subtitle TEXT NOT NULL DEFAULT '',
                    placement TEXT NOT NULL DEFAULT 'HOME_HERO',
                    image_url TEXT NOT NULL DEFAULT '',
                    media_url TEXT NOT NULL DEFAULT '',
                    media_type TEXT NOT NULL DEFAULT 'IMAGE',
                    duration TEXT NOT NULL DEFAULT '',
                    cta_label TEXT NOT NULL DEFAULT '',
                    cta_route TEXT NOT NULL DEFAULT '',
                    starts_at TEXT NOT NULL DEFAULT '',
                    ends_at TEXT NOT NULL DEFAULT '',
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS admin_vip_tiers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    minimum_turnover_paise INTEGER NOT NULL DEFAULT 0,
                    cashback_percent REAL NOT NULL DEFAULT 0,
                    withdrawal_priority INTEGER NOT NULL DEFAULT 0,
                    color TEXT NOT NULL DEFAULT '#F1B93D',
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS admin_social_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL UNIQUE,
                    url TEXT NOT NULL DEFAULT '',
                    active INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS admin_settings (
                    setting_key TEXT PRIMARY KEY,
                    setting_value TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS admin_roles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    permissions TEXT NOT NULL DEFAULT '[]',
                    protected INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS admin_audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    module TEXT NOT NULL,
                    action TEXT NOT NULL,
                    subject TEXT NOT NULL DEFAULT '',
                    details TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_admin_games_status_scheduled
                ON admin_games(status, scheduled_at DESC);

                CREATE INDEX IF NOT EXISTS idx_admin_banners_active_order
                ON admin_banners(active, sort_order, id DESC);

                CREATE INDEX IF NOT EXISTS idx_admin_audit_created
                ON admin_audit_log(created_at DESC);
                """
            )
            wallet_columns = {row["name"] for row in connection.execute("PRAGMA table_info(user_wallets)").fetchall()}
            for column, definition in {
                "display_name": "TEXT NOT NULL DEFAULT ''",
                "mobile": "TEXT NOT NULL DEFAULT ''",
                "account_status": "TEXT NOT NULL DEFAULT 'ACTIVE'",
                "vip_tier": "TEXT NOT NULL DEFAULT 'Standard'",
            }.items():
                if column not in wallet_columns:
                    connection.execute(f"ALTER TABLE user_wallets ADD COLUMN {column} {definition}")
            payment_account_columns = {row["name"] for row in connection.execute("PRAGMA table_info(payment_accounts)").fetchall()}
            if "qr_external_url" not in payment_account_columns:
                connection.execute("ALTER TABLE payment_accounts ADD COLUMN qr_external_url TEXT NOT NULL DEFAULT ''")
            game_columns = {row["name"] for row in connection.execute("PRAGMA table_info(admin_games)").fetchall()}
            for column, definition in {
                "thumbnail_url": "TEXT NOT NULL DEFAULT ''",
                "betting_opens_at": "TEXT NOT NULL DEFAULT ''",
                "actual_start_at": "TEXT NOT NULL DEFAULT ''",
                "result_declared_at": "TEXT NOT NULL DEFAULT ''",
                "settled_at": "TEXT NOT NULL DEFAULT ''",
                "state_version": "INTEGER NOT NULL DEFAULT 1",
                "source": "TEXT NOT NULL DEFAULT 'MANUAL'",
                "external_ref": "TEXT NOT NULL DEFAULT ''",
                "match_number": "TEXT NOT NULL DEFAULT ''",
                "category_slug": "TEXT NOT NULL DEFAULT ''",
                "visible": "INTEGER NOT NULL DEFAULT 1",
            }.items():
                if column not in game_columns:
                    connection.execute(f"ALTER TABLE admin_games ADD COLUMN {column} {definition}")
            connection.execute(
                """INSERT OR IGNORE INTO game_categories(slug,name,description,kind,visible,sort_order,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?)""",
                (CHINA_CATEGORY_SLUG, "China 24/7", "Continuous automatic matches mirrored from the upstream China arena.", "CHINA_FEED", 0, 0, utc_now(), utc_now()),
            )
            connection.execute("UPDATE admin_games SET category_slug=? WHERE source='CHINA_FEED' AND category_slug=''", (CHINA_CATEGORY_SLUG,))
            banner_columns = {row["name"] for row in connection.execute("PRAGMA table_info(admin_banners)").fetchall()}
            for column, definition in {
                "media_url": "TEXT NOT NULL DEFAULT ''",
                "media_type": "TEXT NOT NULL DEFAULT 'IMAGE'",
                "duration": "TEXT NOT NULL DEFAULT ''",
            }.items():
                if column not in banner_columns:
                    connection.execute(f"ALTER TABLE admin_banners ADD COLUMN {column} {definition}")
            audit_columns = {row["name"] for row in connection.execute("PRAGMA table_info(admin_audit_log)").fetchall()}
            for column, definition in {
                "actor_id": "TEXT NOT NULL DEFAULT 'SYSTEM'",
                "actor_role": "TEXT NOT NULL DEFAULT 'SYSTEM'",
                "request_id": "TEXT NOT NULL DEFAULT ''",
                "ip_address": "TEXT NOT NULL DEFAULT ''",
            }.items():
                if column not in audit_columns:
                    connection.execute(f"ALTER TABLE admin_audit_log ADD COLUMN {column} {definition}")
            connection.execute("UPDATE admin_games SET betting_opens_at=scheduled_at WHERE betting_opens_at='' ")
            now = utc_now()
            seed_betting_close = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(timespec="seconds")
            seed_match_start = (datetime.now(timezone.utc) + timedelta(minutes=35)).isoformat(timespec="seconds")
            if self.preview_mode:
                connection.execute(
                    "INSERT OR IGNORE INTO user_wallets(user_id,balance_paise,created_at,updated_at) VALUES(?,?,?,?)",
                    ("arena-guest", 1_245_000, now, now),
                )
                connection.execute(
                    "UPDATE user_wallets SET display_name = ? WHERE user_id = ? AND display_name = ''",
                    ("Arena Guest", "arena-guest"),
                )
            if self.preview_mode or self.operating_mode == "APPROVAL_DEMO":
                has_demo_account = connection.execute(
                    "SELECT 1 FROM payment_accounts WHERE label='Approval demo UPI'"
                ).fetchone()
                if not has_demo_account:
                    connection.execute(
                        """INSERT INTO payment_accounts
                        (label,account_type,upi_id,account_holder,active,created_at,updated_at)
                        VALUES('Approval demo UPI','UPI','demo@upi','DEMO ONLY — DO NOT PAY',1,?,?)""",
                        (now, now),
                    )
                connection.execute(
                    """INSERT OR IGNORE INTO admin_games
                    (id,title,arena,status,betting_opens_at,scheduled_at,betting_closes_at,team_a_name,team_a_odds,draw_odds,team_b_name,team_b_odds,stream_type,stream_url,thumbnail_url,featured,created_at,updated_at)
                    VALUES(1,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,?)""",
                    ("Main Arena · Match 41", "Main Arena", "BETTING_OPEN", now, seed_match_start, seed_betting_close, "Red", 2.45, 8.75, "Blue", 2.45, "OFFLINE", "", "/static/arena-poster-v2.png", now, now),
                )
            for name, turnover, cashback, priority, color in [
                ("Standard", 0, 0, 0, "#7F8796"),
                ("Gold", 100_000_00, 1.0, 1, "#F1B93D"),
                ("Platinum", 500_000_00, 2.0, 2, "#A8B4C7"),
                ("Diamond", 1_500_000_00, 3.0, 3, "#6CD9FF"),
            ]:
                connection.execute(
                    """INSERT OR IGNORE INTO admin_vip_tiers
                    (name,minimum_turnover_paise,cashback_percent,withdrawal_priority,color,active,created_at,updated_at)
                    VALUES(?,?,?,?,?,1,?,?)""",
                    (name, turnover, cashback, priority, color, now, now),
                )
            for platform in ("Instagram", "YouTube", "Telegram", "Facebook", "X"):
                connection.execute(
                    "INSERT OR IGNORE INTO admin_social_links(platform,url,active,updated_at) VALUES(?,?,1,?)",
                    (platform, "", now),
                )
            defaults = {
                "brand": {"site_name": "RoosterRun", "tagline": "Live Arena", "logo_url": "/static/ic_rooster.svg", "favicon_url": "/static/pwa/icon-192x192.png"},
                "theme": {"primary": "#E8B84C", "primary_bright": "#FFD878", "background": "#090B0F", "surface": "#121620", "text": "#F7F8FB", "danger": "#EF4E57", "success": "#46D18B"},
                "general": {"timezone": "Asia/Kolkata", "currency": "INR", "language": "English", "maintenance_mode": False},
                "responsible": {"minimum_age": 18, "deposit_minimum": 100, "deposit_maximum": 500000, "withdrawal_minimum": 500, "withdrawal_maximum": 200000},
                "notifications": {"payment_alerts": True, "game_alerts": True, "security_alerts": True},
            }
            for key, value in defaults.items():
                connection.execute(
                    "INSERT OR IGNORE INTO admin_settings(setting_key,setting_value,updated_at) VALUES(?,?,?)",
                    (key, json.dumps(value), now),
                )
            roles = {
                "Super Admin": ["*"],
                "Game Operator": ["overview", "games", "banners", "assets"],
                "Payments Manager": ["overview", "payments", "users"],
                "Content Manager": ["overview", "banners", "theme", "social", "assets"],
                "Compliance Manager": ["overview", "compliance", "users", "audit"],
                "Operations Manager": ["overview", "operations", "payments", "games", "audit"],
                "Support Manager": ["overview", "support", "users", "payments", "compliance", "audit"],
                "Risk Analyst": ["overview", "intelligence", "users", "payments", "games", "audit"],
            }
            for name, permissions in roles.items():
                connection.execute(
                    """INSERT INTO admin_roles(name,permissions,protected) VALUES(?,?,1)
                    ON CONFLICT(name) DO UPDATE SET permissions=excluded.permissions,protected=1""",
                    (name, json.dumps(permissions)),
                )
            connection.execute("PRAGMA optimize")

    def ensure_user(self, user_id: str) -> None:
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO user_wallets(user_id,balance_paise,created_at,updated_at) VALUES(?,?,?,?)",
                (user_id, self.initial_wallet_balance_paise, now, now),
            )

    def save_image(self, data_url: object, prefix: str, required: bool = True, private: bool = False) -> str:
        if not data_url:
            if required:
                raise ValueError("Upload the required image.")
            return ""
        match = re.fullmatch(r"data:image/(png|jpeg|jpg|webp);base64,([A-Za-z0-9+/=\r\n]+)", str(data_url))
        if not match:
            raise ValueError("Only PNG, JPEG, or WebP images are accepted.")
        try:
            raw = base64.b64decode(match.group(2), validate=True)
        except (ValueError, base64.binascii.Error):
            raise ValueError("The uploaded image is invalid.") from None
        if not raw or len(raw) > MAX_IMAGE_BYTES:
            raise ValueError("The image must be smaller than 2.5 MB.")
        kind = "jpeg" if match.group(1) in {"jpeg", "jpg"} else match.group(1)
        signatures = {
            "png": raw.startswith(b"\x89PNG\r\n\x1a\n"),
            "jpeg": raw.startswith(b"\xff\xd8\xff"),
            "webp": raw.startswith(b"RIFF") and raw[8:12] == b"WEBP",
        }
        if not signatures.get(kind, False):
            raise ValueError("The image contents do not match its file type.")
        extension = "jpg" if kind == "jpeg" else kind
        digest = hashlib.sha256(raw).hexdigest()[:16]
        filename = f"{prefix}-{digest}-{secrets.token_hex(4)}.{extension}"
        destination = self.private_payment_dir if private else self.upload_dir
        target = (destination / filename).resolve()
        if destination not in target.parents:
            raise ValueError("Invalid upload target.")
        target.write_bytes(raw)
        return filename

    def save_media_upload(self, stream, length: int, content_type: str, asset_kind: str) -> dict:
        """Stream an administrator upload to disk after type and signature checks."""
        kind = str(asset_kind or "").upper()
        if kind not in {"IMAGE", "VIDEO"}:
            raise ValueError("Choose an image or video upload.")
        maximum = MAX_MEDIA_IMAGE_BYTES if kind == "IMAGE" else MAX_MEDIA_VIDEO_BYTES
        if length <= 0 or length > maximum:
            label = "5 MB" if kind == "IMAGE" else "250 MB"
            raise ValueError(f"The {kind.lower()} must be smaller than {label}.")

        declared_type = str(content_type or "").split(";", 1)[0].strip().lower()
        allowed_types = {
            "IMAGE": {"image/png", "image/jpeg", "image/webp", "application/octet-stream", ""},
            "VIDEO": {"video/mp4", "video/webm", "application/octet-stream", ""},
        }
        if declared_type not in allowed_types[kind]:
            accepted = "PNG, JPG, or WebP" if kind == "IMAGE" else "MP4 or WebM"
            raise ValueError(f"Only {accepted} {kind.lower()} files are accepted.")

        token = secrets.token_hex(10)
        temporary = (self.upload_dir / f".upload-{token}.tmp").resolve()
        if self.upload_dir not in temporary.parents:
            raise ValueError("Invalid upload target.")
        digest = hashlib.sha256()
        remaining = length
        header = bytearray()
        try:
            with temporary.open("xb") as handle:
                while remaining:
                    chunk = stream.read(min(64 * 1024, remaining))
                    if not chunk:
                        raise ValueError("The uploaded file ended unexpectedly.")
                    if len(header) < 32:
                        header.extend(chunk[: 32 - len(header)])
                    digest.update(chunk)
                    handle.write(chunk)
                    remaining -= len(chunk)

            signatures = {
                "image/png": bytes(header).startswith(b"\x89PNG\r\n\x1a\n"),
                "image/jpeg": bytes(header).startswith(b"\xff\xd8\xff"),
                "image/webp": bytes(header).startswith(b"RIFF") and bytes(header[8:12]) == b"WEBP",
                "video/mp4": len(header) >= 12 and bytes(header[4:8]) == b"ftyp",
                "video/webm": bytes(header).startswith(b"\x1a\x45\xdf\xa3"),
            }
            detected = next((mime for mime, valid in signatures.items() if valid), "")
            if not detected or not detected.startswith(kind.lower() + "/"):
                raise ValueError("The uploaded file contents do not match the selected media type.")
            if declared_type not in {"", "application/octet-stream", detected}:
                raise ValueError("The uploaded file contents do not match its file type.")
            extension = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "video/mp4": "mp4", "video/webm": "webm"}[detected]
            filename = f"admin-{kind.lower()}-{digest.hexdigest()[:16]}-{secrets.token_hex(4)}.{extension}"
            target = (self.upload_dir / filename).resolve()
            if self.upload_dir not in target.parents:
                raise ValueError("Invalid upload target.")
            temporary.replace(target)
            return {"url": f"/uploads/{filename}", "kind": kind, "content_type": detected, "size": length}
        finally:
            if temporary.exists():
                temporary.unlink()

    @staticmethod
    def account_to_dict(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "label": row["label"],
            "account_type": row["account_type"],
            "upi_id": row["upi_id"],
            "account_holder": row["account_holder"],
            "bank_name": row["bank_name"],
            "account_number": row["account_number"],
            "ifsc": row["ifsc"],
            "qr_url": row["qr_external_url"] or (f"/uploads/{row['qr_filename']}" if row["qr_filename"] else ""),
            "active": bool(row["active"]),
            "created_at": row["created_at"],
        }

    @staticmethod
    def request_to_dict(row: sqlite3.Row, admin: bool = False) -> dict:
        route = "/api/payments/admin/requests" if admin else "/api/payments/requests"
        return {
            "id": row["id"],
            "reference": row["reference"],
            "user_id": row["user_id"],
            "request_type": row["request_type"],
            "amount": paise_to_rupees(row["amount_paise"]),
            "status": row["status"],
            "account_id": row["account_id"],
            "account": json.loads(row["account_snapshot"] or "{}"),
            "user_utr": row["user_utr"],
            "deposit_proof_url": f"{route}/{row['id']}/deposit-proof/" if row["deposit_proof_filename"] else "",
            "beneficiary": json.loads(row["beneficiary"] or "{}"),
            "admin_note": row["admin_note"],
            "payout_utr": row["payout_utr"],
            "payout_proof_url": f"{route}/{row['id']}/payout-proof/" if row["payout_proof_filename"] else "",
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "reviewed_at": row["reviewed_at"],
        }

    def payment_evidence(self, request_id: int, kind: str, user_id: str | None = None) -> tuple[Path, str]:
        column = {
            "deposit-proof": "deposit_proof_filename",
            "payout-proof": "payout_proof_filename",
        }.get(kind)
        if not column:
            raise LookupError("Payment evidence not found.")
        with self.connect() as connection:
            row = connection.execute(
                f"SELECT user_id,{column} AS filename FROM payment_requests WHERE id = ?",
                (request_id,),
            ).fetchone()
        if not row or (user_id is not None and row["user_id"] != user_id):
            raise LookupError("Payment evidence not found.")
        filename = str(row["filename"] or "")
        if not filename or Path(filename).name != filename:
            raise LookupError("Payment evidence not found.")
        path = (self.private_payment_dir / filename).resolve()
        if self.private_payment_dir not in path.parents or not path.is_file():
            raise LookupError("Payment evidence not found.")
        return path, mimetypes.guess_type(filename)[0] or "application/octet-stream"

    def list_accounts(self, include_inactive: bool = False) -> list[dict]:
        query = "SELECT * FROM payment_accounts"
        if not include_inactive:
            query += " WHERE active = 1"
        query += " ORDER BY active DESC, id DESC"
        with self.connect() as connection:
            return [self.account_to_dict(row) for row in connection.execute(query).fetchall()]

    def create_account(self, payload: dict) -> dict:
        account_type = str(payload.get("account_type") or "").upper()
        if account_type not in {"UPI", "BANK"}:
            raise ValueError("Choose UPI or bank transfer.")
        label = clean_text(payload.get("label"), "Account label", 2, 60)
        holder = clean_text(payload.get("account_holder"), "Account holder", 2, 100)
        upi_id = str(payload.get("upi_id") or "").strip()
        bank_name = str(payload.get("bank_name") or "").strip()
        account_number = str(payload.get("account_number") or "").replace(" ", "")
        ifsc = str(payload.get("ifsc") or "").replace(" ", "").upper()
        if account_type == "UPI" and not UPI_PATTERN.fullmatch(upi_id):
            raise ValueError("Enter a valid UPI ID, for example name@bank.")
        if account_type == "BANK":
            bank_name = clean_text(bank_name, "Bank name", 2, 80)
            if not ACCOUNT_NUMBER_PATTERN.fullmatch(account_number):
                raise ValueError("Enter a valid 8–22 digit account number.")
            if not IFSC_PATTERN.fullmatch(ifsc):
                raise ValueError("Enter a valid IFSC code.")
        qr_filename = self.save_image(payload.get("qr_data_url"), "payment-qr", required=False)
        qr_external_url = "" if qr_filename else clean_media_url(payload.get("qr_url"), "Payment QR URL")
        now = utc_now()
        with self.connect() as connection:
            cursor = connection.execute(
                """INSERT INTO payment_accounts
                (label,account_type,upi_id,account_holder,bank_name,account_number,ifsc,qr_filename,qr_external_url,active,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,1,?,?)""",
                (label, account_type, upi_id, holder, bank_name, account_number, ifsc, qr_filename, qr_external_url, now, now),
            )
            row = connection.execute("SELECT * FROM payment_accounts WHERE id = ?", (cursor.lastrowid,)).fetchone()
            self._audit(connection, "Payments", "Receiving account added", label, account_type)
        return self.account_to_dict(row)

    def toggle_account(self, account_id: int) -> dict:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM payment_accounts WHERE id = ?", (account_id,)).fetchone()
            if not row:
                raise LookupError("Payment account not found.")
            connection.execute(
                "UPDATE payment_accounts SET active = ?, updated_at = ? WHERE id = ?",
                (0 if row["active"] else 1, utc_now(), account_id),
            )
            updated = connection.execute("SELECT * FROM payment_accounts WHERE id = ?", (account_id,)).fetchone()
            self._audit(connection, "Payments", "Receiving account toggled", updated["label"], "Enabled" if updated["active"] else "Disabled")
        return self.account_to_dict(updated)

    def wallet(self, user_id: str) -> dict:
        return self.cockfight.wallet(user_id)

    def create_deposit(self, user_id: str, payload: dict) -> dict:
        amount = money_to_paise(payload.get("amount"), 100, 500_000)
        try:
            account_id = int(payload.get("account_id"))
        except (TypeError, ValueError):
            raise ValueError("Choose the payment account you used.") from None
        utr = str(payload.get("utr") or "").replace(" ", "").strip()
        if not UTR_PATTERN.fullmatch(utr):
            raise ValueError("Enter a valid 6–35 character UTR or transaction reference.")
        proof = self.save_image(payload.get("proof_data_url"), "deposit-proof", private=True)
        self.ensure_user(user_id)
        now = utc_now()
        reference = f"DEP-{datetime.now().strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self.compliance.assert_allowed_in_transaction(connection, user_id, "DEPOSIT", amount)
            account = connection.execute("SELECT * FROM payment_accounts WHERE id = ? AND active = 1", (account_id,)).fetchone()
            if not account:
                raise ValueError("That payment account is no longer available.")
            snapshot = self.account_to_dict(account)
            try:
                cursor = connection.execute(
                    """INSERT INTO payment_requests
                    (reference,user_id,request_type,amount_paise,status,account_id,account_snapshot,user_utr,deposit_proof_filename,created_at,updated_at)
                    VALUES(?,?,'DEPOSIT',?,'PENDING',?,?,?,?,?,?)""",
                    (reference, user_id, amount, account_id, json.dumps(snapshot), utr, proof, now, now),
                )
            except self.database.integrity_error_types() as error:
                if "user_utr" in str(error) or "UNIQUE" in str(error):
                    raise ValueError("This UTR has already been submitted.") from None
                raise
            row = connection.execute("SELECT * FROM payment_requests WHERE id = ?", (cursor.lastrowid,)).fetchone()
            self.operations.notify(
                connection, audience="USER", user_id=user_id, event_type="DEPOSIT_SUBMITTED", severity="INFO",
                title="Deposit submitted", message=f"{reference} is waiting for administrator verification.",
                action_route="#wallet", dedupe_key=f"user:{user_id}:deposit-submitted:{reference}",
            )
            self.operations.notify(
                connection, audience="ADMIN", event_type="PAYMENT_REVIEW_REQUIRED", severity="WARNING",
                title="Deposit verification required", message=f"{reference} requires proof and UTR review.",
                action_route="#payments", dedupe_key=f"admin:deposit-review:{reference}",
            )
        return self.request_to_dict(row)

    def create_withdrawal(self, user_id: str, payload: dict) -> dict:
        amount = money_to_paise(payload.get("amount"), 500, 200_000)
        method = str(payload.get("method") or "").upper()
        holder = clean_text(payload.get("account_holder"), "Account holder", 2, 100)
        beneficiary = {"method": method, "account_holder": holder}
        if method == "UPI":
            upi_id = str(payload.get("upi_id") or "").strip()
            if not UPI_PATTERN.fullmatch(upi_id):
                raise ValueError("Enter a valid UPI ID.")
            beneficiary["upi_id"] = upi_id
        elif method == "BANK":
            bank_name = clean_text(payload.get("bank_name"), "Bank name", 2, 80)
            account_number = str(payload.get("account_number") or "").replace(" ", "")
            ifsc = str(payload.get("ifsc") or "").replace(" ", "").upper()
            if not ACCOUNT_NUMBER_PATTERN.fullmatch(account_number):
                raise ValueError("Enter a valid 8–22 digit account number.")
            if not IFSC_PATTERN.fullmatch(ifsc):
                raise ValueError("Enter a valid IFSC code.")
            beneficiary.update({"bank_name": bank_name, "account_number": account_number, "ifsc": ifsc})
        else:
            raise ValueError("Choose bank transfer or UPI.")
        self.ensure_user(user_id)
        now = utc_now()
        reference = f"WDR-{datetime.now().strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self.compliance.assert_allowed_in_transaction(connection, user_id, "WITHDRAWAL", amount)
            wallet = connection.execute("SELECT balance_paise FROM user_wallets WHERE user_id = ?", (user_id,)).fetchone()
            held = connection.execute(
                "SELECT COALESCE(SUM(amount_paise),0) AS held FROM payment_requests WHERE user_id = ? AND request_type = 'WITHDRAWAL' AND status = 'PENDING'",
                (user_id,),
            ).fetchone()["held"]
            if int(wallet["balance_paise"]) - int(held) < amount:
                raise ValueError("Your available balance is not enough for this withdrawal.")
            cursor = connection.execute(
                """INSERT INTO payment_requests
                (reference,user_id,request_type,amount_paise,status,beneficiary,created_at,updated_at)
                VALUES(?,?,'WITHDRAWAL',?,'PENDING',?,?,?)""",
                (reference, user_id, amount, json.dumps(beneficiary), now, now),
            )
            row = connection.execute("SELECT * FROM payment_requests WHERE id = ?", (cursor.lastrowid,)).fetchone()
            self.operations.notify(
                connection, audience="USER", user_id=user_id, event_type="WITHDRAWAL_SUBMITTED", severity="INFO",
                title="Withdrawal submitted", message=f"{reference} is reserved and waiting for payout review.",
                action_route="#wallet", dedupe_key=f"user:{user_id}:withdrawal-submitted:{reference}",
            )
            self.operations.notify(
                connection, audience="ADMIN", event_type="PAYMENT_REVIEW_REQUIRED", severity="WARNING",
                title="Withdrawal payout required", message=f"{reference} requires beneficiary review and manual payout.",
                action_route="#payments", dedupe_key=f"admin:withdrawal-review:{reference}",
            )
        return self.request_to_dict(row)

    def list_requests(self, user_id: str | None = None, status: str = "") -> list[dict]:
        conditions = []
        values: list[object] = []
        if user_id:
            conditions.append("user_id = ?")
            values.append(user_id)
        if status:
            status = status.upper()
            if status not in {"PENDING", "APPROVED", "REJECTED"}:
                raise ValueError("Invalid request status.")
            conditions.append("status = ?")
            values.append(status)
        query = "SELECT * FROM payment_requests"
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY CASE status WHEN 'PENDING' THEN 0 ELSE 1 END, created_at DESC"
        with self.connect() as connection:
            rows = connection.execute(query, values).fetchall()
        return [self.request_to_dict(row, admin=user_id is None) for row in rows]

    def list_ledger(self, user_id: str) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM wallet_ledger WHERE user_id = ? ORDER BY created_at DESC, id DESC LIMIT 100",
                (user_id,),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "request_id": row["request_id"],
                "entry_type": row["entry_type"],
                "amount": paise_to_rupees(row["amount_paise"]),
                "balance_after": paise_to_rupees(row["balance_after_paise"]),
                "description": row["description"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def decide_request(self, request_id: int, payload: dict) -> dict:
        decision = str(payload.get("decision") or "").upper()
        if decision not in {"APPROVED", "REJECTED"}:
            raise ValueError("Choose approve or reject.")
        note = str(payload.get("admin_note") or "").strip()
        if decision == "REJECTED":
            note = clean_text(note, "Rejection reason", 3, 300)
        payout_utr = str(payload.get("payout_utr") or "").replace(" ", "").strip()
        payout_proof = ""
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            request_row = connection.execute("SELECT * FROM payment_requests WHERE id = ?", (request_id,)).fetchone()
            if not request_row:
                raise LookupError("Payment request not found.")
            if request_row["status"] != "PENDING":
                raise ValueError("This request has already been reviewed.")
            if request_row["request_type"] == "WITHDRAWAL" and decision == "APPROVED":
                if payout_utr and not UTR_PATTERN.fullmatch(payout_utr):
                    raise ValueError("Enter a valid payout UTR.")
                payout_proof = self.save_image(payload.get("payout_proof_data_url"), "withdrawal-proof", required=False, private=True)
                if not payout_utr and not payout_proof:
                    raise ValueError("Enter the payout UTR or upload the payout screenshot.")
            now = utc_now()
            if decision == "APPROVED":
                wallet = connection.execute(
                    "SELECT balance_paise FROM user_wallets WHERE user_id = ?",
                    (request_row["user_id"],),
                ).fetchone()
                current = int(wallet["balance_paise"])
                delta = int(request_row["amount_paise"])
                if request_row["request_type"] == "WITHDRAWAL":
                    delta = -delta
                    if current + delta < 0:
                        raise ValueError("The wallet no longer has enough balance for this payout.")
                updated_balance = current + delta
                connection.execute(
                    "UPDATE user_wallets SET balance_paise = ?, updated_at = ? WHERE user_id = ?",
                    (updated_balance, now, request_row["user_id"]),
                )
                connection.execute(
                    """INSERT INTO wallet_ledger
                    (user_id,request_id,entry_type,amount_paise,balance_after_paise,description,created_at)
                    VALUES(?,?,?,?,?,?,?)""",
                    (
                        request_row["user_id"],
                        request_row["id"],
                        request_row["request_type"],
                        delta,
                        updated_balance,
                        f"{request_row['reference']} approved",
                        now,
                    ),
                )
            connection.execute(
                """UPDATE payment_requests SET status = ?, admin_note = ?, payout_utr = ?,
                payout_proof_filename = ?, updated_at = ?, reviewed_at = ? WHERE id = ?""",
                (decision, note, payout_utr, payout_proof, now, now, request_id),
            )
            updated = connection.execute("SELECT * FROM payment_requests WHERE id = ?", (request_id,)).fetchone()
            self._audit(connection, "Payments", f"{request_row['request_type'].title()} {decision.lower()}", request_row["reference"], note or payout_utr)
            request_label = request_row["request_type"].title()
            self.operations.notify(
                connection, audience="USER", user_id=request_row["user_id"], event_type=f"{request_row['request_type']}_{decision}",
                severity="SUCCESS" if decision == "APPROVED" else "WARNING",
                title=f"{request_label} {decision.lower()}",
                message=(f"{request_row['reference']} was approved and the wallet is updated." if decision == "APPROVED" else f"{request_row['reference']} was rejected. {note}"),
                action_route="#wallet", dedupe_key=f"user:{request_row['user_id']}:payment-decision:{request_row['reference']}:{decision}",
            )
        return self.request_to_dict(updated, admin=True)

    @staticmethod
    def _audit(connection: sqlite3.Connection, module: str, action: str, subject: str = "", details: str = "") -> None:
        context = AUDIT_CONTEXT.get()
        connection.execute(
            """INSERT INTO admin_audit_log
            (module,action,subject,details,actor_id,actor_role,request_id,ip_address,created_at)
            VALUES(?,?,?,?,?,?,?,?,?)""",
            (
                module,
                action,
                subject,
                details[:500],
                str(context.get("actor_id") or "SYSTEM")[:100],
                str(context.get("actor_role") or "SYSTEM")[:100],
                str(context.get("request_id") or "")[:100],
                str(context.get("ip_address") or "")[:80],
                utc_now(),
            ),
        )

    @staticmethod
    def game_to_dict(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"], "title": row["title"], "arena": row["arena"], "status": row["status"],
            "betting_opens_at": row["betting_opens_at"], "scheduled_at": row["scheduled_at"], "betting_closes_at": row["betting_closes_at"],
            "team_a_name": row["team_a_name"], "team_a_odds": row["team_a_odds"],
            "draw_odds": row["draw_odds"], "team_b_name": row["team_b_name"], "team_b_odds": row["team_b_odds"],
            "stream_type": row["stream_type"], "stream_url": row["stream_url"], "thumbnail_url": row["thumbnail_url"], "result": row["result"],
            "featured": bool(row["featured"]), "actual_start_at": row["actual_start_at"], "result_declared_at": row["result_declared_at"],
            "settled_at": row["settled_at"], "state_version": row["state_version"], "created_at": row["created_at"], "updated_at": row["updated_at"],
            "source": row["source"], "external_ref": row["external_ref"], "match_number": row["match_number"],
            "category_slug": row["category_slug"], "visible": bool(row["visible"]),
        }

    @staticmethod
    def banner_to_dict(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"], "title": row["title"], "subtitle": row["subtitle"], "placement": row["placement"],
            "image_url": row["image_url"], "media_url": row["media_url"], "media_type": row["media_type"], "duration": row["duration"],
            "cta_label": row["cta_label"], "cta_route": row["cta_route"],
            "starts_at": row["starts_at"], "ends_at": row["ends_at"], "sort_order": row["sort_order"],
            "active": bool(row["active"]), "created_at": row["created_at"], "updated_at": row["updated_at"],
        }

    @staticmethod
    def vip_to_dict(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"], "name": row["name"],
            "minimum_turnover": paise_to_rupees(row["minimum_turnover_paise"]),
            "cashback_percent": row["cashback_percent"], "withdrawal_priority": row["withdrawal_priority"],
            "color": row["color"], "active": bool(row["active"]),
        }

    def admin_overview(self) -> dict:
        with self.connect() as connection:
            users = connection.execute(
                "SELECT COUNT(*) AS total, COALESCE(SUM(balance_paise),0) AS balance, SUM(CASE WHEN vip_tier <> 'Standard' THEN 1 ELSE 0 END) AS vip FROM user_wallets"
            ).fetchone()
            payments = connection.execute(
                "SELECT COUNT(*) AS total, COALESCE(SUM(amount_paise),0) AS amount FROM payment_requests WHERE status = 'PENDING'"
            ).fetchone()
            games = connection.execute(
                "SELECT COUNT(*) AS total FROM admin_games WHERE status IN ('BETTING_OPEN','BETTING_CLOSED','LIVE')"
            ).fetchone()
            banners = connection.execute("SELECT COUNT(*) AS total FROM admin_banners WHERE active = 1").fetchone()
            recent = connection.execute("SELECT * FROM admin_audit_log ORDER BY created_at DESC,id DESC LIMIT 8").fetchall()
        overview = {
            "users": int(users["total"] or 0), "wallet_balance": paise_to_rupees(users["balance"]),
            "vip_users": int(users["vip"] or 0), "pending_payments": int(payments["total"] or 0),
            "pending_payment_amount": paise_to_rupees(payments["amount"]), "active_games": int(games["total"] or 0),
            "active_banners": int(banners["total"] or 0),
            "recent_activity": [dict(row) for row in recent],
        }
        overview["engine"] = self.cockfight.health()
        overview["streaming"] = self.streaming.health()
        return overview

    def admin_users(self) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT u.*, COUNT(p.id) AS payment_count,
                SUM(CASE WHEN p.status='PENDING' THEN 1 ELSE 0 END) AS pending_count,
                MAX(p.created_at) AS last_payment
                FROM user_wallets u LEFT JOIN payment_requests p ON p.user_id=u.user_id
                GROUP BY u.user_id ORDER BY u.created_at DESC"""
            ).fetchall()
        return [{
            "user_id": row["user_id"], "display_name": row["display_name"] or row["user_id"], "mobile": row["mobile"],
            "balance": paise_to_rupees(row["balance_paise"]), "status": row["account_status"], "vip_tier": row["vip_tier"],
            "payment_count": int(row["payment_count"] or 0), "pending_count": int(row["pending_count"] or 0),
            "last_payment": row["last_payment"] or "", "created_at": row["created_at"],
        } for row in rows]

    def admin_update_user(self, user_id: str, payload: dict) -> dict:
        if not USER_ID_PATTERN.fullmatch(user_id):
            raise ValueError("Invalid user identity.")
        status = str(payload.get("status") or "ACTIVE").upper()
        if status not in {"ACTIVE", "SUSPENDED", "BLOCKED"}:
            raise ValueError("Choose active, suspended, or blocked.")
        vip_tier = clean_text(payload.get("vip_tier") or "Standard", "VIP tier", 2, 40)
        with self.connect() as connection:
            if not connection.execute("SELECT 1 FROM admin_vip_tiers WHERE name = ?", (vip_tier,)).fetchone():
                raise ValueError("Choose an existing VIP tier.")
            if not connection.execute("SELECT 1 FROM user_wallets WHERE user_id = ?", (user_id,)).fetchone():
                raise LookupError("User not found.")
            connection.execute(
                "UPDATE user_wallets SET account_status=?,vip_tier=?,updated_at=? WHERE user_id=?",
                (status, vip_tier, utc_now(), user_id),
            )
            self._audit(connection, "Users", "Account updated", user_id, f"Status {status}; VIP {vip_tier}")
        return next(user for user in self.admin_users() if user["user_id"] == user_id)

    def admin_games(self) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM admin_games ORDER BY featured DESC,scheduled_at DESC,id DESC").fetchall()
        return [self.game_to_dict(row) for row in rows]

    def admin_save_game(self, payload: dict, game_id: int | None = None) -> dict:
        statuses = {"DRAFT", "SCHEDULED", "BETTING_OPEN", "BETTING_CLOSED", "LIVE", "AWAITING_RESULT", "SETTLED", "CANCELLED"}
        stream_types = {"OFFLINE", "VIDEO", "HLS", "YOUTUBE", "WHEP", "IFRAME"}
        now = utc_now()
        with self.connect() as connection:
            existing = connection.execute("SELECT * FROM admin_games WHERE id=?", (game_id,)).fetchone() if game_id else None
            if game_id and not existing:
                raise LookupError("Game not found.")
            current = dict(existing) if existing else {
                "title": "New cockfight", "arena": "Main Arena", "status": "DRAFT", "scheduled_at": now,
                "betting_opens_at": now, "betting_closes_at": now, "team_a_name": "Red", "team_a_odds": 2.45, "draw_odds": 8.75,
                "team_b_name": "Blue", "team_b_odds": 2.45, "stream_type": "OFFLINE", "stream_url": "", "thumbnail_url": "",
                "result": "", "featured": 0, "category_slug": "", "visible": 1,
            }
            category_slug = str(payload.get("category_slug", current["category_slug"]) or "").strip().lower()
            if category_slug:
                category = connection.execute("SELECT kind FROM game_categories WHERE slug=?", (category_slug,)).fetchone()
                if not category:
                    raise ValueError("Choose an existing game category.")
                if category["kind"] == "CHINA_FEED" and current.get("source", "MANUAL") != "CHINA_FEED":
                    raise ValueError("China 24/7 matches are created automatically by the feed.")
            visible = 1 if payload.get("visible", current["visible"]) else 0
            title = clean_text(payload.get("title", current["title"]), "Game title", 3, 90)
            arena = clean_text(payload.get("arena", current["arena"]), "Arena", 2, 60)
            status = str(payload.get("status", current["status"])).upper()
            stream_type = str(payload.get("stream_type", current["stream_type"])).upper()
            if status not in statuses:
                raise ValueError("Invalid game status.")
            if existing and status != current["status"]:
                raise ValueError("Use the match lifecycle controls to change game status.")
            if not existing and status not in {"DRAFT", "SCHEDULED"}:
                raise ValueError("A new game must begin as draft or scheduled.")
            if stream_type not in stream_types:
                raise ValueError("Invalid stream type.")
            odds = []
            for key in ("team_a_odds", "draw_odds", "team_b_odds"):
                try:
                    value = round(float(payload.get(key, current[key])), 2)
                except (TypeError, ValueError):
                    raise ValueError("Enter valid decimal odds.") from None
                if value < 1.01 or value > 100:
                    raise ValueError("Odds must be between 1.01 and 100.")
                odds.append(value)
            betting_opens_at = timestamp(payload.get("betting_opens_at", current["betting_opens_at"]), "Betting opens")
            betting_closes_at = timestamp(payload.get("betting_closes_at", current["betting_closes_at"]), "Betting closes")
            scheduled_at = timestamp(payload.get("scheduled_at", current["scheduled_at"]), "Scheduled start")
            team_a_name = clean_text(payload.get("team_a_name", current["team_a_name"]), "Red corner name", 1, 50)
            team_b_name = clean_text(payload.get("team_b_name", current["team_b_name"]), "Blue corner name", 1, 50)
            if parse_timestamp(betting_opens_at) > parse_timestamp(betting_closes_at):
                raise ValueError("Betting must open before it closes.")
            if parse_timestamp(betting_closes_at) > parse_timestamp(scheduled_at):
                raise ValueError("Betting must close before the scheduled match start.")
            if existing and current["status"] not in {"DRAFT", "SCHEDULED"}:
                original_schedule = tuple(timestamp(current[key], key.replace("_", " ").title()) for key in ("betting_opens_at", "betting_closes_at", "scheduled_at"))
                if (betting_opens_at, betting_closes_at, scheduled_at) != original_schedule:
                    raise ValueError("The match schedule is locked once betting opens.")
                if (team_a_name, team_b_name) != (current["team_a_name"], current["team_b_name"]):
                    raise ValueError("The match outcomes are locked once betting opens.")
                original_odds = tuple(round(float(current[key]), 2) for key in ("team_a_odds", "draw_odds", "team_b_odds"))
                if tuple(odds) != original_odds:
                    raise ValueError("Use the odds engine to publish an odds change.")
            values = (
                title, arena, status, betting_opens_at, scheduled_at, betting_closes_at,
                team_a_name, odds[0], odds[1], team_b_name, odds[2],
                stream_type, clean_media_url(payload.get("stream_url", current["stream_url"]), "Playback URL"),
                clean_media_url(payload.get("thumbnail_url", current["thumbnail_url"]), "Thumbnail URL"),
                current["result"], 1 if payload.get("featured", current["featured"]) else 0,
            )
            featured = bool(values[-1])
            if featured:
                connection.execute("UPDATE admin_games SET featured=0 WHERE id<>?", (game_id or 0,))
            if existing:
                connection.execute(
                    """UPDATE admin_games SET title=?,arena=?,status=?,betting_opens_at=?,scheduled_at=?,betting_closes_at=?,team_a_name=?,team_a_odds=?,draw_odds=?,team_b_name=?,team_b_odds=?,stream_type=?,stream_url=?,thumbnail_url=?,result=?,featured=?,category_slug=?,visible=?,updated_at=? WHERE id=?""",
                    (*values, category_slug, visible, now, game_id),
                )
                saved_id = game_id
                action = "Game updated"
            else:
                cursor = connection.execute(
                    """INSERT INTO admin_games(title,arena,status,betting_opens_at,scheduled_at,betting_closes_at,team_a_name,team_a_odds,draw_odds,team_b_name,team_b_odds,stream_type,stream_url,thumbnail_url,result,featured,category_slug,visible,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (*values, category_slug, visible, now, now),
                )
                saved_id = cursor.lastrowid
                action = "Game created"
            self._audit(connection, "Games", action, title, f"Status {status}")
            row = connection.execute("SELECT * FROM admin_games WHERE id=?", (saved_id,)).fetchone()
        self.cockfight.sync_game(saved_id, "ADMIN", current["status"] if existing else "")
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM admin_games WHERE id=?", (saved_id,)).fetchone()
        return self.game_to_dict(row)

    @staticmethod
    def category_to_dict(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"], "slug": row["slug"], "name": row["name"], "description": row["description"],
            "kind": row["kind"], "builtin": row["kind"] == "CHINA_FEED", "visible": bool(row["visible"]),
            "sort_order": row["sort_order"], "created_at": row["created_at"], "updated_at": row["updated_at"],
        }

    def admin_game_categories(self) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM game_categories ORDER BY sort_order ASC, name ASC").fetchall()
            counts = {row["category_slug"]: row["total"] for row in connection.execute("SELECT category_slug, COUNT(*) AS total FROM admin_games GROUP BY category_slug").fetchall()}
        feed_enabled = bool(self.china_feed.settings()["enabled"])
        categories = []
        for row in rows:
            item = self.category_to_dict(row)
            if item["builtin"]:
                item["visible"] = feed_enabled
            item["game_count"] = int(counts.get(item["slug"], 0))
            categories.append(item)
        return categories

    def admin_save_game_category(self, payload: dict, category_id: int | None = None, actor: str = "ADMIN") -> dict:
        now = utc_now()
        with self.connect() as connection:
            existing = connection.execute("SELECT * FROM game_categories WHERE id=?", (category_id,)).fetchone() if category_id else None
            if category_id and not existing:
                raise LookupError("Category not found.")
            name = clean_text(payload.get("name", existing["name"] if existing else ""), "Category name", 2, 60)
            description = str(payload.get("description", existing["description"] if existing else "") or "").strip()[:240]
            try:
                sort_order = int(payload.get("sort_order", existing["sort_order"] if existing else 100))
            except (TypeError, ValueError):
                raise ValueError("Sort order must be a whole number.") from None
            visible = 1 if payload.get("visible", existing["visible"] if existing else 1) else 0
            if existing and existing["kind"] == "CHINA_FEED":
                connection.execute("UPDATE game_categories SET name=?,description=?,sort_order=?,updated_at=? WHERE id=?", (name, description, sort_order, now, category_id))
                self._audit(connection, "Games", "Category updated", name, "Built-in China 24/7 category")
                saved_id = category_id
            elif existing:
                connection.execute("UPDATE game_categories SET name=?,description=?,visible=?,sort_order=?,updated_at=? WHERE id=?", (name, description, visible, sort_order, now, category_id))
                self._audit(connection, "Games", "Category updated", name, f"Visible {bool(visible)}")
                saved_id = category_id
            else:
                slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or f"category-{secrets.token_hex(3)}"
                if connection.execute("SELECT 1 FROM game_categories WHERE slug=?", (slug,)).fetchone():
                    raise ValueError("A category with this name already exists.")
                cursor = connection.execute(
                    "INSERT INTO game_categories(slug,name,description,kind,visible,sort_order,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                    (slug, name, description, "CUSTOM", visible, sort_order, now, now),
                )
                saved_id = cursor.lastrowid
                self._audit(connection, "Games", "Category created", name, f"Visible {bool(visible)}")
        if existing and existing["kind"] == "CHINA_FEED" and "visible" in payload:
            self.china_feed.update_settings({"enabled": bool(payload.get("visible"))}, actor=actor)
        return next(item for item in self.admin_game_categories() if item["id"] == saved_id)

    def admin_delete_game_category(self, category_id: int) -> None:
        with self.connect() as connection:
            existing = connection.execute("SELECT * FROM game_categories WHERE id=?", (category_id,)).fetchone()
            if not existing:
                raise LookupError("Category not found.")
            if existing["kind"] == "CHINA_FEED":
                raise ValueError("The China 24/7 category is built in. Switch it off instead of deleting it.")
            connection.execute("UPDATE admin_games SET category_slug='' WHERE category_slug=?", (existing["slug"],))
            connection.execute("DELETE FROM game_categories WHERE id=?", (category_id,))
            self._audit(connection, "Games", "Category deleted", existing["name"], "Games moved to uncategorised")

    def admin_set_game_visibility(self, game_id: int, visible: bool) -> dict:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM admin_games WHERE id=?", (game_id,)).fetchone()
            if not row:
                raise LookupError("Game not found.")
            connection.execute("UPDATE admin_games SET visible=?,updated_at=? WHERE id=?", (1 if visible else 0, utc_now(), game_id))
            self._audit(connection, "Games", "Game visibility", row["title"], "Shown to players" if visible else "Hidden from players")
            row = connection.execute("SELECT * FROM admin_games WHERE id=?", (game_id,)).fetchone()
        return self.game_to_dict(row)

    def player_visible_games(self, games: list[dict] | None = None) -> list[dict]:
        games = self.admin_games() if games is None else games
        hidden_categories = {item["slug"] for item in self.admin_game_categories() if not item["visible"]}
        return [game for game in games if game["visible"] and game["category_slug"] not in hidden_categories]

    def admin_banners(self, active_only: bool = False) -> list[dict]:
        query = "SELECT * FROM admin_banners"
        parameters: tuple = ()
        if active_only:
            now = utc_now()
            query += " WHERE active=1 AND (starts_at='' OR starts_at<=?) AND (ends_at='' OR ends_at>?)"
            parameters = (now, now)
        query += " ORDER BY sort_order ASC,id DESC"
        with self.connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [self.banner_to_dict(row) for row in rows]

    def admin_save_banner(self, payload: dict, banner_id: int | None = None) -> dict:
        now = utc_now()
        with self.connect() as connection:
            existing = connection.execute("SELECT * FROM admin_banners WHERE id=?", (banner_id,)).fetchone() if banner_id else None
            if banner_id and not existing:
                raise LookupError("Banner not found.")
            current = dict(existing) if existing else {"title":"New content","subtitle":"","placement":"HOME_HERO","image_url":"","media_url":"","media_type":"IMAGE","duration":"","cta_label":"","cta_route":"","starts_at":"","ends_at":"","sort_order":0,"active":1}
            placement = str(payload.get("placement", current["placement"])).upper()
            if placement not in {"HOME_HERO", "HOME_LIVE", "HOME_VIDEO", "HOME_HIGHLIGHT", "HOME_YOUTUBE", "LIVE", "WALLET"}:
                raise ValueError("Invalid content placement.")
            media_type = str(payload.get("media_type", current["media_type"])).upper()
            if media_type not in {"IMAGE", "VIDEO", "YOUTUBE", "EXTERNAL"}:
                raise ValueError("Invalid media type.")
            duration = str(payload.get("duration", current["duration"])).strip()
            if duration and not re.fullmatch(r"(?:\d{1,2}:)?\d{1,2}:\d{2}", duration):
                raise ValueError("Duration must use MM:SS or HH:MM:SS.")
            try:
                sort_order = int(payload.get("sort_order", current["sort_order"]))
            except (TypeError, ValueError):
                raise ValueError("Sort order must be a number.") from None
            image_url = clean_media_url(payload.get("image_url", current["image_url"]), "Thumbnail image URL")
            media_url = clean_media_url(payload.get("media_url", current["media_url"]), "Video URL")
            if placement.startswith("HOME_") and not image_url:
                raise ValueError("Upload or link a thumbnail image for home content.")
            if placement in {"HOME_VIDEO", "HOME_HIGHLIGHT", "HOME_YOUTUBE"} and media_type != "IMAGE" and not media_url:
                raise ValueError("Upload or link the video source for this home section.")
            values = (
                clean_text(payload.get("title", current["title"]), "Content title", 2, 100),
                str(payload.get("subtitle", current["subtitle"])).strip()[:180], placement,
                image_url, media_url,
                media_type, duration,
                str(payload.get("cta_label", current["cta_label"])).strip()[:40],
                str(payload.get("cta_route", current["cta_route"])).strip()[:150],
                str(payload.get("starts_at", current["starts_at"])), str(payload.get("ends_at", current["ends_at"])),
                sort_order, 1 if payload.get("active", current["active"]) else 0,
            )
            if existing:
                connection.execute("""UPDATE admin_banners SET title=?,subtitle=?,placement=?,image_url=?,media_url=?,media_type=?,duration=?,cta_label=?,cta_route=?,starts_at=?,ends_at=?,sort_order=?,active=?,updated_at=? WHERE id=?""", (*values,now,banner_id))
                saved_id = banner_id
                action = "Banner updated"
            else:
                cursor = connection.execute("""INSERT INTO admin_banners(title,subtitle,placement,image_url,media_url,media_type,duration,cta_label,cta_route,starts_at,ends_at,sort_order,active,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (*values,now,now))
                saved_id = cursor.lastrowid
                action = "Banner created"
            row = connection.execute("SELECT * FROM admin_banners WHERE id=?", (saved_id,)).fetchone()
            self._audit(connection, "Banners", action, row["title"], row["placement"])
        return self.banner_to_dict(row)

    def admin_vip_tiers(self, active_only: bool = False) -> list[dict]:
        query = "SELECT * FROM admin_vip_tiers" + (" WHERE active=1" if active_only else "") + " ORDER BY minimum_turnover_paise ASC,id ASC"
        with self.connect() as connection:
            rows = connection.execute(query).fetchall()
        return [self.vip_to_dict(row) for row in rows]

    def admin_save_vip(self, payload: dict, tier_id: int | None = None) -> dict:
        now = utc_now()
        with self.connect() as connection:
            existing = connection.execute("SELECT * FROM admin_vip_tiers WHERE id=?", (tier_id,)).fetchone() if tier_id else None
            if tier_id and not existing:
                raise LookupError("VIP tier not found.")
            current = dict(existing) if existing else {"name":"New tier","minimum_turnover_paise":0,"cashback_percent":0,"withdrawal_priority":0,"color":"#F1B93D","active":1}
            name = clean_text(payload.get("name", current["name"]), "Tier name", 2, 40)
            minimum = money_to_paise(payload.get("minimum_turnover", paise_to_rupees(current["minimum_turnover_paise"])), 0, 100_000_000)
            try:
                cashback = round(float(payload.get("cashback_percent", current["cashback_percent"])), 2)
                priority = int(payload.get("withdrawal_priority", current["withdrawal_priority"]))
            except (TypeError, ValueError):
                raise ValueError("Enter valid VIP values.") from None
            if cashback < 0 or cashback > 25 or priority < 0 or priority > 20:
                raise ValueError("VIP values are outside the allowed range.")
            color = str(payload.get("color", current["color"])).upper()
            if not re.fullmatch(r"#[0-9A-F]{6}", color):
                raise ValueError("Enter a valid six-digit color.")
            values = (name, minimum, cashback, priority, color, 1 if payload.get("active", current["active"]) else 0)
            if existing:
                connection.execute("UPDATE admin_vip_tiers SET name=?,minimum_turnover_paise=?,cashback_percent=?,withdrawal_priority=?,color=?,active=?,updated_at=? WHERE id=?", (*values,now,tier_id))
                saved_id = tier_id
                action = "VIP tier updated"
            else:
                cursor = connection.execute("INSERT INTO admin_vip_tiers(name,minimum_turnover_paise,cashback_percent,withdrawal_priority,color,active,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)", (*values,now,now))
                saved_id = cursor.lastrowid
                action = "VIP tier created"
            row = connection.execute("SELECT * FROM admin_vip_tiers WHERE id=?", (saved_id,)).fetchone()
            self._audit(connection, "VIP", action, name, f"Cashback {cashback}%")
        return self.vip_to_dict(row)

    def admin_config(self) -> dict:
        with self.connect() as connection:
            settings = connection.execute("SELECT * FROM admin_settings ORDER BY setting_key").fetchall()
            social = connection.execute("SELECT * FROM admin_social_links ORDER BY id").fetchall()
            roles = connection.execute("SELECT * FROM admin_roles ORDER BY id").fetchall()
        result = {row["setting_key"]: json.loads(row["setting_value"] or "{}") for row in settings}
        result["social"] = [{"id":row["id"],"platform":row["platform"],"url":row["url"],"active":bool(row["active"])} for row in social]
        result["roles"] = [{"id":row["id"],"name":row["name"],"permissions":json.loads(row["permissions"] or "[]"),"protected":bool(row["protected"])} for row in roles]
        return result

    def admin_update_config(self, payload: dict) -> dict:
        allowed = {"brand", "theme", "general", "responsible", "notifications"}
        now = utc_now()
        with self.connect() as connection:
            for key, value in payload.items():
                if key not in allowed or not isinstance(value, dict):
                    raise ValueError("Invalid settings group.")
                if key == "theme":
                    for color_key in ("primary", "primary_bright", "background", "surface", "text", "danger", "success"):
                        color = str(value.get(color_key, ""))
                        if color and not re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
                            raise ValueError(f"{color_key.replace('_',' ').title()} must be a six-digit color.")
                if key == "brand":
                    value = dict(value)
                    value["logo_url"] = clean_media_url(value.get("logo_url"), "Logo URL")
                    if value.get("favicon_url"):
                        value["favicon_url"] = clean_media_url(value.get("favicon_url"), "Favicon URL")
                connection.execute(
                    "INSERT INTO admin_settings(setting_key,setting_value,updated_at) VALUES(?,?,?) ON CONFLICT(setting_key) DO UPDATE SET setting_value=excluded.setting_value,updated_at=excluded.updated_at",
                    (key, json.dumps(value), now),
                )
                self._audit(connection, "Settings", "Configuration updated", key, ", ".join(value.keys()))
        return self.admin_config()

    def admin_save_logo(self, payload: dict) -> dict:
        filename = self.save_image(payload.get("logo_data_url"), "site-logo")
        config = self.admin_config().get("brand", {})
        config["logo_url"] = f"/uploads/{filename}"
        return self.admin_update_config({"brand": config})["brand"]

    def admin_update_social(self, payload: dict) -> list[dict]:
        links = payload.get("links")
        if not isinstance(links, list) or not links:
            raise ValueError("Provide at least one social link.")
        now = utc_now()
        with self.connect() as connection:
            for link in links:
                platform = clean_text(link.get("platform"), "Platform", 1, 40)
                url = str(link.get("url") or "").strip()[:500]
                if url and not re.match(r"^https://", url, re.I):
                    raise ValueError("Social links must use HTTPS.")
                connection.execute(
                    "INSERT INTO admin_social_links(platform,url,active,updated_at) VALUES(?,?,?,?) ON CONFLICT(platform) DO UPDATE SET url=excluded.url,active=excluded.active,updated_at=excluded.updated_at",
                    (platform, url, 1 if link.get("active", True) else 0, now),
                )
            self._audit(connection, "Social", "Social links updated", "Public profiles", f"{len(links)} links")
        return self.admin_config()["social"]

    def admin_audit(self, limit: int = 100) -> list[dict]:
        limit = max(1, min(int(limit), 200))
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM admin_audit_log ORDER BY created_at DESC,id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]

    def public_site_config(self) -> dict:
        config = self.admin_config()
        games = [game for game in self.player_visible_games() if game["status"] not in {"DRAFT", "CANCELLED", "SETTLED"}]
        featured_game = next((game for game in games if game["featured"]), games[0] if games else None)
        categories = [item for item in self.admin_game_categories() if item["visible"]]
        compliance = self.compliance.policy()
        return {
            "brand": config.get("brand", {}), "theme": config.get("theme", {}),
            "social": [link for link in config.get("social", []) if link["active"] and link["url"]],
            "banners": self.admin_banners(True), "vip_tiers": self.admin_vip_tiers(True),
            "featured_game": featured_game,
            "games": games,
            "categories": [{"slug": item["slug"], "name": item["name"], "description": item["description"], "builtin": item["builtin"]} for item in categories],
            "stream": self.streaming.current_stream(featured_game["id"]) if featured_game else {"status": "OFFLINE", "playback_url": ""},
            "china_feed": self.china_feed.current(),
            "operating_mode": compliance.get("operating_mode", "SOCIAL_PREVIEW"),
            "legal_notice": compliance.get("legal_notice", ""),
            "identity_review_required": any(compliance.get(key) for key in ("kyc_required_for_betting", "kyc_required_for_deposit", "kyc_required_for_withdrawal")),
        }

    def readiness(self, server: "RoosterRunServer | None" = None) -> dict:
        """Return deployment readiness without exposing secrets or user data."""
        checks: dict[str, dict] = {}
        try:
            with self.connect() as connection:
                connection.execute("SELECT 1").fetchone()
                admin_count = int(connection.execute("SELECT COUNT(*) FROM admin_accounts WHERE active=1").fetchone()[0])
            require_postgres = os.environ.get("ROOSTERRUN_REQUIRE_POSTGRES", "0" if self.preview_mode else "1").strip().lower() not in {"0", "false", "no"}
            require_database_tls = os.environ.get("ROOSTERRUN_REQUIRE_DATABASE_TLS", "0" if self.preview_mode else "1").strip().lower() not in {"0", "false", "no"}
            database_ok = (not require_postgres or self.database.backend == "postgresql") and (not require_database_tls or self.database.uses_tls())
            checks["database"] = {"ok": database_ok, "detail": f"{self.database.describe()} is writable and queryable." if database_ok else "Production requires PostgreSQL with TLS."}
            checks["administrator"] = {"ok": self.preview_mode or admin_count > 0, "detail": "Configured" if admin_count else "No active administrator"}
        except Exception:
            checks["database"] = {"ok": False, "detail": "Database check failed."}
            checks["administrator"] = {"ok": False, "detail": "Could not verify administrators."}

        storage_ok = all(path.is_dir() and os.access(path, os.R_OK | os.W_OK) for path in (self.data_dir, self.upload_dir, self.private_payment_dir))
        checks["storage"] = {"ok": storage_ok, "detail": "Writable" if storage_ok else "Data storage is not writable"}
        require_offsite = os.environ.get("ROOSTERRUN_REQUIRE_OFFSITE_BACKUP", "0" if self.preview_mode else "1").strip().lower() not in {"0", "false", "no"}
        recovery_dir = Path(os.environ.get("ROOSTERRUN_RECOVERY_STATE_DIR", "/restore-state"))
        backup_marker = recovery_dir / "last-backup-success.json"
        restore_marker = recovery_dir / "last-restore-drill.json"
        def recent_recovery_marker(path: Path, maximum_age_days: int) -> bool:
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
                completed = datetime.fromisoformat(str(record["completed_at"]).replace("Z", "+00:00"))
                if completed.tzinfo is None:
                    completed = completed.replace(tzinfo=timezone.utc)
                age = datetime.now(timezone.utc) - completed.astimezone(timezone.utc)
                return timedelta(0) <= age <= timedelta(days=maximum_age_days)
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
                return False
        recovery_ok = (not require_offsite) or (recent_recovery_marker(backup_marker, 2) and recent_recovery_marker(restore_marker, 90))
        checks["offsite_recovery"] = {
            "ok": recovery_ok,
            "detail": "Verified backup and restore drill" if recovery_ok and require_offsite else ("Not required" if not require_offsite else "Run an encrypted off-site backup and isolated restore drill"),
        }
        checks["operating_mode"] = {
            "ok": self.operating_mode in OPERATING_MODES,
            "detail": OPERATING_MODE_LABELS.get(self.operating_mode, self.operating_mode),
        }
        checks["secret_rotation"] = secret_rotation_status(self.preview_mode)

        otp_test_enabled = bool(self.auth.otp_test_mode and not self.preview_mode)
        sms_ok = self.preview_mode or (self.delivery.sms_configured and not otp_test_enabled)
        checks["identity"] = {
            "ok": sms_ok,
            "detail": "Configured" if sms_ok else "Configure an HTTPS SMS webhook and disable OTP test mode",
        }

        require_streaming = os.environ.get("ROOSTERRUN_REQUIRE_STREAMING", "0" if self.preview_mode else "1").strip().lower() not in {"0", "false", "no"}
        require_recording = os.environ.get("ROOSTERRUN_REQUIRE_RECORDING", "0" if self.preview_mode else "1").strip().lower() not in {"0", "false", "no"}
        require_media_health = os.environ.get("ROOSTERRUN_REQUIRE_MEDIA_HEALTH", "0" if self.preview_mode else "1").strip().lower() not in {"0", "false", "no"}
        stream_urls_secure = self.preview_mode or all(
            not value or value.startswith("https://")
            for value in (self.streaming.whip_base, self.streaming.whep_base, self.streaming.hls_base, self.streaming.recording_base)
        )
        streaming_ok = (not require_streaming) or (
            self.streaming.media_plane_configured and stream_urls_secure and len(self.streaming.hook_secret) >= 32
            and (not require_recording or bool(self.streaming.recording_base))
            and (not require_media_health or (bool(self.streaming.media_health_url) and self.streaming.media_plane_reachable))
        )
        checks["streaming"] = {
            "ok": streaming_ok,
            "detail": "Configured and reachable" if streaming_ok else "Configure reachable SRS, HTTPS WHIP/WHEP/HLS/recording URLs, and a 32+ character hook secret",
        }

        require_alerts = os.environ.get("ROOSTERRUN_REQUIRE_EXTERNAL_ALERTS", "0" if self.preview_mode else "1").strip().lower() not in {"0", "false", "no"}
        alerts_ok = (not require_alerts) or self.delivery.alerts_configured
        checks["external_alerts"] = {
            "ok": alerts_ok,
            "detail": "Configured" if alerts_ok else "Configure an HTTPS alert webhook or an SMS/email alert destination",
        }

        background_ok = bool(
            self.cockfight._scheduler and self.cockfight._scheduler.is_alive()
            and self.streaming._monitor and self.streaming._monitor.is_alive()
            and self.delivery._worker and self.delivery._worker.is_alive()
        )
        checks["background_workers"] = {"ok": background_ok, "detail": "Running" if background_ok else "Workers are not running"}
        if server is not None:
            cookie_ok = self.preview_mode or server.secure_cookies
            checks["secure_cookies"] = {"ok": cookie_ok, "detail": "Enabled" if cookie_ok else "Secure cookies are disabled"}

        return {
            "status": "ready" if all(item["ok"] for item in checks.values()) else "not_ready",
            "mode": "preview" if self.preview_mode else "production",
            "operating_mode": self.operating_mode,
            "time": utc_now(),
            "checks": checks,
        }


class LivePresence:
    """Shared viewer counter shown on the arena: a smooth random walk between the configured
    bounds (same value for every player), plus the clients genuinely polling the live arena."""

    WINDOW_SECONDS = 30

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._seen: dict[str, float] = {}
        low = int(os.environ.get("ROOSTERRUN_VIEWERS_MIN", "8000") or 0)
        high = int(os.environ.get("ROOSTERRUN_VIEWERS_MAX", "15000") or 0)
        self._low, self._high = max(0, min(low, high)), max(0, max(low, high))
        self._simulated = float(random.randint(self._low, self._high)) if self._high else 0.0
        self._target = self._simulated
        self._last_step = time.monotonic()

    def _advance(self, now: float) -> None:
        if not self._high:
            return
        elapsed = now - self._last_step
        if elapsed < 3:
            return
        self._last_step = now
        span = max(self._high - self._low, 1)
        if abs(self._target - self._simulated) < span * 0.01 or random.random() < 0.08:
            self._target = random.uniform(self._low, self._high)
        # Drift a few percent of the gap per tick with a little jitter so the count moves like a crowd.
        self._simulated += (self._target - self._simulated) * random.uniform(0.04, 0.12) + random.uniform(-span * 0.004, span * 0.004)
        self._simulated = min(max(self._simulated, self._low), self._high)

    def _real(self, now: float) -> int:
        cutoff = now - self.WINDOW_SECONDS
        for key in [key for key, stamp in self._seen.items() if stamp < cutoff]:
            del self._seen[key]
        return len(self._seen)

    def touch(self, client_key: str) -> int:
        now = time.monotonic()
        with self._lock:
            self._seen[client_key] = now
            self._advance(now)
            return int(self._simulated) + self._real(now)

    def count(self) -> int:
        now = time.monotonic()
        with self._lock:
            self._advance(now)
            return int(self._simulated) + self._real(now)


class RoosterRunServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 128

    def __init__(self, address: tuple[str, int], handler, payments: PaymentService, preview_mode: bool):
        super().__init__(address, handler)
        self.payments = payments
        self.preview_mode = preview_mode
        secure_default = "0" if preview_mode else "1"
        self.secure_cookies = os.environ.get("ROOSTERRUN_SECURE_COOKIES", secure_default).strip().lower() not in {"0", "false", "no"}
        self.trust_proxy = os.environ.get("ROOSTERRUN_TRUST_PROXY", "0").strip().lower() in {"1", "true", "yes"}
        self.presence = LivePresence()
        try:
            max_requests = int(os.environ.get("ROOSTERRUN_MAX_CONCURRENT_REQUESTS", "64"))
        except ValueError:
            max_requests = 64
        self.request_slots = threading.BoundedSemaphore(max(8, min(max_requests, 256)))

    def process_request(self, request, client_address) -> None:
        self.request_slots.acquire()
        try:
            super().process_request(request, client_address)
        except Exception:
            self.request_slots.release()
            raise

    def process_request_thread(self, request, client_address) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.request_slots.release()


class RequestHandler(BaseHTTPRequestHandler):
    server: RoosterRunServer
    server_version = "RoosterRun"
    sys_version = ""

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(30)

    def handle_one_request(self) -> None:
        started = time.monotonic()
        self._response_status = 500
        try:
            super().handle_one_request()
        except Exception as error:
            self.server.payments.metrics.observe_exception(type(error).__name__)
            raise
        finally:
            method = getattr(self, "command", "UNKNOWN")
            path = getattr(self, "path", "/")
            self.server.payments.metrics.observe_request(method, path, self._response_status, time.monotonic() - started)

    def send_response(self, code: int, message: str | None = None) -> None:
        self._response_status = int(code)
        super().send_response(code, message)

    def log_message(self, fmt: str, *args: object) -> None:
        message = fmt % args
        message = re.sub(r"(?i)(secret|token|ticket|code)=([^&\s]+)", r"\1=[REDACTED]", message)
        self.server.payments.logger.emit(
            "INFO", "http_request", method=getattr(self, "command", ""),
            path=urlparse(getattr(self, "path", "/")).path,
            status=getattr(self, "_response_status", 0), client_ip=self.client_ip(), message=message,
        )

    def send_json(self, status: int, data: object, cookies: list[str] | None = None) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        if not self.server.preview_mode and self.server.secure_cookies:
            self.send_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        for cookie in cookies or []:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)

    def send_private_file(self, path: Path, content_type: str, filename: str = "verification", attachment: bool = False) -> None:
        size = path.stat().st_size
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(size))
        self.send_header("Cache-Control", "no-store, private")
        disposition = "attachment" if attachment else "inline"
        safe_name = re.sub(r"[^A-Za-z0-9._-]", "-", filename)[:160] or f"private{path.suffix}"
        self.send_header("Content-Disposition", f'{disposition}; filename="{safe_name}"')
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        if not self.server.preview_mode and self.server.secure_cookies:
            self.send_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        self.end_headers()
        with path.open("rb") as handle:
            while chunk := handle.read(64 * 1024):
                self.wfile.write(chunk)

    def send_private_bytes(self, body: bytes, content_type: str, filename: str) -> None:
        safe_name = re.sub(r"[^A-Za-z0-9._-]", "-", filename)[:160] or "export.bin"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, private")
        self.send_header("Content-Disposition", f'attachment; filename="{safe_name}"')
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        if not self.server.preview_mode and self.server.secure_cookies:
            self.send_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            raise ValueError("Invalid request length.") from None
        if length <= 0 or length > MAX_JSON_BYTES:
            raise ValueError("Request payload is empty or too large.")
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ValueError("Request body must be valid JSON.") from None
        if not isinstance(payload, dict):
            raise ValueError("Request body must be an object.")
        return payload

    def cookie(self, name: str) -> str:
        raw = self.headers.get("Cookie", "")
        if not raw:
            return ""
        try:
            parsed = SimpleCookie()
            parsed.load(raw)
            return parsed[name].value if name in parsed else ""
        except Exception:
            return ""

    def client_ip(self) -> str:
        peer = str(self.client_address[0])
        if self.server.trust_proxy:
            try:
                peer_address = ipaddress.ip_address(peer)
                forwarded = self.headers.get("X-Forwarded-For", "").split(",", 1)[0].strip()
                forwarded_address = ipaddress.ip_address(forwarded)
                if peer_address.is_private or peer_address.is_loopback:
                    return str(forwarded_address)
            except ValueError:
                pass
        return peer

    def presence_key(self) -> str:
        session = self.cookie(USER_SESSION_COOKIE)
        raw = session or f"{self.client_ip()}|{self.headers.get('User-Agent', '')}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

    def request_context(self, actor_id: object, actor_role: object) -> None:
        AUDIT_CONTEXT.set(
            {
                "actor_id": str(actor_id or "SYSTEM"),
                "actor_role": str(actor_role or "SYSTEM"),
                "request_id": self.headers.get("X-Request-ID", "") or secrets.token_hex(8),
                "ip_address": self.client_ip(),
            }
        )

    def user_identity(self, mutate: bool = False) -> dict:
        session_token = self.cookie(USER_SESSION_COOKIE)
        if not session_token and self.server.preview_mode and self.client_ip() in {"127.0.0.1", "::1"}:
            return self.server.payments.cockfight.user_profile("arena-guest")
        csrf = self.headers.get("X-CSRF-Token", "") if mutate else ""
        return self.server.payments.auth.authenticate_user(session_token, csrf, mutate)

    def user_id(self, mutate: bool = False) -> str:
        identity = self.user_identity(mutate)
        user_id = str(identity.get("id") or "")
        if not USER_ID_PATTERN.fullmatch(user_id):
            raise AuthenticationError("The player identity is invalid.")
        return user_id

    def bearer_token(self) -> str:
        authorization = self.headers.get("Authorization", "").strip()
        if not authorization.lower().startswith("bearer "):
            raise PermissionError("Broadcast authorization is required.")
        return authorization[7:].strip()

    def require_admin(self, permission: str = "overview", mutate: bool = False) -> dict:
        client_ip = self.client_ip()
        is_loopback = client_ip in {"127.0.0.1", "::1"}
        direct_private_preview = self.path.startswith(
            ("/api/admin/compliance/documents/", "/api/admin/operations/backups/", "/api/payments/admin/requests/")
        )
        if self.server.preview_mode and is_loopback and (self.headers.get("X-Preview-Admin") == "1" or direct_private_preview):
            identity = {"id": "preview-admin", "display_name": "Preview Admin", "role": "Super Admin", "permissions": ["*"], "mfa_enabled": False}
            self.request_context(identity["id"], identity["role"])
            return identity
        identity = self.server.payments.auth.authenticate_admin(
            self.cookie(ADMIN_SESSION_COOKIE),
            self.headers.get("X-CSRF-Token", "") if mutate else "",
            mutate,
            permission,
        )
        self.request_context(identity["id"], identity["role"])
        return identity

    @staticmethod
    def admin_permission(path: str) -> str:
        if path.startswith("/api/admin/intelligence"):
            return "intelligence"
        if path.startswith("/api/admin/support"):
            return "support"
        if path.startswith("/api/admin/operations"):
            return "operations"
        if path.startswith("/api/admin/compliance"):
            return "compliance"
        if path.startswith("/api/payments/admin/"):
            return "payments"
        if path.startswith("/api/admin/users"):
            return "users"
        if path.startswith("/api/admin/games") or path.startswith("/api/admin/game-categories") or path.startswith("/api/admin/streams") or path in {"/api/admin/risk/", "/api/admin/china-feed/", "/api/admin/china-feed/poll/", "/api/admin/china-feed/recover/"}:
            return "games"
        if path.startswith("/api/admin/banners"):
            return "banners"
        if path.startswith("/api/admin/vip"):
            return "vip"
        if path.startswith("/api/admin/social"):
            return "social"
        if path.startswith("/api/admin/assets"):
            return "assets"
        if path.startswith("/api/admin/team") or path.startswith("/api/admin/auth/mfa"):
            return "team"
        if path.startswith("/api/admin/audit"):
            return "audit"
        if path.startswith("/api/admin/config") or path.startswith("/api/admin/logo"):
            return "settings"
        return "overview"

    def session_cookies(self, auth_result: dict, admin: bool = False) -> tuple[dict, list[str]]:
        result = dict(auth_result)
        session_token = result.pop("session_token")
        csrf_token = result.pop("csrf_token")
        session_name = ADMIN_SESSION_COOKIE if admin else USER_SESSION_COOKIE
        csrf_name = ADMIN_CSRF_COOKIE if admin else USER_CSRF_COOKIE
        max_age = int((timedelta(hours=4) if admin else timedelta(hours=12)).total_seconds())
        secure = "; Secure" if self.server.secure_cookies else ""
        cookies = [
            f"{session_name}={session_token}; Path=/; Max-Age={max_age}; HttpOnly; SameSite=Strict{secure}",
            f"{csrf_name}={csrf_token}; Path=/; Max-Age={max_age}; SameSite=Strict{secure}",
        ]
        result["authenticated"] = True
        return result, cookies

    def clear_session_cookies(self, admin: bool = False) -> list[str]:
        session_name = ADMIN_SESSION_COOKIE if admin else USER_SESSION_COOKIE
        csrf_name = ADMIN_CSRF_COOKIE if admin else USER_CSRF_COOKIE
        secure = "; Secure" if self.server.secure_cookies else ""
        return [
            f"{session_name}=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict{secure}",
            f"{csrf_name}=; Path=/; Max-Age=0; SameSite=Strict{secure}",
        ]

    def handle_api_error(self, error: Exception) -> None:
        if isinstance(error, AuthenticationError):
            self.send_json(HTTPStatus.UNAUTHORIZED, {"detail": str(error)})
        elif isinstance(error, RateLimitError):
            self.send_json(HTTPStatus.TOO_MANY_REQUESTS, {"detail": str(error)})
        elif isinstance(error, PermissionError):
            self.send_json(HTTPStatus.FORBIDDEN, {"detail": str(error)})
        elif isinstance(error, LookupError):
            self.send_json(HTTPStatus.NOT_FOUND, {"detail": str(error)})
        elif isinstance(error, ValueError):
            self.send_json(HTTPStatus.BAD_REQUEST, {"detail": str(error)})
        else:
            self.log_error("Unhandled error: %r", error)
            self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"detail": "The request could not be completed."})

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if path == "/health/live/":
            return self.send_json(HTTPStatus.OK, {"status": "alive", "time": utc_now()})
        if path == "/health/ready/":
            readiness = self.server.payments.readiness(self.server)
            status = HTTPStatus.OK if readiness["status"] == "ready" else HTTPStatus.SERVICE_UNAVAILABLE
            return self.send_json(status, readiness)
        if path == "/metrics/":
            body = self.server.payments.metrics.render(self.server.payments)
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/site/config/":
            try:
                payload = self.server.payments.public_site_config()
                payload["viewers"] = self.server.presence.count()
                return self.send_json(HTTPStatus.OK, payload)
            except Exception as error:
                return self.handle_api_error(error)
        if path.startswith("/api/user/"):
            try:
                if path == "/api/user/me/":
                    return self.send_json(HTTPStatus.OK, self.server.payments.cockfight.user_profile(self.user_id()))
                if path == "/api/user/statement/":
                    return self.send_json(HTTPStatus.OK, {"results": self.server.payments.cockfight.statement(self.user_id())})
                if path == "/api/user/compliance/":
                    return self.send_json(HTTPStatus.OK, self.server.payments.compliance.profile(self.user_id()))
                if path == "/api/user/responsible-play/":
                    return self.send_json(HTTPStatus.OK, self.server.payments.compliance.controls(self.user_id()))
                if path == "/api/user/notifications/":
                    return self.send_json(HTTPStatus.OK, self.server.payments.operations.list_user_notifications(self.user_id()))
                if path == "/api/user/support/tickets/":
                    return self.send_json(HTTPStatus.OK, {"results": self.server.payments.support.list_user(self.user_id())})
                return self.send_json(HTTPStatus.NOT_FOUND, {"detail": "User endpoint not found."})
            except Exception as error:
                return self.handle_api_error(error)
        if path.startswith("/api/cockfight/"):
            try:
                if path == "/api/cockfight/engine/health/":
                    return self.send_json(HTTPStatus.OK, self.server.payments.cockfight.health())
                if path == "/api/cockfight/odds/current/":
                    game_value = (query.get("game_id") or [""])[0]
                    return self.send_json(HTTPStatus.OK, self.server.payments.cockfight.current_odds(int(game_value) if game_value else None))
                if path == "/api/cockfight/bets/":
                    return self.send_json(HTTPStatus.OK, {"results": self.server.payments.cockfight.list_bets(self.user_id())})
                if path in {"/api/cockfight/manual-history/", "/api/cockfight/auto-history/"}:
                    limit = int((query.get("limit") or ["20"])[0])
                    return self.send_json(HTTPStatus.OK, {"results": self.server.payments.cockfight.history(limit)})
                if path == "/api/cockfight/events/":
                    after = int((query.get("after") or ["0"])[0])
                    viewers = self.server.presence.touch(self.presence_key())
                    return self.send_json(HTTPStatus.OK, {"results": self.server.payments.cockfight.events(after), "viewers": viewers})
                if path == "/api/cockfight/stream/current/":
                    game_value = (query.get("game_id") or [""])[0]
                    return self.send_json(HTTPStatus.OK, self.server.payments.streaming.current_stream(int(game_value) if game_value else None))
                if path == "/api/cockfight/stream/health/":
                    return self.send_json(HTTPStatus.OK, self.server.payments.streaming.health())
                if path == "/api/cockfight/china/current/":
                    return self.send_json(HTTPStatus.OK, self.server.payments.china_feed.current())
                return self.send_json(HTTPStatus.NOT_FOUND, {"detail": "Cockfight endpoint not found."})
            except Exception as error:
                return self.handle_api_error(error)
        if path.startswith("/api/admin/"):
            try:
                if path == "/api/admin/auth/session/":
                    identity = self.require_admin("overview")
                    return self.send_json(HTTPStatus.OK, {"authenticated": True, "admin": identity})
                permission = "overview" if path in {"/api/admin/config/", "/api/admin/vip/"} else self.admin_permission(path)
                self.require_admin(permission)
                if path == "/api/admin/health/":
                    return self.send_json(HTTPStatus.OK, {"status": "ok", "preview": self.server.preview_mode, "time": utc_now(), "cockfight": self.server.payments.cockfight.health(), "china_feed": self.server.payments.china_feed.health(), "streaming": self.server.payments.streaming.health(), "compliance": self.server.payments.compliance.health(), "operations": {"status": "ok"}, "support": self.server.payments.support.health(), "intelligence": self.server.payments.intelligence.health()})
                if path == "/api/admin/overview/":
                    return self.send_json(HTTPStatus.OK, self.server.payments.admin_overview())
                if path == "/api/admin/users/":
                    return self.send_json(HTTPStatus.OK, {"results": self.server.payments.admin_users()})
                if path == "/api/admin/games/":
                    return self.send_json(HTTPStatus.OK, {"results": self.server.payments.admin_games()})
                if path == "/api/admin/banners/":
                    return self.send_json(HTTPStatus.OK, {"results": self.server.payments.admin_banners()})
                if path == "/api/admin/vip/":
                    return self.send_json(HTTPStatus.OK, {"results": self.server.payments.admin_vip_tiers()})
                if path == "/api/admin/config/":
                    return self.send_json(HTTPStatus.OK, self.server.payments.admin_config())
                if path == "/api/admin/risk/":
                    return self.send_json(HTTPStatus.OK, self.server.payments.cockfight.risk_policy())
                if path == "/api/admin/china-feed/":
                    return self.send_json(HTTPStatus.OK, self.server.payments.china_feed.admin_view())
                if path == "/api/admin/game-categories/":
                    return self.send_json(HTTPStatus.OK, {"results": self.server.payments.admin_game_categories()})
                if path == "/api/admin/streams/":
                    game_value = (query.get("game_id") or [""])[0]
                    return self.send_json(HTTPStatus.OK, {"results": self.server.payments.streaming.list_sessions(int(game_value) if game_value else None)})
                if path == "/api/admin/streams/health/":
                    return self.send_json(HTTPStatus.OK, self.server.payments.streaming.health())
                if path == "/api/admin/audit/":
                    limit = int((query.get("limit") or ["100"])[0])
                    return self.send_json(HTTPStatus.OK, {"results": self.server.payments.admin_audit(limit)})
                if path == "/api/admin/team/":
                    return self.send_json(HTTPStatus.OK, {"results": self.server.payments.auth.list_admins()})
                if path == "/api/admin/compliance/":
                    status = (query.get("status") or [""])[0]
                    return self.send_json(HTTPStatus.OK, {"results": self.server.payments.compliance.admin_queue(status)})
                if path == "/api/admin/compliance/policy/":
                    return self.send_json(HTTPStatus.OK, self.server.payments.compliance.policy())
                if path == "/api/admin/operations/overview/":
                    return self.send_json(HTTPStatus.OK, self.server.payments.operations.overview())
                if path == "/api/admin/support/tickets/":
                    status = (query.get("status") or [""])[0]
                    return self.send_json(HTTPStatus.OK, self.server.payments.support.list_admin(status))
                if path == "/api/admin/intelligence/overview/":
                    return self.send_json(HTTPStatus.OK, self.server.payments.intelligence.overview())
                if path == "/api/admin/intelligence/alerts/":
                    status = (query.get("status") or [""])[0]
                    return self.send_json(HTTPStatus.OK, self.server.payments.intelligence.list_alerts(status))
                if path == "/api/admin/intelligence/policy/":
                    return self.send_json(HTTPStatus.OK, self.server.payments.intelligence.policy())
                if path == "/api/admin/intelligence/export/":
                    filename = f"roosterrun-financial-intelligence-{datetime.now(timezone.utc).date().isoformat()}.csv"
                    return self.send_private_bytes(self.server.payments.intelligence.export_csv(), "text/csv; charset=utf-8", filename)
                backup_download = re.fullmatch(r"/api/admin/operations/backups/(\d+)/download/", path)
                if backup_download:
                    backup_path = self.server.payments.operations.backup_file(int(backup_download.group(1)))
                    return self.send_private_file(backup_path, "application/gzip", backup_path.name, attachment=True)
                document = re.fullmatch(r"/api/admin/compliance/documents/(\d+)/", path)
                if document:
                    file_path, content_type = self.server.payments.compliance.document(int(document.group(1)))
                    return self.send_private_file(file_path, content_type)
                return self.send_json(HTTPStatus.NOT_FOUND, {"detail": "Admin endpoint not found."})
            except Exception as error:
                return self.handle_api_error(error)
        if path.startswith("/api/payments/"):
            try:
                if path == "/api/payments/health/":
                    return self.send_json(HTTPStatus.OK, {"status": "ok", "preview": self.server.preview_mode})
                if path == "/api/payments/accounts/":
                    return self.send_json(HTTPStatus.OK, {"results": self.server.payments.list_accounts(False)})
                if path == "/api/payments/wallet/":
                    return self.send_json(HTTPStatus.OK, self.server.payments.wallet(self.user_id()))
                if path == "/api/payments/requests/":
                    return self.send_json(HTTPStatus.OK, {"results": self.server.payments.list_requests(self.user_id())})
                if path == "/api/payments/ledger/":
                    return self.send_json(HTTPStatus.OK, {"results": self.server.payments.list_ledger(self.user_id())})
                player_evidence = re.fullmatch(r"/api/payments/requests/(\d+)/(deposit-proof|payout-proof)/", path)
                if player_evidence:
                    file_path, content_type = self.server.payments.payment_evidence(
                        int(player_evidence.group(1)), player_evidence.group(2), self.user_id()
                    )
                    return self.send_private_file(file_path, content_type, file_path.name)
                if path == "/api/payments/admin/accounts/":
                    self.require_admin("payments")
                    return self.send_json(HTTPStatus.OK, {"results": self.server.payments.list_accounts(True)})
                if path == "/api/payments/admin/requests/":
                    self.require_admin("payments")
                    status = (query.get("status") or [""])[0]
                    return self.send_json(HTTPStatus.OK, {"results": self.server.payments.list_requests(None, status)})
                admin_evidence = re.fullmatch(r"/api/payments/admin/requests/(\d+)/(deposit-proof|payout-proof)/", path)
                if admin_evidence:
                    self.require_admin("payments")
                    file_path, content_type = self.server.payments.payment_evidence(
                        int(admin_evidence.group(1)), admin_evidence.group(2)
                    )
                    return self.send_private_file(file_path, content_type, file_path.name)
                return self.send_json(HTTPStatus.NOT_FOUND, {"detail": "Payment endpoint not found."})
            except Exception as error:  # centralized JSON API boundary
                return self.handle_api_error(error)
        self.serve_static(path)

    def do_POST(self) -> None:  # noqa: N802
        parsed_request = urlparse(self.path)
        path = unquote(parsed_request.path)
        request_query = parse_qs(parsed_request.query)
        try:
            if path == "/api/admin/assets/upload/":
                self.require_admin("assets", mutate=True)
                try:
                    length = int(self.headers.get("Content-Length") or "0")
                except ValueError:
                    raise ValueError("Invalid upload length.") from None
                saved = self.server.payments.save_media_upload(
                    self.rfile,
                    length,
                    self.headers.get("Content-Type", ""),
                    self.headers.get("X-Asset-Kind", ""),
                )
                return self.send_json(HTTPStatus.CREATED, saved)
            payload = self.read_json()
            if path == "/api/user/register/":
                result = self.server.payments.auth.register_user(payload, self.client_ip(), self.headers.get("User-Agent", ""))
                if "session_token" in result:
                    body, cookies = self.session_cookies(result)
                    return self.send_json(HTTPStatus.CREATED, body, cookies)
                return self.send_json(HTTPStatus.ACCEPTED, result)
            if path == "/api/user/login/":
                result = self.server.payments.auth.login_user(payload, self.client_ip(), self.headers.get("User-Agent", ""))
                body, cookies = self.session_cookies(result)
                return self.send_json(HTTPStatus.OK, body, cookies)
            if path == "/api/user/logout/":
                token = self.cookie(USER_SESSION_COOKIE)
                if token:
                    self.user_identity(mutate=True)
                    self.server.payments.auth.revoke_session(token, "USER")
                return self.send_json(HTTPStatus.OK, {"authenticated": False}, self.clear_session_cookies())
            if path == "/api/user/forgot-password/request-otp/":
                return self.send_json(HTTPStatus.ACCEPTED, self.server.payments.auth.request_password_reset(payload.get("mobile")))
            if path == "/api/user/forgot-password/reset/":
                return self.send_json(HTTPStatus.OK, self.server.payments.auth.reset_password(payload), self.clear_session_cookies())
            if path == "/api/user/password/change/":
                user_id = self.user_id(mutate=True)
                self.request_context(user_id, "USER")
                result = self.server.payments.auth.change_user_password(user_id, payload)
                return self.send_json(HTTPStatus.OK, result, self.clear_session_cookies())
            if path == "/api/user/compliance/submit/":
                return self.send_json(HTTPStatus.OK, self.server.payments.compliance.submit(self.user_id(mutate=True), payload))
            if path == "/api/user/responsible-play/limits/":
                return self.send_json(HTTPStatus.OK, self.server.payments.compliance.update_limits(self.user_id(mutate=True), payload))
            if path == "/api/user/responsible-play/restrict/":
                return self.send_json(HTTPStatus.OK, self.server.payments.compliance.restrict(self.user_id(mutate=True), payload.get("kind"), int(payload.get("duration_days") or 0)))
            notification_read = re.fullmatch(r"/api/user/notifications/(\d+)/read/", path)
            if notification_read:
                return self.send_json(HTTPStatus.OK, self.server.payments.operations.mark_notification_read(self.user_id(mutate=True), int(notification_read.group(1))))
            if path == "/api/user/notifications/read-all/":
                return self.send_json(HTTPStatus.OK, self.server.payments.operations.mark_all_notifications_read(self.user_id(mutate=True)))
            if path == "/api/user/support/tickets/":
                return self.send_json(HTTPStatus.CREATED, self.server.payments.support.create(self.user_id(mutate=True), payload))
            support_reply = re.fullmatch(r"/api/user/support/tickets/(\d+)/messages/", path)
            if support_reply:
                return self.send_json(HTTPStatus.OK, self.server.payments.support.user_reply(self.user_id(mutate=True), int(support_reply.group(1)), payload.get("message")))
            if path == "/api/admin/auth/login/":
                self.request_context(payload.get("username") or "anonymous", "AUTH")
                result = self.server.payments.auth.login_admin(payload, self.client_ip(), self.headers.get("User-Agent", ""))
                if "session_token" in result:
                    body, cookies = self.session_cookies(result, admin=True)
                    return self.send_json(HTTPStatus.OK, body, cookies)
                return self.send_json(HTTPStatus.ACCEPTED, result)
            if path == "/api/admin/auth/mfa/verify/":
                result = self.server.payments.auth.verify_admin_mfa(payload, self.client_ip(), self.headers.get("User-Agent", ""))
                body, cookies = self.session_cookies(result, admin=True)
                return self.send_json(HTTPStatus.OK, body, cookies)
            if path == "/api/admin/auth/logout/":
                token = self.cookie(ADMIN_SESSION_COOKIE)
                if token:
                    self.require_admin("overview", mutate=True)
                    self.server.payments.auth.revoke_session(token, "ADMIN")
                return self.send_json(HTTPStatus.OK, {"authenticated": False}, self.clear_session_cookies(admin=True))
            if path == "/api/cockfight/bets/quote/":
                return self.send_json(HTTPStatus.CREATED, self.server.payments.cockfight.quote_bet(self.user_id(mutate=True), payload))
            if path == "/api/cockfight/bets/place-bet/":
                return self.send_json(HTTPStatus.CREATED, self.server.payments.cockfight.place_bet(self.user_id(mutate=True), payload))
            if path == "/api/cockfight/broadcast/hooks/srs/publish/":
                hook_secret = (request_query.get("secret") or [""])[0]
                return self.send_json(HTTPStatus.OK, self.server.payments.streaming.authorize_media_publish(payload, hook_secret))
            if path == "/api/cockfight/broadcast/hooks/srs/unpublish/":
                hook_secret = (request_query.get("secret") or [""])[0]
                return self.send_json(HTTPStatus.OK, self.server.payments.streaming.media_unpublish(payload, hook_secret))
            if path == "/api/cockfight/broadcast/hooks/srs/recording/":
                hook_secret = (request_query.get("secret") or [""])[0]
                return self.send_json(HTTPStatus.OK, self.server.payments.streaming.recording_ready(payload, hook_secret))
            if path == "/api/cockfight/broadcast/pair/":
                return self.send_json(HTTPStatus.OK, self.server.payments.streaming.pair_mobile(payload.get("session_id"), payload.get("pairing_code")))
            if path == "/api/internal/monitoring/alerts/":
                expected = os.environ.get("ROOSTERRUN_INTERNAL_ALERT_TOKEN", "")
                supplied = self.bearer_token()
                if not expected or not secrets.compare_digest(expected, supplied):
                    raise PermissionError("Monitoring hook authorization is required.")
                return self.send_json(HTTPStatus.ACCEPTED, self.server.payments.operations.ingest_monitoring_alerts(payload))
            broadcast_ticket = re.fullmatch(r"/api/cockfight/broadcast/sessions/([^/]+)/ticket/", path)
            if broadcast_ticket:
                return self.send_json(HTTPStatus.OK, self.server.payments.streaming.issue_ticket(broadcast_ticket.group(1), self.bearer_token()))
            broadcast_heartbeat = re.fullmatch(r"/api/cockfight/broadcast/sessions/([^/]+)/heartbeat/", path)
            if broadcast_heartbeat:
                return self.send_json(HTTPStatus.OK, self.server.payments.streaming.heartbeat(broadcast_heartbeat.group(1), self.bearer_token(), payload))
            broadcast_stop = re.fullmatch(r"/api/cockfight/broadcast/sessions/([^/]+)/stop/", path)
            if broadcast_stop:
                return self.send_json(HTTPStatus.OK, self.server.payments.streaming.stop_session(broadcast_stop.group(1), "PUBLISHER", self.bearer_token(), str(payload.get("reason") or "")))
            if path.startswith("/api/admin/"):
                permission = self.admin_permission(path)
                if path == "/api/admin/config/" and set(payload).issubset({"brand", "theme"}):
                    permission = "theme"
                admin_identity = self.require_admin(permission, mutate=True)
                if path == "/api/admin/games/":
                    return self.send_json(HTTPStatus.CREATED, self.server.payments.admin_save_game(payload))
                game = re.fullmatch(r"/api/admin/games/(\d+)/", path)
                if game:
                    return self.send_json(HTTPStatus.OK, self.server.payments.admin_save_game(payload, int(game.group(1))))
                if path == "/api/admin/banners/":
                    return self.send_json(HTTPStatus.CREATED, self.server.payments.admin_save_banner(payload))
                banner = re.fullmatch(r"/api/admin/banners/(\d+)/", path)
                if banner:
                    return self.send_json(HTTPStatus.OK, self.server.payments.admin_save_banner(payload, int(banner.group(1))))
                if path == "/api/admin/vip/":
                    return self.send_json(HTTPStatus.CREATED, self.server.payments.admin_save_vip(payload))
                tier = re.fullmatch(r"/api/admin/vip/(\d+)/", path)
                if tier:
                    return self.send_json(HTTPStatus.OK, self.server.payments.admin_save_vip(payload, int(tier.group(1))))
                user = re.fullmatch(r"/api/admin/users/([^/]+)/", path)
                if user:
                    return self.send_json(HTTPStatus.OK, self.server.payments.admin_update_user(user.group(1), payload))
                if path == "/api/admin/config/":
                    return self.send_json(HTTPStatus.OK, self.server.payments.admin_update_config(payload))
                if path == "/api/admin/risk/":
                    return self.send_json(HTTPStatus.OK, self.server.payments.cockfight.update_risk_policy(payload))
                if path == "/api/admin/china-feed/":
                    return self.send_json(HTTPStatus.OK, self.server.payments.china_feed.update_settings(payload))
                if path == "/api/admin/china-feed/poll/":
                    return self.send_json(HTTPStatus.OK, self.server.payments.china_feed.poll_once(force=True))
                if path == "/api/admin/china-feed/recover/":
                    return self.send_json(HTTPStatus.OK, {"recovered": self.server.payments.china_feed.recover()})
                if path == "/api/admin/game-categories/":
                    return self.send_json(HTTPStatus.CREATED, self.server.payments.admin_save_game_category(payload))
                category = re.fullmatch(r"/api/admin/game-categories/(\d+)/", path)
                if category:
                    return self.send_json(HTTPStatus.OK, self.server.payments.admin_save_game_category(payload, int(category.group(1))))
                category_delete = re.fullmatch(r"/api/admin/game-categories/(\d+)/delete/", path)
                if category_delete:
                    self.server.payments.admin_delete_game_category(int(category_delete.group(1)))
                    return self.send_json(HTTPStatus.OK, {"deleted": True})
                game_visibility = re.fullmatch(r"/api/admin/games/(\d+)/visibility/", path)
                if game_visibility:
                    return self.send_json(HTTPStatus.OK, self.server.payments.admin_set_game_visibility(int(game_visibility.group(1)), bool(payload.get("visible"))))
                broadcast_create = re.fullmatch(r"/api/admin/games/(\d+)/broadcast/session/", path)
                if broadcast_create:
                    return self.send_json(HTTPStatus.CREATED, self.server.payments.streaming.create_session(int(broadcast_create.group(1)), payload))
                broadcast_admin_stop = re.fullmatch(r"/api/admin/streams/([^/]+)/stop/", path)
                if broadcast_admin_stop:
                    return self.send_json(HTTPStatus.OK, self.server.payments.streaming.stop_session(broadcast_admin_stop.group(1), "ADMIN", reason=str(payload.get("reason") or "Administrator ended stream")))
                broadcast_credentials = re.fullmatch(r"/api/admin/streams/([^/]+)/credentials/", path)
                if broadcast_credentials:
                    return self.send_json(HTTPStatus.OK, self.server.payments.streaming.rotate_credentials(broadcast_credentials.group(1)))
                transition = re.fullmatch(r"/api/admin/games/(\d+)/transition/", path)
                if transition:
                    result = self.server.payments.cockfight.transition_game(
                        int(transition.group(1)), str(payload.get("status") or ""), "ADMIN", str(payload.get("reason") or "")
                    )
                    return self.send_json(HTTPStatus.OK, self.server.payments.game_to_dict(result))
                odds = re.fullmatch(r"/api/admin/games/(\d+)/odds/", path)
                if odds:
                    return self.send_json(HTTPStatus.OK, self.server.payments.cockfight.publish_odds(int(odds.group(1)), payload))
                result = re.fullmatch(r"/api/admin/games/(\d+)/result/", path)
                if result:
                    saved = self.server.payments.cockfight.declare_result(int(result.group(1)), payload.get("result"), "ADMIN")
                    return self.send_json(HTTPStatus.OK, self.server.payments.game_to_dict(saved))
                settlement = re.fullmatch(r"/api/admin/games/(\d+)/settle/", path)
                if settlement:
                    return self.send_json(HTTPStatus.OK, self.server.payments.cockfight.settle_game(int(settlement.group(1)), "ADMIN"))
                if path == "/api/admin/logo/":
                    return self.send_json(HTTPStatus.OK, self.server.payments.admin_save_logo(payload))
                if path == "/api/admin/social/":
                    return self.send_json(HTTPStatus.OK, {"results": self.server.payments.admin_update_social(payload)})
                if path == "/api/admin/team/":
                    return self.send_json(HTTPStatus.CREATED, self.server.payments.auth.create_admin(payload))
                team_member = re.fullmatch(r"/api/admin/team/(\d+)/", path)
                if team_member:
                    actor_id = int(admin_identity["id"]) if str(admin_identity["id"]).isdigit() else -1
                    return self.send_json(HTTPStatus.OK, self.server.payments.auth.update_admin(int(team_member.group(1)), payload, actor_id))
                if path == "/api/admin/auth/mfa/enroll/":
                    if not str(admin_identity["id"]).isdigit():
                        raise ValueError("Sign in with an administrator account to configure MFA.")
                    return self.send_json(HTTPStatus.OK, self.server.payments.auth.begin_mfa_enrollment(int(admin_identity["id"]), self.server.payments.admin_config().get("brand", {}).get("site_name", "RoosterRun")))
                if path == "/api/admin/auth/mfa/confirm/":
                    if not str(admin_identity["id"]).isdigit():
                        raise ValueError("Sign in with an administrator account to configure MFA.")
                    return self.send_json(HTTPStatus.OK, self.server.payments.auth.confirm_mfa_enrollment(int(admin_identity["id"]), payload.get("code")))
                if path == "/api/admin/compliance/policy/":
                    return self.send_json(HTTPStatus.OK, self.server.payments.compliance.save_policy(payload))
                if path == "/api/admin/operations/reconciliation/run/":
                    actor = str(admin_identity.get("display_name") or admin_identity.get("id") or "ADMIN")
                    return self.send_json(HTTPStatus.CREATED, self.server.payments.operations.run_reconciliation(actor))
                if path == "/api/admin/operations/backups/create/":
                    actor = str(admin_identity.get("display_name") or admin_identity.get("id") or "ADMIN")
                    return self.send_json(HTTPStatus.CREATED, self.server.payments.operations.create_backup(actor))
                incident = re.fullmatch(r"/api/admin/operations/incidents/(\d+)/", path)
                if incident:
                    actor = str(admin_identity.get("display_name") or admin_identity.get("id") or "ADMIN")
                    return self.send_json(HTTPStatus.OK, self.server.payments.operations.update_incident(int(incident.group(1)), payload.get("status"), payload.get("note"), actor))
                if path == "/api/admin/intelligence/scan/":
                    actor = str(admin_identity.get("display_name") or admin_identity.get("id") or "ADMIN")
                    return self.send_json(HTTPStatus.CREATED, self.server.payments.intelligence.scan(actor))
                if path == "/api/admin/intelligence/policy/":
                    return self.send_json(HTTPStatus.OK, self.server.payments.intelligence.save_policy(payload))
                intelligence_alert = re.fullmatch(r"/api/admin/intelligence/alerts/(\d+)/", path)
                if intelligence_alert:
                    actor = str(admin_identity.get("display_name") or admin_identity.get("id") or "ADMIN")
                    return self.send_json(HTTPStatus.OK, self.server.payments.intelligence.update_alert(int(intelligence_alert.group(1)), payload, actor))
                support_ticket = re.fullmatch(r"/api/admin/support/tickets/(\d+)/", path)
                if support_ticket:
                    actor = str(admin_identity.get("display_name") or admin_identity.get("id") or "ADMIN")
                    return self.send_json(HTTPStatus.OK, self.server.payments.support.admin_update(int(support_ticket.group(1)), payload, actor))
                support_message = re.fullmatch(r"/api/admin/support/tickets/(\d+)/messages/", path)
                if support_message:
                    actor = str(admin_identity.get("display_name") or admin_identity.get("id") or "ADMIN")
                    return self.send_json(HTTPStatus.OK, self.server.payments.support.admin_reply(int(support_message.group(1)), payload.get("message"), actor, bool(payload.get("internal"))))
                compliance_decision = re.fullmatch(r"/api/admin/compliance/users/([^/]+)/decision/", path)
                if compliance_decision:
                    return self.send_json(HTTPStatus.OK, self.server.payments.compliance.decide(
                        compliance_decision.group(1), payload.get("decision"), payload.get("note"), str(admin_identity.get("display_name") or admin_identity.get("id") or "ADMIN")
                    ))
                return self.send_json(HTTPStatus.NOT_FOUND, {"detail": "Admin endpoint not found."})
            if not path.startswith("/api/payments/"):
                return self.send_json(HTTPStatus.NOT_FOUND, {"detail": "Endpoint not found."})
            if path == "/api/payments/deposits/":
                result = self.server.payments.create_deposit(self.user_id(mutate=True), payload)
                return self.send_json(HTTPStatus.CREATED, result)
            if path == "/api/payments/withdrawals/":
                result = self.server.payments.create_withdrawal(self.user_id(mutate=True), payload)
                return self.send_json(HTTPStatus.CREATED, result)
            if path == "/api/payments/admin/accounts/":
                self.require_admin("payments", mutate=True)
                return self.send_json(HTTPStatus.CREATED, self.server.payments.create_account(payload))
            account_toggle = re.fullmatch(r"/api/payments/admin/accounts/(\d+)/toggle/", path)
            if account_toggle:
                self.require_admin("payments", mutate=True)
                return self.send_json(HTTPStatus.OK, self.server.payments.toggle_account(int(account_toggle.group(1))))
            decision = re.fullmatch(r"/api/payments/admin/requests/(\d+)/decision/", path)
            if decision:
                self.require_admin("payments", mutate=True)
                return self.send_json(HTTPStatus.OK, self.server.payments.decide_request(int(decision.group(1)), payload))
            return self.send_json(HTTPStatus.NOT_FOUND, {"detail": "Payment endpoint not found."})
        except Exception as error:  # centralized JSON API boundary
            return self.handle_api_error(error)

    def do_HEAD(self) -> None:  # noqa: N802
        self.serve_static(urlparse(self.path).path, head_only=True)

    def serve_static(self, request_path: str, head_only: bool = False) -> None:
        request_path = unquote(request_path)
        if request_path == "/":
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", "/play/")
            self.end_headers()
            return
        if request_path.startswith("/play/"):
            relative = request_path.removeprefix("/play/") or "index.html"
            base = WEB_ROOT / "play"
        elif request_path.startswith("/admin/"):
            relative = request_path.removeprefix("/admin/") or "index.html"
            base = WEB_ROOT / "admin"
        elif request_path.startswith("/broadcast/"):
            relative = request_path.removeprefix("/broadcast/") or "index.html"
            base = WEB_ROOT / "broadcast"
        elif request_path.startswith("/static/"):
            relative = request_path.removeprefix("/static/")
            base = WEB_ROOT / "static"
        elif request_path.startswith("/uploads/"):
            relative = request_path.removeprefix("/uploads/")
            base = self.server.payments.upload_dir
        else:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        target = (base / relative).resolve()
        if base.resolve() not in target.parents or not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        size = target.stat().st_size
        start, end = 0, size - 1
        range_header = self.headers.get("Range", "")
        if range_header:
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header.strip())
            if not match:
                self.send_error(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                return
            if match.group(1):
                start = int(match.group(1))
                end = min(int(match.group(2)), size - 1) if match.group(2) else size - 1
            elif match.group(2):
                suffix = min(int(match.group(2)), size)
                start = size - suffix
            if start < 0 or start >= size or end < start:
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
        response_size = end - start + 1
        self.send_response(HTTPStatus.PARTIAL_CONTENT if range_header else HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(response_size))
        self.send_header("Accept-Ranges", "bytes")
        if range_header:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Permissions-Policy", "camera=(self), microphone=(self)" if request_path.startswith("/broadcast/") else "camera=(), microphone=(), geolocation=()")
        if not self.server.preview_mode and self.server.secure_cookies:
            self.send_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; "
            "script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; "
            "media-src 'self' blob: https:; connect-src 'self' ws: wss: https:; "
            "frame-src https://www.youtube.com https://www.youtube-nocookie.com "
            + " ".join(self.server.payments.china_feed.frame_origins)
            + "; form-action 'self'",
        )
        self.send_header("Cache-Control", "no-store" if request_path.startswith("/uploads/") else "no-cache")
        self.end_headers()
        if not head_only:
            with target.open("rb") as handle:
                handle.seek(start)
                remaining = response_size
                while remaining and (chunk := handle.read(min(64 * 1024, remaining))):
                    self.wfile.write(chunk)
                    remaining -= len(chunk)


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve RoosterRun with the manual-payments API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--preview", action="store_true", help="Enable loopback-only preview admin access")
    args = parser.parse_args()
    load_secret_files()
    validate_runtime_secrets(args.preview)
    payments = PaymentService(args.data_dir, args.preview)
    server = RoosterRunServer((args.host, args.port), RequestHandler, payments, args.preview)
    payments.cockfight.start_scheduler()
    payments.china_feed.start_worker()
    payments.streaming.start_monitor()
    payments.delivery.start_worker()
    mode = "preview" if args.preview else "production"
    print(f"RoosterRun {mode}: http://{args.host}:{args.port}/play/", flush=True)
    print(f"Payment data: {payments.data_dir}", flush=True)

    stopping = threading.Event()

    def request_shutdown(signum=None, frame=None) -> None:
        del signum, frame
        if stopping.is_set():
            return
        stopping.set()
        threading.Thread(target=server.shutdown, name="roosterrun-shutdown", daemon=True).start()

    for signal_name in ("SIGINT", "SIGTERM"):
        if hasattr(signal, signal_name):
            signal.signal(getattr(signal, signal_name), request_shutdown)
    try:
        server.serve_forever()
    finally:
        payments.cockfight.stop_scheduler()
        payments.china_feed.stop_worker()
        payments.streaming.stop_monitor()
        payments.delivery.stop_worker()
        payments.database.close()
        server.server_close()


if __name__ == "__main__":
    main()
