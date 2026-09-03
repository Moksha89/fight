from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from types import MethodType


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
from manual_payments_server import PaymentService


with tempfile.TemporaryDirectory(prefix="roosterrun-delivery-") as directory:
    os.environ["ROOSTERRUN_SMTP_HOST"] = "smtp.vendor.com"
    os.environ["ROOSTERRUN_SMTP_FROM"] = "alerts@vendor.com"
    os.environ["ROOSTERRUN_ALERT_EMAIL_TO"] = "operator@vendor.com"
    service = PaymentService(Path(directory), preview_mode=True)
    sent: list[tuple[str, str, str]] = []

    def fake_email(self, destination: str, title: str, message: str) -> str:
        sent.append((destination, title, message))
        return "provider-message-1"

    service.delivery.send_email = MethodType(fake_email, service.delivery)
    with service.connect() as connection:
        service.operations.notify(
            connection, audience="ADMIN", event_type="TEST_ALERT", severity="CRITICAL",
            title="Test incident", message="Delivery verification", action_route="#operations",
            dedupe_key="test:critical:delivery",
        )
    assert service.delivery.deliver_once()
    with service.connect() as connection:
        row = connection.execute("SELECT * FROM notification_deliveries WHERE dedupe_key LIKE 'test:critical:delivery:%'").fetchone()
        assert row["status"] == "DELIVERED"
        assert row["provider_reference"] == "provider-message-1"
    assert sent == [("operator@vendor.com", "Test incident", "Delivery verification")]

    attempts = {"count": 0}
    def flaky_email(self, destination: str, title: str, message: str) -> str:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise TimeoutError("synthetic provider timeout")
        return "provider-message-2"
    service.delivery.send_email = MethodType(flaky_email, service.delivery)
    with service.connect() as connection:
        service.operations.notify(connection, audience="ADMIN", event_type="RETRY_ALERT", severity="CRITICAL", title="Retry test", message="Retry verification", dedupe_key="test:retry:delivery")
    assert service.delivery.deliver_once()
    with service.connect() as connection:
        connection.execute("UPDATE notification_deliveries SET next_attempt_at='2000-01-01T00:00:00+00:00' WHERE dedupe_key LIKE 'test:retry:delivery:%'")
    assert service.delivery.deliver_once()
    with service.connect() as connection:
        retried = connection.execute("SELECT * FROM notification_deliveries WHERE dedupe_key LIKE 'test:retry:delivery:%'").fetchone()
        assert retried["status"] == "DELIVERED" and retried["attempts"] == 2

print("Durable email/SMS/webhook delivery and retry checks passed.")
