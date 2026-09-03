"""Identity, privacy, responsible-play, and operating-mode controls.

The engine deliberately keeps identity documents outside the public uploads
directory. Browser clients receive document metadata only; the raw file can be
read solely through an authenticated administrator endpoint.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


UTC = timezone.utc
DOCUMENT_TYPES = {"PAN", "DRIVING_LICENCE", "PASSPORT", "VOTER_ID"}
DOCUMENT_SIGNATURES = {
    "image/png": (b"\x89PNG\r\n\x1a\n", ".png"),
    "image/jpeg": (b"\xff\xd8\xff", ".jpg"),
    "image/webp": (b"RIFF", ".webp"),
    "application/pdf": (b"%PDF-", ".pdf"),
}
STATE_PATTERN = re.compile(r"^[A-Z]{2,3}$")
LEGAL_NOTICES = {
    "SOCIAL_PREVIEW": "Social preview build. Real-money operation requires a permitted deployment.",
    "APPROVAL_DEMO": "Approval demonstration using demo credits only. No real funds are accepted or paid.",
    "REAL_MONEY": "Players must be 18+. Betting involves financial risk; play responsibly and only with funds you can afford to lose.",
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def parse_date(value: object) -> date:
    try:
        result = date.fromisoformat(str(value or "").strip())
    except ValueError:
        raise ValueError("Enter a valid date of birth.") from None
    if result >= date.today():
        raise ValueError("Date of birth must be in the past.")
    return result


def age_on(dob: date, today: date | None = None) -> int:
    current = today or date.today()
    return current.year - dob.year - ((current.month, current.day) < (dob.month, dob.day))


def clean_text(value: object, label: str, minimum: int, maximum: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if len(text) < minimum or len(text) > maximum:
        raise ValueError(f"{label} must contain {minimum}–{maximum} characters.")
    return text


class ComplianceEngine:
    def __init__(self, platform):
        self.platform = platform
        self.operating_mode = platform.operating_mode
        self.private_dir = (platform.data_dir / "private" / "identity").resolve()
        self.private_dir.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def connect(self):
        return self.platform.connect()

    def _initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS compliance_profiles (
                    user_id TEXT PRIMARY KEY REFERENCES user_wallets(user_id),
                    legal_name TEXT NOT NULL DEFAULT '',
                    date_of_birth TEXT NOT NULL DEFAULT '',
                    state_code TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'NOT_SUBMITTED'
                        CHECK(status IN ('NOT_SUBMITTED','PENDING','VERIFIED','REJECTED','REVIEW_REQUIRED')),
                    consent_identity INTEGER NOT NULL DEFAULT 0 CHECK(consent_identity IN (0,1)),
                    consent_privacy INTEGER NOT NULL DEFAULT 0 CHECK(consent_privacy IN (0,1)),
                    submitted_at TEXT NOT NULL DEFAULT '',
                    reviewed_at TEXT NOT NULL DEFAULT '',
                    reviewed_by TEXT NOT NULL DEFAULT '',
                    review_note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS compliance_documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL REFERENCES user_wallets(user_id),
                    document_type TEXT NOT NULL,
                    private_filename TEXT NOT NULL UNIQUE,
                    content_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(user_id, sha256)
                );

                CREATE INDEX IF NOT EXISTS compliance_profiles_status_idx
                ON compliance_profiles(status, submitted_at);

                CREATE TABLE IF NOT EXISTS responsible_controls (
                    user_id TEXT PRIMARY KEY REFERENCES user_wallets(user_id),
                    daily_deposit_limit_paise INTEGER NOT NULL DEFAULT 0 CHECK(daily_deposit_limit_paise >= 0),
                    daily_stake_limit_paise INTEGER NOT NULL DEFAULT 0 CHECK(daily_stake_limit_paise >= 0),
                    session_limit_minutes INTEGER NOT NULL DEFAULT 0 CHECK(session_limit_minutes >= 0),
                    pending_limits_json TEXT NOT NULL DEFAULT '{}',
                    pending_effective_at TEXT NOT NULL DEFAULT '',
                    cool_off_until TEXT NOT NULL DEFAULT '',
                    exclusion_until TEXT NOT NULL DEFAULT '',
                    permanent_exclusion INTEGER NOT NULL DEFAULT 0 CHECK(permanent_exclusion IN (0,1)),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS responsible_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL REFERENCES user_wallets(user_id),
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    actor TEXT NOT NULL DEFAULT 'PLAYER',
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS responsible_events_user_idx
                ON responsible_events(user_id, created_at DESC);
                """
            )
            defaults = {
                "operating_mode": self.operating_mode,
                "minimum_age": 18,
                "kyc_required_for_betting": True,
                "kyc_required_for_deposit": True,
                "kyc_required_for_withdrawal": True,
                "limit_increase_delay_hours": 24,
                "document_retention_days": 365,
                "blocked_state_codes": [],
                "legal_notice": LEGAL_NOTICES.get(self.operating_mode, LEGAL_NOTICES["SOCIAL_PREVIEW"]),
            }
            connection.execute(
                "INSERT OR IGNORE INTO admin_settings(setting_key,setting_value,updated_at) VALUES('compliance',?,?)",
                (json.dumps(defaults), utc_now()),
            )
            current_row = connection.execute("SELECT setting_value FROM admin_settings WHERE setting_key='compliance'").fetchone()
            current = json.loads(current_row["setting_value"] or "{}") if current_row else defaults
            current["operating_mode"] = self.operating_mode
            stale_notices = {notice for mode, notice in LEGAL_NOTICES.items() if mode != self.operating_mode}
            if str(current.get("legal_notice", "")) in stale_notices or "Real-money operation requires" in str(current.get("legal_notice", "")):
                current["legal_notice"] = defaults["legal_notice"]
            connection.execute(
                "UPDATE admin_settings SET setting_value=?,updated_at=? WHERE setting_key='compliance'",
                (json.dumps(current), utc_now()),
            )
            if self.platform.preview_mode:
                now = utc_now()
                connection.execute(
                    """INSERT INTO compliance_profiles
                    (user_id,legal_name,date_of_birth,state_code,status,consent_identity,consent_privacy,submitted_at,reviewed_at,reviewed_by,created_at,updated_at)
                    VALUES('arena-guest','Arena Guest','1990-01-01','KA','VERIFIED',1,1,?,?, 'PREVIEW',?,?)
                    ON CONFLICT(user_id) DO NOTHING""",
                    (now, now, now, now),
                )
                self._ensure_controls(connection, "arena-guest")

    def policy(self) -> dict:
        with self.connect() as connection:
            row = connection.execute("SELECT setting_value FROM admin_settings WHERE setting_key='compliance'").fetchone()
        return json.loads(row["setting_value"] or "{}") if row else {}

    def save_policy(self, payload: dict) -> dict:
        current = self.policy()
        allowed = {
            "minimum_age", "kyc_required_for_betting", "kyc_required_for_deposit",
            "kyc_required_for_withdrawal", "limit_increase_delay_hours",
            "document_retention_days", "blocked_state_codes", "legal_notice",
        }
        for key in allowed:
            if key in payload:
                current[key] = payload[key]
        current["minimum_age"] = min(99, max(18, int(current.get("minimum_age", 18))))
        current["limit_increase_delay_hours"] = min(168, max(1, int(current.get("limit_increase_delay_hours", 24))))
        current["document_retention_days"] = min(3650, max(30, int(current.get("document_retention_days", 365))))
        current["blocked_state_codes"] = sorted({str(code).upper() for code in current.get("blocked_state_codes", []) if STATE_PATTERN.fullmatch(str(code).upper())})
        current["legal_notice"] = clean_text(current.get("legal_notice"), "Legal notice", 10, 500)
        current["operating_mode"] = self.operating_mode
        for key in ("kyc_required_for_betting", "kyc_required_for_deposit", "kyc_required_for_withdrawal"):
            current[key] = bool(current.get(key))
        with self.connect() as connection:
            connection.execute(
                "UPDATE admin_settings SET setting_value=?,updated_at=? WHERE setting_key='compliance'",
                (json.dumps(current), utc_now()),
            )
            self.platform._audit(connection, "Compliance", "Policy updated", "Platform safeguards", "Identity, limits, and jurisdiction controls")
        return current

    def _ensure_profile(self, connection, user_id: str) -> None:
        now = utc_now()
        connection.execute(
            "INSERT OR IGNORE INTO compliance_profiles(user_id,created_at,updated_at) VALUES(?,?,?)",
            (user_id, now, now),
        )

    def _ensure_controls(self, connection, user_id: str) -> None:
        now = utc_now()
        connection.execute(
            "INSERT OR IGNORE INTO responsible_controls(user_id,created_at,updated_at) VALUES(?,?,?)",
            (user_id, now, now),
        )

    @staticmethod
    def _profile_dict(row, documents: list[dict], policy: dict) -> dict:
        dob = parse_date(row["date_of_birth"]) if row["date_of_birth"] else None
        return {
            "user_id": row["user_id"], "legal_name": row["legal_name"],
            "date_of_birth": row["date_of_birth"], "age": age_on(dob) if dob else None,
            "state_code": row["state_code"], "status": row["status"],
            "submitted_at": row["submitted_at"], "reviewed_at": row["reviewed_at"],
            "reviewed_by": row["reviewed_by"], "review_note": row["review_note"],
            "documents": documents, "minimum_age": int(policy.get("minimum_age", 18)),
            "notice": policy.get("legal_notice", ""),
        }

    def profile(self, user_id: str) -> dict:
        self.platform.ensure_user(user_id)
        policy = self.policy()
        with self.connect() as connection:
            self._ensure_profile(connection, user_id)
            row = connection.execute("SELECT * FROM compliance_profiles WHERE user_id=?", (user_id,)).fetchone()
            documents = [
                {"id": item["id"], "document_type": item["document_type"], "content_type": item["content_type"], "size_bytes": item["size_bytes"], "created_at": item["created_at"]}
                for item in connection.execute("SELECT * FROM compliance_documents WHERE user_id=? ORDER BY id DESC", (user_id,)).fetchall()
            ]
        return self._profile_dict(row, documents, policy)

    def _save_document(self, user_id: str, item: dict) -> dict:
        document_type = str(item.get("document_type") or "").upper()
        if document_type not in DOCUMENT_TYPES:
            raise ValueError("Choose PAN, driving licence, passport, or voter ID. Aadhaar images are not accepted.")
        data_url = str(item.get("data_url") or "")
        match = re.fullmatch(r"data:([^;,]+);base64,(.+)", data_url, re.DOTALL)
        if not match or match.group(1).lower() not in DOCUMENT_SIGNATURES:
            raise ValueError("Verification documents must be PNG, JPG, WebP, or PDF files.")
        content_type = match.group(1).lower()
        try:
            raw = base64.b64decode(match.group(2), validate=True)
        except Exception:
            raise ValueError("The verification document could not be read.") from None
        if not raw or len(raw) > 8 * 1024 * 1024:
            raise ValueError("Each verification document must be smaller than 8 MB.")
        signature, suffix = DOCUMENT_SIGNATURES[content_type]
        if not raw.startswith(signature) or (content_type == "image/webp" and raw[8:12] != b"WEBP"):
            raise ValueError("The verification document content does not match its file type.")
        digest = hashlib.sha256(raw).hexdigest()
        filename = f"{secrets.token_hex(20)}{suffix}"
        target = (self.private_dir / filename).resolve()
        if target.parent != self.private_dir:
            raise ValueError("Invalid private document path.")
        target.write_bytes(raw)
        return {"document_type": document_type, "private_filename": filename, "content_type": content_type, "size_bytes": len(raw), "sha256": digest}

    def submit(self, user_id: str, payload: dict) -> dict:
        self.platform.ensure_user(user_id)
        legal_name = clean_text(payload.get("legal_name"), "Legal name", 2, 100)
        dob = parse_date(payload.get("date_of_birth"))
        policy = self.policy()
        if age_on(dob) < int(policy.get("minimum_age", 18)):
            raise ValueError("You do not meet the minimum age requirement.")
        state_code = str(payload.get("state_code") or "").strip().upper()
        if not STATE_PATTERN.fullmatch(state_code):
            raise ValueError("Choose a valid state or union territory.")
        if state_code in set(policy.get("blocked_state_codes", [])):
            raise PermissionError("This service is not available in the selected jurisdiction.")
        if payload.get("consent_identity") is not True or payload.get("consent_privacy") is not True:
            raise ValueError("Identity verification and privacy consent are required.")
        documents = payload.get("documents")
        if not isinstance(documents, list) or not 1 <= len(documents) <= 3:
            raise ValueError("Upload one to three identity documents.")
        saved: list[dict] = []
        try:
            for item in documents:
                if not isinstance(item, dict):
                    raise ValueError("Invalid verification document.")
                saved.append(self._save_document(user_id, item))
            now = utc_now()
            with self.connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                self._ensure_profile(connection, user_id)
                connection.execute(
                    """UPDATE compliance_profiles SET legal_name=?,date_of_birth=?,state_code=?,status='PENDING',
                    consent_identity=1,consent_privacy=1,submitted_at=?,reviewed_at='',reviewed_by='',review_note='',updated_at=? WHERE user_id=?""",
                    (legal_name, dob.isoformat(), state_code, now, now, user_id),
                )
                for document in saved:
                    cursor = connection.execute(
                        """INSERT OR IGNORE INTO compliance_documents
                        (user_id,document_type,private_filename,content_type,size_bytes,sha256,created_at)
                        VALUES(?,?,?,?,?,?,?)""",
                        (user_id, document["document_type"], document["private_filename"], document["content_type"], document["size_bytes"], document["sha256"], now),
                    )
                    if cursor.rowcount == 0:
                        (self.private_dir / document["private_filename"]).unlink(missing_ok=True)
                connection.execute(
                    "INSERT INTO responsible_events(user_id,event_type,payload_json,actor,created_at) VALUES(?, 'KYC_SUBMITTED', ?, 'PLAYER', ?)",
                    (user_id, json.dumps({"documents": len(saved), "state_code": state_code}), now),
                )
                self.platform.operations.notify(
                    connection, audience="USER", user_id=user_id, event_type="KYC_SUBMITTED", severity="INFO",
                    title="Verification submitted", message="Your identity documents are in the private compliance review queue.",
                    action_route="#profile", dedupe_key=f"user:{user_id}:kyc-submitted:{now}",
                )
                self.platform.operations.notify(
                    connection, audience="ADMIN", event_type="KYC_REVIEW_REQUIRED", severity="WARNING",
                    title="Identity review required", message=f"{user_id} submitted {len(saved)} private verification document(s).",
                    action_route="#compliance", dedupe_key=f"admin:kyc-review:{user_id}:{now}",
                )
            return self.profile(user_id)
        except Exception:
            for document in saved:
                (self.private_dir / document["private_filename"]).unlink(missing_ok=True)
            raise

    def admin_queue(self, status: str = "") -> list[dict]:
        values: list[object] = []
        where = ""
        if status:
            normalized = status.upper()
            if normalized not in {"NOT_SUBMITTED", "PENDING", "VERIFIED", "REJECTED", "REVIEW_REQUIRED"}:
                raise ValueError("Invalid compliance status.")
            where = "WHERE p.status=?"
            values.append(normalized)
        policy = self.policy()
        with self.connect() as connection:
            rows = connection.execute(
                f"""SELECT p.*,w.display_name,w.mobile FROM compliance_profiles p
                JOIN user_wallets w ON w.user_id=p.user_id {where}
                ORDER BY CASE p.status WHEN 'PENDING' THEN 0 WHEN 'REVIEW_REQUIRED' THEN 1 ELSE 2 END,p.submitted_at ASC""",
                values,
            ).fetchall()
            results = []
            for row in rows:
                documents = [
                    {"id": item["id"], "document_type": item["document_type"], "content_type": item["content_type"], "size_bytes": item["size_bytes"], "created_at": item["created_at"]}
                    for item in connection.execute("SELECT * FROM compliance_documents WHERE user_id=? ORDER BY id DESC", (row["user_id"],)).fetchall()
                ]
                item = self._profile_dict(row, documents, policy)
                item.update({"display_name": row["display_name"], "mobile": row["mobile"]})
                results.append(item)
        return results

    def decide(self, user_id: str, decision: object, note: object, actor: str) -> dict:
        normalized = str(decision or "").upper()
        if normalized not in {"VERIFIED", "REJECTED", "REVIEW_REQUIRED"}:
            raise ValueError("Choose verified, rejected, or needs more information.")
        review_note = str(note or "").strip()
        if normalized != "VERIFIED":
            review_note = clean_text(review_note, "Review note", 3, 500)
        now = utc_now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM compliance_profiles WHERE user_id=?", (user_id,)).fetchone()
            if not row:
                raise LookupError("Verification profile not found.")
            if not row["date_of_birth"] or age_on(parse_date(row["date_of_birth"])) < int(self.policy().get("minimum_age", 18)):
                raise ValueError("This profile does not meet the minimum age requirement.")
            connection.execute(
                "UPDATE compliance_profiles SET status=?,reviewed_at=?,reviewed_by=?,review_note=?,updated_at=? WHERE user_id=?",
                (normalized, now, actor, review_note, now, user_id),
            )
            connection.execute(
                "INSERT INTO responsible_events(user_id,event_type,payload_json,actor,created_at) VALUES(?,?,?,?,?)",
                (user_id, "KYC_DECISION", json.dumps({"decision": normalized, "note": review_note}), actor, now),
            )
            self.platform._audit(connection, "Compliance", f"Identity {normalized.lower()}", user_id, review_note or "Checks completed")
            self.platform.operations.notify(
                connection, audience="USER", user_id=user_id, event_type=f"KYC_{normalized}",
                severity="SUCCESS" if normalized == "VERIFIED" else "WARNING",
                title="Identity verified" if normalized == "VERIFIED" else "Verification update",
                message=("Your identity and age review is approved." if normalized == "VERIFIED" else review_note),
                action_route="#profile", dedupe_key=f"user:{user_id}:kyc-decision:{normalized}:{now}",
            )
        return self.profile(user_id)

    def document(self, document_id: int) -> tuple[Path, str]:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM compliance_documents WHERE id=?", (document_id,)).fetchone()
        if not row:
            raise LookupError("Verification document not found.")
        path = (self.private_dir / row["private_filename"]).resolve()
        if path.parent != self.private_dir or not path.is_file():
            raise LookupError("Verification document file is unavailable.")
        return path, row["content_type"]

    def _apply_pending(self, connection, user_id: str) -> None:
        self._ensure_controls(connection, user_id)
        row = connection.execute("SELECT * FROM responsible_controls WHERE user_id=?", (user_id,)).fetchone()
        if not row["pending_effective_at"]:
            return
        effective = datetime.fromisoformat(row["pending_effective_at"])
        if effective.tzinfo is None:
            effective = effective.replace(tzinfo=UTC)
        if effective > datetime.now(UTC):
            return
        pending = json.loads(row["pending_limits_json"] or "{}")
        connection.execute(
            """UPDATE responsible_controls SET daily_deposit_limit_paise=?,daily_stake_limit_paise=?,session_limit_minutes=?,
            pending_limits_json='{}',pending_effective_at='',updated_at=? WHERE user_id=?""",
            (int(pending.get("daily_deposit_limit_paise", row["daily_deposit_limit_paise"])), int(pending.get("daily_stake_limit_paise", row["daily_stake_limit_paise"])), int(pending.get("session_limit_minutes", row["session_limit_minutes"])), utc_now(), user_id),
        )

    @staticmethod
    def _controls_dict(row) -> dict:
        pending = json.loads(row["pending_limits_json"] or "{}")
        return {
            "daily_deposit_limit": round(row["daily_deposit_limit_paise"] / 100, 2),
            "daily_stake_limit": round(row["daily_stake_limit_paise"] / 100, 2),
            "session_limit_minutes": row["session_limit_minutes"],
            "pending_limits": {
                "daily_deposit_limit": round(int(pending.get("daily_deposit_limit_paise", 0)) / 100, 2),
                "daily_stake_limit": round(int(pending.get("daily_stake_limit_paise", 0)) / 100, 2),
                "session_limit_minutes": int(pending.get("session_limit_minutes", 0)),
            } if pending else {},
            "pending_effective_at": row["pending_effective_at"],
            "cool_off_until": row["cool_off_until"], "exclusion_until": row["exclusion_until"],
            "permanent_exclusion": bool(row["permanent_exclusion"]),
        }

    def controls(self, user_id: str) -> dict:
        self.platform.ensure_user(user_id)
        with self.connect() as connection:
            self._apply_pending(connection, user_id)
            row = connection.execute("SELECT * FROM responsible_controls WHERE user_id=?", (user_id,)).fetchone()
        result = self._controls_dict(row)
        result["increase_delay_hours"] = int(self.policy().get("limit_increase_delay_hours", 24))
        return result

    @staticmethod
    def _money_limit(value: object, label: str) -> int:
        try:
            paise = int(round(float(value or 0) * 100))
        except (TypeError, ValueError):
            raise ValueError(f"Enter a valid {label}.") from None
        if paise < 0 or paise > 100_000_000 * 100:
            raise ValueError(f"{label} is outside the allowed range.")
        return paise

    def update_limits(self, user_id: str, payload: dict) -> dict:
        requested = {
            "daily_deposit_limit_paise": self._money_limit(payload.get("daily_deposit_limit"), "daily deposit limit"),
            "daily_stake_limit_paise": self._money_limit(payload.get("daily_stake_limit"), "daily stake limit"),
            "session_limit_minutes": min(1440, max(0, int(payload.get("session_limit_minutes") or 0))),
        }
        now = utc_now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._apply_pending(connection, user_id)
            row = connection.execute("SELECT * FROM responsible_controls WHERE user_id=?", (user_id,)).fetchone()
            increases = False
            immediate = {}
            for key, value in requested.items():
                current = int(row[key])
                # Zero means no personal cap, so changing from zero to a value is a decrease.
                is_increase = (value == 0 and current > 0) or (current > 0 and value > current)
                increases = increases or is_increase
                immediate[key] = current if is_increase else value
            pending = requested if increases else {}
            delay = int(self.policy().get("limit_increase_delay_hours", 24))
            effective_at = (datetime.now(UTC) + timedelta(hours=delay)).isoformat(timespec="seconds") if pending else ""
            connection.execute(
                """UPDATE responsible_controls SET daily_deposit_limit_paise=?,daily_stake_limit_paise=?,session_limit_minutes=?,
                pending_limits_json=?,pending_effective_at=?,updated_at=? WHERE user_id=?""",
                (immediate["daily_deposit_limit_paise"], immediate["daily_stake_limit_paise"], immediate["session_limit_minutes"], json.dumps(pending), effective_at, now, user_id),
            )
            connection.execute(
                "INSERT INTO responsible_events(user_id,event_type,payload_json,actor,created_at) VALUES(?, 'LIMITS_CHANGED', ?, 'PLAYER', ?)",
                (user_id, json.dumps({"requested": requested, "delayed": increases}), now),
            )
        return self.controls(user_id)

    def restrict(self, user_id: str, kind: str, duration_days: int = 0) -> dict:
        normalized = str(kind or "").upper()
        if normalized not in {"COOL_OFF", "SELF_EXCLUDE"}:
            raise ValueError("Choose cooling-off or self-exclusion.")
        now_dt = datetime.now(UTC)
        if normalized == "COOL_OFF":
            if duration_days not in {1, 7, 30}:
                raise ValueError("Cooling-off must be 1, 7, or 30 days.")
            field = "cool_off_until"
            until = (now_dt + timedelta(days=duration_days)).isoformat(timespec="seconds")
            permanent = 0
        else:
            if duration_days not in {180, 365, 0}:
                raise ValueError("Self-exclusion must be 180 days, 365 days, or permanent.")
            field = "exclusion_until"
            permanent = 1 if duration_days == 0 else 0
            until = "" if permanent else (now_dt + timedelta(days=duration_days)).isoformat(timespec="seconds")
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._ensure_controls(connection, user_id)
            if normalized == "COOL_OFF":
                connection.execute("UPDATE responsible_controls SET cool_off_until=?,updated_at=? WHERE user_id=?", (until, utc_now(), user_id))
            else:
                connection.execute("UPDATE responsible_controls SET exclusion_until=?,permanent_exclusion=?,updated_at=? WHERE user_id=?", (until, permanent, utc_now(), user_id))
            connection.execute(
                "INSERT INTO responsible_events(user_id,event_type,payload_json,actor,created_at) VALUES(?,?,?,?,?)",
                (user_id, normalized, json.dumps({"duration_days": duration_days, "until": until, "permanent": bool(permanent)}), "PLAYER", utc_now()),
            )
        return self.controls(user_id)

    def _require_legal_mode(self, action: str) -> None:
        if self.platform.preview_mode or self.operating_mode in {"APPROVAL_DEMO", "REAL_MONEY"}:
            return
        raise PermissionError(f"{action.title()} is unavailable in social-preview mode. Set ROOSTERRUN_OPERATING_MODE=REAL_MONEY to enable it.")

    def assert_allowed(self, user_id: str, action: str, amount_paise: int = 0) -> None:
        self.platform.ensure_user(user_id)
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self.assert_allowed_in_transaction(connection, user_id, action, amount_paise)

    def assert_allowed_in_transaction(self, connection, user_id: str, action: str, amount_paise: int = 0) -> None:
        action = str(action).upper()
        if action in {"BET", "DEPOSIT"}:
            self._require_legal_mode(action.lower())
        policy_row = connection.execute("SELECT setting_value FROM admin_settings WHERE setting_key='compliance'").fetchone()
        policy = json.loads(policy_row["setting_value"] or "{}") if policy_row else {}
        self._ensure_profile(connection, user_id)
        profile = connection.execute("SELECT * FROM compliance_profiles WHERE user_id=?", (user_id,)).fetchone()
        if profile["state_code"] and profile["state_code"] in set(policy.get("blocked_state_codes", [])):
            raise PermissionError("This service is unavailable in your selected jurisdiction.")
        if policy.get(f"kyc_required_for_{'betting' if action == 'BET' else action.lower()}", False) and profile["status"] != "VERIFIED":
            raise PermissionError("Complete identity and age verification before continuing.")
        self._apply_pending(connection, user_id)
        controls_row = connection.execute("SELECT * FROM responsible_controls WHERE user_id=?", (user_id,)).fetchone()
        controls = self._controls_dict(controls_row)
        now = datetime.now(UTC)
        if action in {"BET", "DEPOSIT"}:
            if controls["permanent_exclusion"]:
                raise PermissionError("This account is permanently self-excluded. Withdrawals and support remain available.")
            for value, message in ((controls["exclusion_until"], "This account is self-excluded."), (controls["cool_off_until"], "This account is in a cooling-off period.")):
                if value and datetime.fromisoformat(value) > now:
                    raise PermissionError(f"{message} Withdrawals and support remain available.")
        start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(timespec="seconds")
        if action == "DEPOSIT" and controls["daily_deposit_limit"] > 0:
            used = int(connection.execute(
                "SELECT COALESCE(SUM(amount_paise),0) AS total FROM payment_requests WHERE user_id=? AND request_type='DEPOSIT' AND status IN ('PENDING','APPROVED') AND created_at>=?",
                (user_id, start),
            ).fetchone()["total"])
            if used + amount_paise > int(round(controls["daily_deposit_limit"] * 100)):
                raise PermissionError("This deposit would exceed your daily deposit limit.")
        if action == "BET" and controls["daily_stake_limit"] > 0:
            used = int(connection.execute(
                "SELECT COALESCE(SUM(stake_paise),0) AS total FROM cockfight_bets WHERE user_id=? AND created_at>=?",
                (user_id, start),
            ).fetchone()["total"])
            if used + amount_paise > int(round(controls["daily_stake_limit"] * 100)):
                raise PermissionError("This bet would exceed your daily stake limit.")

    def health(self) -> dict:
        with self.connect() as connection:
            pending = int(connection.execute("SELECT COUNT(*) AS total FROM compliance_profiles WHERE status IN ('PENDING','REVIEW_REQUIRED')").fetchone()["total"])
            excluded = int(connection.execute("SELECT COUNT(*) AS total FROM responsible_controls WHERE permanent_exclusion=1 OR exclusion_until<>''").fetchone()["total"])
        return {"status": "ok", "operating_mode": self.operating_mode, "pending_reviews": pending, "restricted_players": excluded, "private_storage": self.private_dir.is_dir()}
