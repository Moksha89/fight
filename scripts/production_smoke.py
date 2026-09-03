"""Verify configured production dependencies and optionally send test alerts."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from urllib import request as urlrequest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
from database import Database  # noqa: E402
from delivery_engine import DeliveryEngine  # noqa: E402
from runtime_config import database_url_from_env, load_secret_files, validate_runtime_secrets  # noqa: E402


class ProviderPlatform:
    def __init__(self, path: Path):
        self.database = Database(path)

    def connect(self):
        return self.database.connect()


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify RoosterRun production dependencies")
    parser.add_argument("--send-sms-to", default="")
    parser.add_argument("--send-email-to", default="")
    parser.add_argument("--send-alert", action="store_true")
    args = parser.parse_args()
    load_secret_files()
    validate_runtime_secrets(False)
    results: dict[str, object] = {}

    database = Database(Path("unused.sqlite3"), database_url_from_env())
    with database.connect() as connection:
        connection.execute("SELECT 1").fetchone()
    results["database"] = {"ok": True, "backend": database.describe()}

    media_url = os.environ.get("ROOSTERRUN_SRS_API_URL", "").strip()
    if not media_url:
        raise RuntimeError("ROOSTERRUN_SRS_API_URL is required.")
    with urlrequest.urlopen(media_url, timeout=5) as response:
        if response.status < 200 or response.status >= 300:
            raise RuntimeError("SRS health request failed.")
    results["streaming"] = {"ok": True, "health_url": media_url}

    with tempfile.TemporaryDirectory(prefix="roosterrun-provider-smoke-") as directory:
        delivery = DeliveryEngine(ProviderPlatform(Path(directory) / "provider.sqlite3"))
        results["providers"] = {
            "sms_configured": delivery.sms_configured,
            "email_configured": delivery.email_configured,
            "alerts_configured": delivery.alerts_configured,
        }
        if args.send_sms_to:
            delivery.send_sms(args.send_sms_to, "RoosterRun SMS provider verification. No action is required.", purpose="PROVIDER_TEST")
            results["sms_test"] = {"ok": True}
        if args.send_email_to:
            delivery.send_email(args.send_email_to, "RoosterRun email provider verification", "The production email delivery path is working.")
            results["email_test"] = {"ok": True}
        if args.send_alert:
            delivery.send_webhook("RoosterRun alert verification", "The production alert webhook is working.", "WARNING")
            results["alert_test"] = {"ok": True}
    print(json.dumps({"status": "passed", "results": results}, indent=2))


if __name__ == "__main__":
    main()
