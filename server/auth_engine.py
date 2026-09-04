"""Durable authentication and administrator authorization for RoosterRun.

The engine deliberately uses opaque, server-side sessions. Browser cookies hold
only random session material; the database stores hashes. Passwords use salted
PBKDF2-HMAC-SHA256 and OTP/MFA challenges are short-lived, attempt-limited, and
single-use. The module has no dependency outside the Python standard library so
the same security contract is available in the local preview and on the droplet.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import struct
import time
from datetime import datetime, timedelta, timezone
from urllib import request as urlrequest
from urllib.error import URLError
from urllib.parse import quote


UTC = timezone.utc
PASSWORD_ITERATIONS = 600_000
SESSION_IDLE = {"USER": timedelta(hours=12), "ADMIN": timedelta(hours=4)}
SESSION_ABSOLUTE = {"USER": timedelta(days=30), "ADMIN": timedelta(hours=12)}
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{3,30}$")
ADMIN_USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{3,40}$")


class AuthenticationError(Exception):
    """The caller has no valid authenticated session or credentials."""


class RateLimitError(Exception):
    """The caller has exceeded an authentication safety limit."""


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def parse_time(value: object) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=UTC)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_mobile(value: object) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if not re.fullmatch(r"[6-9][0-9]{9}", digits):
        raise ValueError("Enter a valid Indian mobile number.")
    return f"+91{digits}"


def validate_password(password: object) -> str:
    value = str(password or "")
    if len(value) < 10 or len(value) > 128:
        raise ValueError("Password must contain 10–128 characters.")
    if not re.search(r"[A-Za-z]", value) or not re.search(r"[0-9]", value):
        raise ValueError("Password must contain at least one letter and one number.")
    return value


def hash_password(password: str, salt: bytes | None = None, iterations: int = PASSWORD_ITERATIONS) -> tuple[str, str, int]:
    chosen_salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), chosen_salt, iterations, dklen=32)
    return (
        base64.urlsafe_b64encode(digest).decode("ascii"),
        base64.urlsafe_b64encode(chosen_salt).decode("ascii"),
        iterations,
    )


def verify_password(password: str, encoded_digest: str, encoded_salt: str, iterations: int) -> bool:
    try:
        salt = base64.urlsafe_b64decode(encoded_salt.encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        return False
    digest, _, _ = hash_password(password, salt, int(iterations or PASSWORD_ITERATIONS))
    return hmac.compare_digest(digest, encoded_digest or "")


def generate_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def totp_code(secret: str, at: int | None = None) -> str:
    padded = secret.upper() + "=" * ((8 - len(secret) % 8) % 8)
    key = base64.b32decode(padded, casefold=True)
    counter = int((at if at is not None else time.time()) // 30)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = (struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF) % 1_000_000
    return f"{value:06d}"


def verify_totp(secret: str, code: object) -> bool:
    candidate = re.sub(r"\s", "", str(code or ""))
    if not re.fullmatch(r"[0-9]{6}", candidate):
        return False
    now = int(time.time())
    return any(hmac.compare_digest(totp_code(secret, now + offset * 30), candidate) for offset in (-1, 0, 1))


class AuthenticationEngine:
    def __init__(self, platform, preview_mode: bool = False):
        self.platform = platform
        self.preview_mode = preview_mode
        self.otp_test_mode = preview_mode or os.environ.get("ROOSTERRUN_OTP_TEST_MODE", "").strip().lower() in {"1", "true", "yes"}
        self.sms_webhook = os.environ.get("ROOSTERRUN_SMS_WEBHOOK_URL", "").strip()
        self.sms_token = os.environ.get("ROOSTERRUN_SMS_WEBHOOK_TOKEN", "").strip()
        self._dummy_hash, self._dummy_salt, self._dummy_iterations = hash_password("invalid-password-constant")
        self._initialize()

    def connect(self) -> sqlite3.Connection:
        return self.platform.connect()

    def _initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS user_accounts (
                    user_id TEXT PRIMARY KEY REFERENCES user_wallets(user_id),
                    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    mobile TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    password_salt TEXT NOT NULL,
                    password_iterations INTEGER NOT NULL,
                    mobile_verified INTEGER NOT NULL DEFAULT 0 CHECK(mobile_verified IN (0,1)),
                    failed_login_count INTEGER NOT NULL DEFAULT 0,
                    locked_until TEXT NOT NULL DEFAULT '',
                    last_login_at TEXT NOT NULL DEFAULT '',
                    password_changed_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS admin_accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    display_name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    password_salt TEXT NOT NULL,
                    password_iterations INTEGER NOT NULL,
                    role_id INTEGER NOT NULL REFERENCES admin_roles(id),
                    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
                    mfa_secret TEXT NOT NULL DEFAULT '',
                    pending_mfa_secret TEXT NOT NULL DEFAULT '',
                    mfa_enabled INTEGER NOT NULL DEFAULT 0 CHECK(mfa_enabled IN (0,1)),
                    failed_login_count INTEGER NOT NULL DEFAULT 0,
                    locked_until TEXT NOT NULL DEFAULT '',
                    last_login_at TEXT NOT NULL DEFAULT '',
                    password_changed_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS auth_challenges (
                    id TEXT PRIMARY KEY,
                    purpose TEXT NOT NULL CHECK(purpose IN ('REGISTER','PASSWORD_RESET','ADMIN_MFA')),
                    subject TEXT NOT NULL DEFAULT '',
                    mobile TEXT NOT NULL DEFAULT '',
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    code_hash TEXT NOT NULL,
                    code_salt TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 5,
                    expires_at TEXT NOT NULL,
                    consumed_at TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    last_sent_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS auth_sessions (
                    id TEXT PRIMARY KEY,
                    token_hash TEXT NOT NULL UNIQUE,
                    session_type TEXT NOT NULL CHECK(session_type IN ('USER','ADMIN')),
                    subject_id TEXT NOT NULL,
                    csrf_hash TEXT NOT NULL,
                    ip_hash TEXT NOT NULL DEFAULT '',
                    user_agent_hash TEXT NOT NULL DEFAULT '',
                    expires_at TEXT NOT NULL,
                    absolute_expires_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    revoked_at TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS admin_mfa_recovery_codes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id INTEGER NOT NULL REFERENCES admin_accounts(id),
                    code_hash TEXT NOT NULL UNIQUE,
                    used_at TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_auth_sessions_hash_active
                ON auth_sessions(token_hash, session_type, revoked_at);
                CREATE INDEX IF NOT EXISTS idx_auth_sessions_subject
                ON auth_sessions(session_type, subject_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_auth_challenges_expiry
                ON auth_challenges(purpose, expires_at);
                CREATE INDEX IF NOT EXISTS idx_user_accounts_mobile
                ON user_accounts(mobile);
                CREATE INDEX IF NOT EXISTS idx_admin_accounts_role
                ON admin_accounts(role_id, active);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_user_accounts_username_ci
                ON user_accounts(LOWER(username));
                CREATE UNIQUE INDEX IF NOT EXISTS idx_admin_accounts_username_ci
                ON admin_accounts(LOWER(username));
                """
            )
            connection.execute("DELETE FROM auth_challenges WHERE expires_at < ?", (utc_now(),))
            connection.execute("DELETE FROM auth_sessions WHERE absolute_expires_at < ?", (utc_now(),))
            self._bootstrap_admin(connection)
            connection.execute("PRAGMA optimize")

    def _bootstrap_admin(self, connection: sqlite3.Connection) -> None:
        password = os.environ.get("ROOSTERRUN_BOOTSTRAP_ADMIN_PASSWORD", "")
        if not password:
            return
        username = os.environ.get("ROOSTERRUN_BOOTSTRAP_ADMIN_USERNAME", "owner").strip()
        display_name = os.environ.get("ROOSTERRUN_BOOTSTRAP_ADMIN_NAME", "Platform Owner").strip()
        if not ADMIN_USERNAME_PATTERN.fullmatch(username):
            raise RuntimeError("ROOSTERRUN_BOOTSTRAP_ADMIN_USERNAME is invalid.")
        validated = validate_password(password)
        if connection.execute("SELECT 1 FROM admin_accounts LIMIT 1").fetchone():
            return
        role = connection.execute("SELECT id FROM admin_roles WHERE name='Super Admin'").fetchone()
        if not role:
            raise RuntimeError("The Super Admin role is missing.")
        digest, salt, iterations = hash_password(validated)
        now = utc_now()
        connection.execute(
            """INSERT INTO admin_accounts
            (username,display_name,password_hash,password_salt,password_iterations,role_id,active,password_changed_at,created_at,updated_at)
            VALUES(?,?,?,?,?,?,1,?,?,?)""",
            (username, display_name[:80], digest, salt, iterations, role["id"], now, now, now),
        )

    @staticmethod
    def _public_user(row: sqlite3.Row, wallet: sqlite3.Row | None = None, held_paise: int = 0) -> dict:
        balance_paise = int(wallet["balance_paise"] if wallet else 0)
        return {
            "id": row["user_id"],
            "username": row["username"],
            "mobile": row["mobile"],
            "mobile_verified": bool(row["mobile_verified"]),
            "wallet_balance": round(balance_paise / 100, 2),
            "available_balance": round(max(balance_paise - int(held_paise), 0) / 100, 2),
            "exposure": round(int(held_paise) / 100, 2),
            "tier": wallet["vip_tier"] if wallet else "Standard",
            "status": wallet["account_status"] if wallet else "ACTIVE",
        }

    @staticmethod
    def _admin_identity(row: sqlite3.Row) -> dict:
        permissions = json.loads(row["permissions"] or "[]")
        return {
            "id": int(row["id"]),
            "username": row["username"],
            "display_name": row["display_name"],
            "role": row["role_name"],
            "permissions": permissions,
            "mfa_enabled": bool(row["mfa_enabled"]),
        }

    def _send_otp(self, mobile: str, code: str, purpose: str) -> None:
        if self.otp_test_mode:
            return
        try:
            self.platform.delivery.send_otp(mobile, code, purpose)
        except Exception as error:
            raise RuntimeError("The verification message could not be sent.") from error

    def _create_otp_challenge(self, purpose: str, mobile: str, subject: str, payload: dict, deliver: bool = True) -> dict:
        now = datetime.now(UTC)
        with self.connect() as connection:
            recent = connection.execute(
                "SELECT created_at FROM auth_challenges WHERE mobile=? AND purpose=? ORDER BY created_at DESC LIMIT 1",
                (mobile, purpose),
            ).fetchone()
            if recent and now - parse_time(recent["created_at"]) < timedelta(seconds=45):
                raise RateLimitError("Please wait before requesting another verification code.")
            hour_ago = (now - timedelta(hours=1)).isoformat(timespec="seconds")
            count = connection.execute(
                "SELECT COUNT(*) AS total FROM auth_challenges WHERE mobile=? AND purpose=? AND created_at>=?",
                (mobile, purpose, hour_ago),
            ).fetchone()
            if int(count["total"] or 0) >= 5:
                raise RateLimitError("Too many verification codes were requested. Try again later.")
            challenge_id = secrets.token_urlsafe(24)
            code = f"{secrets.randbelow(1_000_000):06d}"
            salt = secrets.token_hex(16)
            digest = token_hash(f"{salt}:{code}")
            expires = (now + timedelta(minutes=5)).isoformat(timespec="seconds")
            connection.execute(
                """INSERT INTO auth_challenges
                (id,purpose,subject,mobile,payload_json,code_hash,code_salt,expires_at,created_at,last_sent_at)
                VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (challenge_id, purpose, subject, mobile, json.dumps(payload), digest, salt, expires, now.isoformat(timespec="seconds"), now.isoformat(timespec="seconds")),
            )
        if deliver:
            self._send_otp(mobile, code, purpose)
        result = {"otp_required": True, "challenge_id": challenge_id, "expires_in": 300}
        if self.otp_test_mode:
            result["preview_otp"] = code
        return result

    def _consume_challenge(self, challenge_id: object, purpose: str, code: object) -> dict:
        challenge = str(challenge_id or "").strip()
        supplied = re.sub(r"\s", "", str(code or ""))
        if not challenge or not supplied:
            raise AuthenticationError("The verification challenge and code are required.")
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM auth_challenges WHERE id=? AND purpose=?", (challenge, purpose)).fetchone()
            if not row or row["consumed_at"]:
                raise AuthenticationError("The verification challenge is invalid or already used.")
            if parse_time(row["expires_at"]) <= datetime.now(UTC):
                raise AuthenticationError("The verification code has expired.")
            if int(row["attempts"]) >= int(row["max_attempts"]):
                raise RateLimitError("Too many invalid verification attempts.")
            valid = hmac.compare_digest(token_hash(f"{row['code_salt']}:{supplied}"), row["code_hash"])
            if not valid:
                connection.execute("UPDATE auth_challenges SET attempts=attempts+1 WHERE id=?", (challenge,))
                connection.commit()
                raise AuthenticationError("The verification code is incorrect.")
            connection.execute("UPDATE auth_challenges SET consumed_at=? WHERE id=?", (utc_now(), challenge))
            return {**dict(row), "payload": json.loads(row["payload_json"] or "{}")}

    def register_user(self, payload: dict, ip_address: str = "", user_agent: str = "") -> dict:
        if payload.get("otp"):
            challenge = self._consume_challenge(payload.get("challenge_id"), "REGISTER", payload.get("otp"))
            registration = challenge["payload"]
            username = registration["username"]
            mobile = registration["mobile"]
            digest = registration["password_hash"]
            salt = registration["password_salt"]
            iterations = int(registration["password_iterations"])
            now = utc_now()
            user_id = f"usr_{secrets.token_hex(8)}"
            with self.connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                if connection.execute("SELECT 1 FROM user_accounts WHERE username=? COLLATE NOCASE OR mobile=?", (username, mobile)).fetchone():
                    raise ValueError("That username or mobile number is already registered.")
                connection.execute(
                    """INSERT INTO user_wallets(user_id,balance_paise,display_name,mobile,account_status,vip_tier,created_at,updated_at)
                    VALUES(?,?,?,?,'ACTIVE','Standard',?,?)""",
                    (user_id, int(self.platform.initial_wallet_balance_paise), username, mobile, now, now),
                )
                connection.execute(
                    """INSERT INTO user_accounts
                    (user_id,username,mobile,password_hash,password_salt,password_iterations,mobile_verified,password_changed_at,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,1,?,?,?)""",
                    (user_id, username, mobile, digest, salt, iterations, now, now, now),
                )
                if self.platform.initial_wallet_balance_paise:
                    connection.execute(
                        """INSERT INTO account_ledger
                        (user_id,reference,entry_type,amount_paise,balance_after_paise,metadata_json,created_at)
                        VALUES(?,?,'ADJUSTMENT',?,?,?,?)""",
                        (
                            user_id,
                            f"DEMO-GRANT-{user_id}",
                            int(self.platform.initial_wallet_balance_paise),
                            int(self.platform.initial_wallet_balance_paise),
                            json.dumps({"reason": "Approval demo starting credits", "non_cash": True}),
                            now,
                        ),
                    )
                row = connection.execute("SELECT * FROM user_accounts WHERE user_id=?", (user_id,)).fetchone()
                wallet = connection.execute("SELECT * FROM user_wallets WHERE user_id=?", (user_id,)).fetchone()
            session = self._create_session("USER", user_id, ip_address, user_agent)
            return {"user": self._public_user(row, wallet), **session}

        username = str(payload.get("username") or "").strip()
        if not USERNAME_PATTERN.fullmatch(username):
            raise ValueError("Username must use 3–30 letters, numbers, dots, dashes, or underscores.")
        mobile = normalize_mobile(payload.get("mobile"))
        password = validate_password(payload.get("password"))
        if payload.get("confirmPassword") is not None and str(payload.get("confirmPassword")) != password:
            raise ValueError("The passwords do not match.")
        with self.connect() as connection:
            if connection.execute("SELECT 1 FROM user_accounts WHERE username=? COLLATE NOCASE", (username,)).fetchone():
                raise ValueError("That username is already registered.")
            if connection.execute("SELECT 1 FROM user_accounts WHERE mobile=?", (mobile,)).fetchone():
                raise ValueError("That mobile number is already registered.")
        digest, salt, iterations = hash_password(password)
        return self._create_otp_challenge(
            "REGISTER",
            mobile,
            username,
            {"username": username, "mobile": mobile, "password_hash": digest, "password_salt": salt, "password_iterations": iterations},
        )

    def login_user(self, payload: dict, ip_address: str = "", user_agent: str = "") -> dict:
        identifier = str(payload.get("identifier") or "").strip()
        password = str(payload.get("password") or "")
        if not identifier or not password:
            raise AuthenticationError("Enter your mobile number or username and password.")
        normalized_mobile = ""
        try:
            normalized_mobile = normalize_mobile(identifier)
        except ValueError:
            pass
        with self.connect() as connection:
            row = connection.execute(
                "SELECT a.*,w.balance_paise,w.vip_tier,w.account_status FROM user_accounts a JOIN user_wallets w ON w.user_id=a.user_id WHERE a.username=? COLLATE NOCASE OR a.mobile=?",
                (identifier, normalized_mobile),
            ).fetchone()
            digest = row["password_hash"] if row else self._dummy_hash
            salt = row["password_salt"] if row else self._dummy_salt
            iterations = row["password_iterations"] if row else self._dummy_iterations
            valid = verify_password(password, digest, salt, iterations)
            if not row or not valid:
                if row:
                    failures = int(row["failed_login_count"]) + 1
                    lock_until = (datetime.now(UTC) + timedelta(minutes=15)).isoformat(timespec="seconds") if failures >= 5 else row["locked_until"]
                    connection.execute("UPDATE user_accounts SET failed_login_count=?,locked_until=?,updated_at=? WHERE user_id=?", (failures, lock_until, utc_now(), row["user_id"]))
                connection.commit()
                raise AuthenticationError("The username/mobile or password is incorrect.")
            if row["locked_until"] and parse_time(row["locked_until"]) > datetime.now(UTC):
                raise RateLimitError("This account is temporarily locked. Try again later.")
            if row["account_status"] != "ACTIVE":
                raise PermissionError("This player account is not active.")
            connection.execute("UPDATE user_accounts SET failed_login_count=0,locked_until='',last_login_at=?,updated_at=? WHERE user_id=?", (utc_now(), utc_now(), row["user_id"]))
            public = self._public_user(row, row)
        return {"user": public, **self._create_session("USER", row["user_id"], ip_address, user_agent)}

    def request_password_reset(self, mobile_value: object) -> dict:
        mobile = normalize_mobile(mobile_value)
        with self.connect() as connection:
            account = connection.execute("SELECT user_id FROM user_accounts WHERE mobile=?", (mobile,)).fetchone()
        if not account:
            result = self._create_otp_challenge("PASSWORD_RESET", mobile, "", {}, deliver=False)
        else:
            result = self._create_otp_challenge("PASSWORD_RESET", mobile, account["user_id"], {})
        result["accepted"] = True
        result["message"] = "If the mobile number is registered, a verification code will be sent."
        return result

    def reset_password(self, payload: dict) -> dict:
        challenge = self._consume_challenge(payload.get("challenge_id"), "PASSWORD_RESET", payload.get("otp"))
        password = validate_password(payload.get("password") or payload.get("new_password"))
        if payload.get("confirmPassword") is not None and str(payload.get("confirmPassword")) != password:
            raise ValueError("The passwords do not match.")
        digest, salt, iterations = hash_password(password)
        now = utc_now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            updated = connection.execute(
                "UPDATE user_accounts SET password_hash=?,password_salt=?,password_iterations=?,password_changed_at=?,failed_login_count=0,locked_until='',updated_at=? WHERE user_id=?",
                (digest, salt, iterations, now, now, challenge["subject"]),
            )
            if updated.rowcount != 1:
                raise AuthenticationError("The password reset request is no longer valid.")
            connection.execute("UPDATE auth_sessions SET revoked_at=? WHERE session_type='USER' AND subject_id=? AND revoked_at=''", (now, challenge["subject"]))
        return {"password_reset": True}

    def change_user_password(self, user_id: str, payload: dict) -> dict:
        current_password = str(payload.get("current_password") or "")
        new_password = validate_password(payload.get("new_password"))
        if str(payload.get("confirm_password") or "") != new_password:
            raise ValueError("The new passwords do not match.")
        if not current_password:
            raise AuthenticationError("Enter your current password.")
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM user_accounts WHERE user_id=?", (user_id,)).fetchone()
            if not row or not verify_password(current_password, row["password_hash"], row["password_salt"], int(row["password_iterations"])):
                raise AuthenticationError("The current password is incorrect.")
            if verify_password(new_password, row["password_hash"], row["password_salt"], int(row["password_iterations"])):
                raise ValueError("Choose a new password that is different from the current password.")
            digest, salt, iterations = hash_password(new_password)
            now = utc_now()
            connection.execute(
                """UPDATE user_accounts SET password_hash=?,password_salt=?,password_iterations=?,
                password_changed_at=?,failed_login_count=0,locked_until='',updated_at=? WHERE user_id=?""",
                (digest, salt, iterations, now, now, user_id),
            )
            connection.execute(
                "UPDATE auth_sessions SET revoked_at=? WHERE session_type='USER' AND subject_id=? AND revoked_at=''",
                (now, user_id),
            )
            self.platform._audit(connection, "Security", "Player password changed", user_id, "All player sessions revoked")
        return {"password_changed": True, "reauthentication_required": True}

    def _create_session(self, session_type: str, subject_id: object, ip_address: str, user_agent: str) -> dict:
        now = datetime.now(UTC)
        raw_token = secrets.token_urlsafe(48)
        csrf = secrets.token_urlsafe(32)
        session_id = secrets.token_urlsafe(18)
        expires = now + SESSION_IDLE[session_type]
        absolute = now + SESSION_ABSOLUTE[session_type]
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO auth_sessions
                (id,token_hash,session_type,subject_id,csrf_hash,ip_hash,user_agent_hash,expires_at,absolute_expires_at,last_seen_at,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    session_id,
                    token_hash(raw_token),
                    session_type,
                    str(subject_id),
                    token_hash(csrf),
                    token_hash(ip_address) if ip_address else "",
                    token_hash(user_agent[:500]) if user_agent else "",
                    expires.isoformat(timespec="seconds"),
                    absolute.isoformat(timespec="seconds"),
                    now.isoformat(timespec="seconds"),
                    now.isoformat(timespec="seconds"),
                ),
            )
        return {"session_token": raw_token, "csrf_token": csrf, "expires_at": expires.isoformat(timespec="seconds")}

    def _session(self, raw_token: object, session_type: str, csrf: object = "", mutate: bool = False) -> sqlite3.Row:
        token = str(raw_token or "").strip()
        if not token:
            raise AuthenticationError("Sign in is required.")
        now = datetime.now(UTC)
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM auth_sessions WHERE token_hash=? AND session_type=? AND revoked_at=''",
                (token_hash(token), session_type),
            ).fetchone()
            if not row or parse_time(row["expires_at"]) <= now or parse_time(row["absolute_expires_at"]) <= now:
                if row:
                    connection.execute("UPDATE auth_sessions SET revoked_at=? WHERE id=?", (utc_now(), row["id"]))
                raise AuthenticationError("Your session has expired. Sign in again.")
            if mutate and not hmac.compare_digest(token_hash(str(csrf or "")), row["csrf_hash"]):
                raise PermissionError("The security token is missing or invalid. Refresh the page and try again.")
            absolute = parse_time(row["absolute_expires_at"])
            refreshed = min(now + SESSION_IDLE[session_type], absolute)
            if now - parse_time(row["last_seen_at"]) >= timedelta(minutes=2):
                connection.execute("UPDATE auth_sessions SET last_seen_at=?,expires_at=? WHERE id=?", (now.isoformat(timespec="seconds"), refreshed.isoformat(timespec="seconds"), row["id"]))
            return row

    def authenticate_user(self, raw_token: object, csrf: object = "", mutate: bool = False) -> dict:
        session = self._session(raw_token, "USER", csrf, mutate)
        with self.connect() as connection:
            row = connection.execute(
                "SELECT a.*,w.balance_paise,w.vip_tier,w.account_status FROM user_accounts a JOIN user_wallets w ON w.user_id=a.user_id WHERE a.user_id=?",
                (session["subject_id"],),
            ).fetchone()
            held = connection.execute(
                "SELECT COALESCE(SUM(amount_paise),0) AS amount FROM wallet_holds WHERE user_id=? AND status='ACTIVE'", (session["subject_id"],)
            ).fetchone()["amount"] if row else 0
        if not row:
            raise AuthenticationError("The player account no longer exists.")
        if row["account_status"] != "ACTIVE":
            raise PermissionError("This player account is not active.")
        return self._public_user(row, row, int(held or 0))

    def login_admin(self, payload: dict, ip_address: str = "", user_agent: str = "") -> dict:
        username = str(payload.get("username") or "").strip()
        password = str(payload.get("password") or "")
        with self.connect() as connection:
            row = connection.execute(
                """SELECT a.*,r.name AS role_name,r.permissions FROM admin_accounts a
                JOIN admin_roles r ON r.id=a.role_id WHERE a.username=? COLLATE NOCASE""",
                (username,),
            ).fetchone()
            digest = row["password_hash"] if row else self._dummy_hash
            salt = row["password_salt"] if row else self._dummy_salt
            iterations = row["password_iterations"] if row else self._dummy_iterations
            valid = verify_password(password, digest, salt, iterations)
            if not row or not valid:
                if row:
                    failures = int(row["failed_login_count"]) + 1
                    lock_until = (datetime.now(UTC) + timedelta(minutes=30)).isoformat(timespec="seconds") if failures >= 5 else row["locked_until"]
                    connection.execute("UPDATE admin_accounts SET failed_login_count=?,locked_until=?,updated_at=? WHERE id=?", (failures, lock_until, utc_now(), row["id"]))
                self.platform._audit(connection, "Security", "Administrator login failed", username or "anonymous", "Invalid credentials")
                connection.commit()
                raise AuthenticationError("The administrator username or password is incorrect.")
            if row["locked_until"] and parse_time(row["locked_until"]) > datetime.now(UTC):
                self.platform._audit(connection, "Security", "Administrator login blocked", row["username"], "Temporary lock active")
                connection.commit()
                raise RateLimitError("This administrator account is temporarily locked.")
            if not row["active"]:
                self.platform._audit(connection, "Security", "Administrator login blocked", row["username"], "Account disabled")
                connection.commit()
                raise PermissionError("This administrator account is disabled.")
            connection.execute("UPDATE admin_accounts SET failed_login_count=0,locked_until='',updated_at=? WHERE id=?", (utc_now(), row["id"]))
            self.platform._audit(connection, "Security", "Administrator password accepted", row["username"], "MFA required" if row["mfa_enabled"] else "Session issued")
            identity = self._admin_identity(row)
        if row["mfa_enabled"]:
            challenge = self._create_admin_mfa_challenge(row["id"])
            return {"mfa_required": True, "challenge_id": challenge, "admin": identity}
        session = self._create_session("ADMIN", row["id"], ip_address, user_agent)
        with self.connect() as connection:
            connection.execute("UPDATE admin_accounts SET last_login_at=?,updated_at=? WHERE id=?", (utc_now(), utc_now(), row["id"]))
        return {"admin": identity, **session}

    def _create_admin_mfa_challenge(self, admin_id: int) -> str:
        challenge = secrets.token_urlsafe(24)
        code_salt = secrets.token_hex(16)
        now = datetime.now(UTC)
        with self.connect() as connection:
            connection.execute(
                """INSERT INTO auth_challenges
                (id,purpose,subject,payload_json,code_hash,code_salt,expires_at,created_at,last_sent_at)
                VALUES(?,'ADMIN_MFA',?,'{}',?,?,?, ?,?)""",
                (challenge, str(admin_id), token_hash(f"{code_salt}:mfa"), code_salt, (now + timedelta(minutes=5)).isoformat(timespec="seconds"), now.isoformat(timespec="seconds"), now.isoformat(timespec="seconds")),
            )
        return challenge

    def verify_admin_mfa(self, payload: dict, ip_address: str = "", user_agent: str = "") -> dict:
        challenge_id = str(payload.get("challenge_id") or "")
        code = re.sub(r"[^A-Za-z0-9]", "", str(payload.get("code") or payload.get("otp") or "")).upper()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            challenge = connection.execute("SELECT * FROM auth_challenges WHERE id=? AND purpose='ADMIN_MFA'", (challenge_id,)).fetchone()
            if not challenge or challenge["consumed_at"] or parse_time(challenge["expires_at"]) <= datetime.now(UTC):
                raise AuthenticationError("The administrator verification challenge is invalid or expired.")
            if int(challenge["attempts"]) >= int(challenge["max_attempts"]):
                raise RateLimitError("Too many invalid verification attempts.")
            row = connection.execute(
                """SELECT a.*,r.name AS role_name,r.permissions FROM admin_accounts a
                JOIN admin_roles r ON r.id=a.role_id WHERE a.id=?""",
                (int(challenge["subject"]),),
            ).fetchone()
            valid = bool(row and row["active"] and row["mfa_enabled"] and verify_totp(row["mfa_secret"], code))
            if not valid and row:
                recovery = connection.execute(
                    "SELECT id FROM admin_mfa_recovery_codes WHERE admin_id=? AND code_hash=? AND used_at=''",
                    (row["id"], token_hash(code)),
                ).fetchone()
                if recovery:
                    connection.execute("UPDATE admin_mfa_recovery_codes SET used_at=? WHERE id=?", (utc_now(), recovery["id"]))
                    valid = True
            if not valid:
                connection.execute("UPDATE auth_challenges SET attempts=attempts+1 WHERE id=?", (challenge_id,))
                connection.commit()
                raise AuthenticationError("The authentication code is incorrect.")
            now = utc_now()
            connection.execute("UPDATE auth_challenges SET consumed_at=? WHERE id=?", (now, challenge_id))
            connection.execute("UPDATE admin_accounts SET last_login_at=?,updated_at=? WHERE id=?", (now, now, row["id"]))
            identity = self._admin_identity(row)
        return {"admin": identity, **self._create_session("ADMIN", row["id"], ip_address, user_agent)}

    def authenticate_admin(self, raw_token: object, csrf: object = "", mutate: bool = False, permission: str = "overview") -> dict:
        session = self._session(raw_token, "ADMIN", csrf, mutate)
        with self.connect() as connection:
            row = connection.execute(
                """SELECT a.*,r.name AS role_name,r.permissions FROM admin_accounts a
                JOIN admin_roles r ON r.id=a.role_id WHERE a.id=?""",
                (int(session["subject_id"]),),
            ).fetchone()
        if not row or not row["active"]:
            raise AuthenticationError("The administrator account is no longer active.")
        identity = self._admin_identity(row)
        if permission and "*" not in identity["permissions"] and permission not in identity["permissions"]:
            raise PermissionError("Your administrator role cannot perform this action.")
        return identity

    def revoke_session(self, raw_token: object, session_type: str) -> None:
        token = str(raw_token or "")
        if not token:
            return
        with self.connect() as connection:
            connection.execute("UPDATE auth_sessions SET revoked_at=? WHERE token_hash=? AND session_type=? AND revoked_at=''", (utc_now(), token_hash(token), session_type))

    def list_admins(self) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT a.*,r.name AS role_name,r.permissions FROM admin_accounts a
                JOIN admin_roles r ON r.id=a.role_id ORDER BY a.created_at,a.id"""
            ).fetchall()
        return [{**self._admin_identity(row), "active": bool(row["active"]), "last_login_at": row["last_login_at"], "created_at": row["created_at"]} for row in rows]

    def create_admin(self, payload: dict) -> dict:
        username = str(payload.get("username") or "").strip()
        if not ADMIN_USERNAME_PATTERN.fullmatch(username):
            raise ValueError("Administrator username must use 3–40 letters, numbers, dots, dashes, or underscores.")
        display_name = re.sub(r"\s+", " ", str(payload.get("display_name") or "").strip())
        if len(display_name) < 2 or len(display_name) > 80:
            raise ValueError("Administrator name must contain 2–80 characters.")
        password = validate_password(payload.get("password"))
        role_id = int(payload.get("role_id") or 0)
        digest, salt, iterations = hash_password(password)
        now = utc_now()
        with self.connect() as connection:
            role = connection.execute("SELECT name FROM admin_roles WHERE id=?", (role_id,)).fetchone()
            if not role:
                raise ValueError("Choose an existing administrator role.")
            if connection.execute("SELECT 1 FROM admin_accounts WHERE username=? COLLATE NOCASE", (username,)).fetchone():
                raise ValueError("That administrator username already exists.")
            cursor = connection.execute(
                """INSERT INTO admin_accounts
                (username,display_name,password_hash,password_salt,password_iterations,role_id,active,password_changed_at,created_at,updated_at)
                VALUES(?,?,?,?,?,?,1,?,?,?)""",
                (username, display_name, digest, salt, iterations, role_id, now, now, now),
            )
            admin_id = cursor.lastrowid
            self.platform._audit(connection, "Security", "Administrator created", username, role["name"])
        return next(item for item in self.list_admins() if item["id"] == admin_id)

    def update_admin(self, admin_id: int, payload: dict, actor_id: int) -> dict:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute("SELECT * FROM admin_accounts WHERE id=?", (admin_id,)).fetchone()
            if not current:
                raise LookupError("Administrator not found.")
            display_name = re.sub(r"\s+", " ", str(payload.get("display_name", current["display_name"])).strip())
            if len(display_name) < 2 or len(display_name) > 80:
                raise ValueError("Administrator name must contain 2–80 characters.")
            role_id = int(payload.get("role_id", current["role_id"]))
            if not connection.execute("SELECT 1 FROM admin_roles WHERE id=?", (role_id,)).fetchone():
                raise ValueError("Choose an existing administrator role.")
            active = 1 if payload.get("active", bool(current["active"])) else 0
            if admin_id == actor_id and not active:
                raise ValueError("You cannot disable your own administrator account.")
            reset_mfa = bool(payload.get("reset_mfa", False))
            connection.execute(
                """UPDATE admin_accounts SET display_name=?,role_id=?,active=?,
                mfa_secret=CASE WHEN ? THEN '' ELSE mfa_secret END,
                pending_mfa_secret=CASE WHEN ? THEN '' ELSE pending_mfa_secret END,
                mfa_enabled=CASE WHEN ? THEN 0 ELSE mfa_enabled END,updated_at=? WHERE id=?""",
                (display_name, role_id, active, reset_mfa, reset_mfa, reset_mfa, utc_now(), admin_id),
            )
            if reset_mfa:
                connection.execute("DELETE FROM admin_mfa_recovery_codes WHERE admin_id=?", (admin_id,))
            if not active:
                connection.execute("UPDATE auth_sessions SET revoked_at=? WHERE session_type='ADMIN' AND subject_id=? AND revoked_at=''", (utc_now(), str(admin_id)))
            self.platform._audit(connection, "Security", "Administrator updated", current["username"], f"Active {bool(active)}; MFA reset {reset_mfa}")
        return next(item for item in self.list_admins() if item["id"] == admin_id)

    def begin_mfa_enrollment(self, admin_id: int, issuer: str = "RoosterRun") -> dict:
        secret = generate_totp_secret()
        with self.connect() as connection:
            row = connection.execute("SELECT username FROM admin_accounts WHERE id=? AND active=1", (admin_id,)).fetchone()
            if not row:
                raise LookupError("Administrator not found.")
            connection.execute("UPDATE admin_accounts SET pending_mfa_secret=?,updated_at=? WHERE id=?", (secret, utc_now(), admin_id))
        label = quote(f"{issuer}:{row['username']}")
        uri = f"otpauth://totp/{label}?secret={secret}&issuer={quote(issuer)}&digits=6&period=30"
        return {"secret": secret, "otpauth_uri": uri}

    def confirm_mfa_enrollment(self, admin_id: int, code: object) -> dict:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM admin_accounts WHERE id=? AND active=1", (admin_id,)).fetchone()
            if not row or not row["pending_mfa_secret"]:
                raise ValueError("Start MFA setup before confirming it.")
            if not verify_totp(row["pending_mfa_secret"], code):
                raise AuthenticationError("The authentication code is incorrect.")
            recovery_codes = [f"RR-{secrets.token_hex(4).upper()}" for _ in range(8)]
            now = utc_now()
            connection.execute("UPDATE admin_accounts SET mfa_secret=pending_mfa_secret,pending_mfa_secret='',mfa_enabled=1,updated_at=? WHERE id=?", (now, admin_id))
            connection.execute("DELETE FROM admin_mfa_recovery_codes WHERE admin_id=?", (admin_id,))
            connection.executemany(
                "INSERT INTO admin_mfa_recovery_codes(admin_id,code_hash,created_at) VALUES(?,?,?)",
                [(admin_id, token_hash(code_value.replace("-", "")), now) for code_value in recovery_codes],
            )
            self.platform._audit(connection, "Security", "Administrator MFA enabled", row["username"], "Recovery codes issued")
        return {"mfa_enabled": True, "recovery_codes": recovery_codes}
