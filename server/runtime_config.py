"""Runtime secret loading, validation, and rotation metadata checks."""

from __future__ import annotations

import os
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote


SECRET_NAMES = (
    "ROOSTERRUN_BOOTSTRAP_ADMIN_PASSWORD",
    "ROOSTERRUN_DATABASE_URL",
    "ROOSTERRUN_DATABASE_PASSWORD",
    "ROOSTERRUN_SMS_WEBHOOK_TOKEN",
    "ROOSTERRUN_TWILIO_AUTH_TOKEN",
    "ROOSTERRUN_SMTP_PASSWORD",
    "ROOSTERRUN_ALERT_WEBHOOK_TOKEN",
    "ROOSTERRUN_SRS_HOOK_SECRET",
    "ROOSTERRUN_SRS_HOOK_SECRET_PREVIOUS",
    "ROOSTERRUN_BACKUP_REPOSITORY_PASSWORD",
    "ROOSTERRUN_INTERNAL_ALERT_TOKEN",
)


def load_secret_files() -> None:
    """Load Docker/Kubernetes-style *_FILE variables without logging values."""

    for name in SECRET_NAMES:
        file_name = os.environ.get(f"{name}_FILE", "").strip()
        if not file_name or os.environ.get(name):
            continue
        path = Path(file_name)
        if not path.is_file():
            raise RuntimeError(f"Secret file for {name} does not exist.")
        value = path.read_text(encoding="utf-8").strip()
        if not value:
            raise RuntimeError(f"Secret file for {name} is empty.")
        os.environ[name] = value


def database_url_from_env() -> str:
    configured = os.environ.get("ROOSTERRUN_DATABASE_URL", "").strip()
    if configured:
        return configured
    host = os.environ.get("ROOSTERRUN_DATABASE_HOST", "").strip()
    if not host:
        return ""
    port = os.environ.get("ROOSTERRUN_DATABASE_PORT", "5432").strip()
    name = os.environ.get("ROOSTERRUN_DATABASE_NAME", "roosterrun").strip()
    user = os.environ.get("ROOSTERRUN_DATABASE_USER", "roosterrun").strip()
    password = os.environ.get("ROOSTERRUN_DATABASE_PASSWORD", "")
    return f"postgresql://{quote(user, safe='')}:{quote(password, safe='')}@{host}:{port}/{quote(name, safe='')}"


def secret_rotation_status(preview_mode: bool) -> dict:
    if preview_mode:
        return {"ok": True, "detail": "Preview mode"}
    required = os.environ.get("ROOSTERRUN_REQUIRE_SECRET_ROTATION", "1").strip().lower() not in {"0", "false", "no"}
    generation = os.environ.get("ROOSTERRUN_SECRET_GENERATION", "").strip()
    rotated_at = os.environ.get("ROOSTERRUN_SECRET_ROTATED_AT", "").strip()
    manifest_path = os.environ.get("ROOSTERRUN_SECRET_ROTATION_MANIFEST", "").strip()
    if manifest_path:
        try:
            manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
            generation = str(manifest.get("generation") or "")
            rotated_at = str(manifest.get("rotated_at") or "")
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return {"ok": False, "detail": "Secret rotation manifest is invalid"}
    if not required:
        return {"ok": True, "detail": "Rotation policy disabled"}
    try:
        generation_valid = int(generation) >= 1
        rotated = datetime.fromisoformat(rotated_at.replace("Z", "+00:00"))
        if rotated.tzinfo is None:
            rotated = rotated.replace(tzinfo=timezone.utc)
        age_days = (datetime.now(timezone.utc) - rotated.astimezone(timezone.utc)).days
    except (TypeError, ValueError):
        return {"ok": False, "detail": "Set secret generation and rotation timestamp"}
    if not generation_valid or age_days < 0 or age_days > 90:
        return {"ok": False, "detail": "Rotate production secrets (maximum age: 90 days)"}
    return {"ok": True, "detail": f"Generation {generation} · rotated {age_days} days ago"}


def validate_runtime_secrets(preview_mode: bool) -> None:
    if preview_mode:
        return
    suspicious = ("replace-with", "changeme", "example-token", "password123", "secret123")
    for name in SECRET_NAMES:
        value = os.environ.get(name, "").strip().lower()
        if value and any(marker in value for marker in suspicious):
            raise RuntimeError(f"{name} contains a placeholder value.")
    hook_secret = os.environ.get("ROOSTERRUN_SRS_HOOK_SECRET", "")
    previous = os.environ.get("ROOSTERRUN_SRS_HOOK_SECRET_PREVIOUS", "")
    if previous and previous == hook_secret:
        raise RuntimeError("Current and previous SRS hook secrets must differ.")
