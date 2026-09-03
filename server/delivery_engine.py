"""External SMS, email, and alert delivery with a durable retry outbox."""

from __future__ import annotations

import base64
import json
import os
import smtplib
import ssl
import threading
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from urllib import parse as urlparse
from urllib import request as urlrequest


UTC = timezone.utc


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def enabled(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name, "1" if default else "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def recipients(name: str) -> list[str]:
    return [value.strip() for value in os.environ.get(name, "").split(",") if value.strip()]


class DeliveryEngine:
    """Provider adapters plus an at-least-once administrative alert outbox."""

    def __init__(self, platform):
        self.platform = platform
        self.sms_provider = os.environ.get("ROOSTERRUN_SMS_PROVIDER", "webhook").strip().lower()
        self.sms_webhook = os.environ.get("ROOSTERRUN_SMS_WEBHOOK_URL", "").strip()
        self.sms_token = os.environ.get("ROOSTERRUN_SMS_WEBHOOK_TOKEN", "").strip()
        self.twilio_sid = os.environ.get("ROOSTERRUN_TWILIO_ACCOUNT_SID", "").strip()
        self.twilio_token = os.environ.get("ROOSTERRUN_TWILIO_AUTH_TOKEN", "").strip()
        self.twilio_from = os.environ.get("ROOSTERRUN_TWILIO_FROM", "").strip()
        self.smtp_host = os.environ.get("ROOSTERRUN_SMTP_HOST", "").strip()
        self.smtp_port = int(os.environ.get("ROOSTERRUN_SMTP_PORT", "587"))
        self.smtp_user = os.environ.get("ROOSTERRUN_SMTP_USERNAME", "").strip()
        self.smtp_password = os.environ.get("ROOSTERRUN_SMTP_PASSWORD", "")
        self.smtp_from = os.environ.get("ROOSTERRUN_SMTP_FROM", "").strip()
        self.smtp_ssl = enabled("ROOSTERRUN_SMTP_SSL")
        self.smtp_starttls = enabled("ROOSTERRUN_SMTP_STARTTLS", default=not self.smtp_ssl)
        self.alert_webhook = os.environ.get("ROOSTERRUN_ALERT_WEBHOOK_URL", "").strip()
        self.alert_webhook_token = os.environ.get("ROOSTERRUN_ALERT_WEBHOOK_TOKEN", "").strip()
        self.admin_sms = recipients("ROOSTERRUN_ALERT_SMS_TO")
        self.admin_email = recipients("ROOSTERRUN_ALERT_EMAIL_TO")
        self.user_sms_notifications = enabled("ROOSTERRUN_USER_SMS_NOTIFICATIONS")
        self._stop_event = threading.Event()
        self._worker: threading.Thread | None = None
        self._initialize()

    @property
    def sms_configured(self) -> bool:
        if self.sms_provider == "twilio":
            return bool(self.twilio_sid and self.twilio_token and self.twilio_from)
        hostname = (urlparse.urlparse(self.sms_webhook).hostname or "").lower()
        return bool(self.sms_webhook.startswith("https://") and not hostname.endswith((".example", ".invalid", ".test")))

    @property
    def email_configured(self) -> bool:
        host = self.smtp_host.lower()
        return bool(
            host and self.smtp_from and (not self.smtp_user or self.smtp_password)
            and not host.endswith((".example", ".invalid", ".test"))
        )

    @property
    def alerts_configured(self) -> bool:
        hostname = (urlparse.urlparse(self.alert_webhook).hostname or "").lower()
        webhook_ready = self.alert_webhook.startswith("https://") and not hostname.endswith((".example", ".invalid", ".test"))
        return bool(webhook_ready or (self.email_configured and self.admin_email) or (self.sms_configured and self.admin_sms))

    def connect(self):
        return self.platform.connect()

    def _initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS notification_deliveries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    notification_id INTEGER NOT NULL REFERENCES notifications(id),
                    channel TEXT NOT NULL CHECK(channel IN ('SMS','EMAIL','WEBHOOK')),
                    destination TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'QUEUED' CHECK(status IN ('QUEUED','SENDING','DELIVERED','FAILED')),
                    attempts INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 6,
                    next_attempt_at TEXT NOT NULL,
                    provider_reference TEXT NOT NULL DEFAULT '',
                    last_error TEXT NOT NULL DEFAULT '',
                    dedupe_key TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    delivered_at TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_notification_deliveries_queue
                ON notification_deliveries(status,next_attempt_at,id);
                """
            )

    def send_sms(self, mobile: str, message: str, *, code: str = "", purpose: str = "") -> str:
        if not self.sms_configured:
            raise RuntimeError("SMS provider is not configured.")
        if self.sms_provider == "twilio":
            endpoint = f"https://api.twilio.com/2010-04-01/Accounts/{self.twilio_sid}/Messages.json"
            data = urlparse.urlencode({"To": mobile, "From": self.twilio_from, "Body": message}).encode("utf-8")
            credentials = base64.b64encode(f"{self.twilio_sid}:{self.twilio_token}".encode()).decode()
            headers = {"Authorization": f"Basic {credentials}", "Content-Type": "application/x-www-form-urlencoded"}
        else:
            endpoint = self.sms_webhook
            data = json.dumps({"mobile": mobile, "message": message, "code": code, "purpose": purpose, "product": "RoosterRun"}).encode("utf-8")
            headers = {"Content-Type": "application/json"}
            if self.sms_token:
                headers["Authorization"] = f"Bearer {self.sms_token}"
        with urlrequest.urlopen(urlrequest.Request(endpoint, data=data, headers=headers, method="POST"), timeout=10) as response:
            if response.status < 200 or response.status >= 300:
                raise RuntimeError(f"SMS provider returned HTTP {response.status}.")
            provider_reference = response.headers.get("X-Request-Id", "")
            if self.sms_provider == "twilio":
                try:
                    provider_reference = json.loads(response.read().decode("utf-8")).get("sid", provider_reference)
                except (ValueError, UnicodeDecodeError):
                    pass
        return provider_reference[:160]

    def send_email(self, destination: str, title: str, message: str) -> str:
        if not self.email_configured:
            raise RuntimeError("Email provider is not configured.")
        mail = EmailMessage()
        mail["From"] = self.smtp_from
        mail["To"] = destination
        mail["Subject"] = title
        mail.set_content(message)
        context = ssl.create_default_context()
        smtp = (
            smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=12, context=context)
            if self.smtp_ssl else smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=12)
        )
        with smtp:
            if self.smtp_starttls:
                smtp.starttls(context=context)
            if self.smtp_user:
                smtp.login(self.smtp_user, self.smtp_password)
            response = smtp.send_message(mail)
        if response:
            raise RuntimeError("SMTP rejected one or more recipients.")
        return mail["Message-ID"] or "accepted"

    def send_webhook(self, title: str, message: str, severity: str) -> str:
        if not self.alert_webhook.startswith("https://"):
            raise RuntimeError("Alert webhook is not configured.")
        body = json.dumps({"product": "RoosterRun", "severity": severity, "title": title, "message": message, "time": utc_now()}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.alert_webhook_token:
            headers["Authorization"] = f"Bearer {self.alert_webhook_token}"
        with urlrequest.urlopen(urlrequest.Request(self.alert_webhook, data=body, headers=headers, method="POST"), timeout=10) as response:
            if response.status < 200 or response.status >= 300:
                raise RuntimeError(f"Alert destination returned HTTP {response.status}.")
            return response.headers.get("X-Request-Id", "accepted")[:160]

    def send_otp(self, mobile: str, code: str, purpose: str) -> None:
        self.send_sms(mobile, f"Your RoosterRun verification code is {code}. It expires in 5 minutes.", code=code, purpose=purpose)

    def queue_notification(self, connection, notification: dict) -> None:
        destinations: list[tuple[str, str]] = []
        if notification["audience"] == "ADMIN" and notification["severity"] in {"WARNING", "CRITICAL"}:
            destinations.extend(("SMS", item) for item in self.admin_sms if self.sms_configured)
            destinations.extend(("EMAIL", item) for item in self.admin_email if self.email_configured)
            if self.alert_webhook.startswith("https://"):
                destinations.append(("WEBHOOK", self.alert_webhook))
        elif notification["audience"] == "USER" and self.user_sms_notifications and self.sms_configured:
            row = connection.execute("SELECT mobile FROM user_wallets WHERE user_id=?", (notification["user_id"],)).fetchone()
            if row and row["mobile"]:
                destinations.append(("SMS", row["mobile"]))
        now = utc_now()
        for channel, destination in destinations:
            dedupe = f"{notification['dedupe_key']}:{channel}:{destination}"
            connection.execute(
                """INSERT OR IGNORE INTO notification_deliveries
                (notification_id,channel,destination,title,message,status,next_attempt_at,dedupe_key,created_at,updated_at)
                VALUES(?,?,?,?,?,'QUEUED',?,?,?,?)""",
                (notification["id"], channel, destination, notification["title"], notification["message"], now, dedupe[:300], now, now),
            )

    def _claim(self):
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            stale = (datetime.now(UTC) - timedelta(minutes=5)).isoformat(timespec="seconds")
            connection.execute("UPDATE notification_deliveries SET status='QUEUED',updated_at=? WHERE status='SENDING' AND updated_at<?", (utc_now(), stale))
            row = connection.execute(
                "SELECT * FROM notification_deliveries WHERE status='QUEUED' AND next_attempt_at<=? ORDER BY id LIMIT 1",
                (utc_now(),),
            ).fetchone()
            if not row:
                return None
            updated = connection.execute(
                "UPDATE notification_deliveries SET status='SENDING',attempts=attempts+1,updated_at=? WHERE id=? AND status='QUEUED'",
                (utc_now(), row["id"]),
            )
            return dict(row) if updated.rowcount == 1 else None

    def deliver_once(self) -> bool:
        delivery = self._claim()
        if not delivery:
            return False
        try:
            if delivery["channel"] == "SMS":
                provider_reference = self.send_sms(delivery["destination"], delivery["message"])
            elif delivery["channel"] == "EMAIL":
                provider_reference = self.send_email(delivery["destination"], delivery["title"], delivery["message"])
            else:
                provider_reference = self.send_webhook(delivery["title"], delivery["message"], "CRITICAL")
            with self.connect() as connection:
                connection.execute(
                    "UPDATE notification_deliveries SET status='DELIVERED',provider_reference=?,last_error='',delivered_at=?,updated_at=? WHERE id=?",
                    (provider_reference, utc_now(), utc_now(), delivery["id"]),
                )
        except Exception as error:
            attempts = int(delivery["attempts"]) + 1
            terminal = attempts >= int(delivery["max_attempts"])
            delay = min(900, 2 ** min(attempts, 9) * 5)
            retry_at = (datetime.now(UTC) + timedelta(seconds=delay)).isoformat(timespec="seconds")
            with self.connect() as connection:
                connection.execute(
                    "UPDATE notification_deliveries SET status=?,last_error=?,next_attempt_at=?,updated_at=? WHERE id=?",
                    ("FAILED" if terminal else "QUEUED", str(error)[:400], retry_at, utc_now(), delivery["id"]),
                )
        return True

    def start_worker(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        self._stop_event.clear()

        def run() -> None:
            while not self._stop_event.is_set():
                worked = False
                try:
                    worked = self.deliver_once()
                except Exception:
                    worked = False
                self._stop_event.wait(0.25 if worked else 2.0)

        self._worker = threading.Thread(target=run, name="roosterrun-delivery-worker", daemon=True)
        self._worker.start()

    def stop_worker(self) -> None:
        self._stop_event.set()
        if self._worker and self._worker.is_alive():
            self._worker.join(timeout=3)

    def health(self) -> dict:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT SUM(CASE WHEN status='QUEUED' THEN 1 ELSE 0 END) AS queued,SUM(CASE WHEN status='FAILED' THEN 1 ELSE 0 END) AS failed FROM notification_deliveries"
            ).fetchone()
        return {
            "sms": "CONFIGURED" if self.sms_configured else "NOT_CONFIGURED",
            "email": "CONFIGURED" if self.email_configured else "NOT_CONFIGURED",
            "alerts": "CONFIGURED" if self.alerts_configured else "NOT_CONFIGURED",
            "worker": bool(self._worker and self._worker.is_alive()),
            "queued": int(row["queued"] or 0),
            "failed": int(row["failed"] or 0),
        }
