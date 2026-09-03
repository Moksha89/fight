"""Generate versioned secret files for a controlled production rotation."""

from __future__ import annotations

import argparse
import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path


def write_private(path: Path, value: str) -> None:
    path.write_text(value + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a new RoosterRun internal secret generation")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--generation", type=int, required=True)
    args = parser.parse_args()
    if args.generation < 1:
        raise SystemExit("Generation must be at least 1.")
    target = args.output_dir.resolve()
    target.mkdir(parents=True, exist_ok=True)
    current_hook = target / "srs_hook_secret"
    previous_hook = target / "srs_hook_secret_previous"
    if current_hook.is_file():
        previous = current_hook.read_text(encoding="utf-8").strip()
        if previous:
            write_private(previous_hook, previous)
    elif not previous_hook.is_file():
        write_private(previous_hook, secrets.token_urlsafe(48))
    write_private(current_hook, secrets.token_urlsafe(48))
    for name in ("postgres_password", "backup_repository_password", "metrics_token", "internal_alert_token", "grafana_admin_password"):
        write_private(target / name, secrets.token_urlsafe(48))
    write_private(target / "bootstrap_admin_password", "Rr9!" + secrets.token_urlsafe(32))
    manifest = {
        "generation": args.generation,
        "rotated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files": ["srs_hook_secret", "srs_hook_secret_previous", "postgres_password", "backup_repository_password", "metrics_token", "internal_alert_token", "grafana_admin_password", "bootstrap_admin_password"],
        "operator": os.environ.get("USERNAME") or os.environ.get("USER") or "unknown",
    }
    write_private(target / "rotation-manifest.json", json.dumps(manifest, indent=2))
    print(json.dumps({"status": "created", "directory": str(target), **manifest}))


if __name__ == "__main__":
    main()
