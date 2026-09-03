"""Approval-demo operating boundary and demo-credit regression checks."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

os.environ.update(
    {
        "ROOSTERRUN_OPERATING_MODE": "APPROVAL_DEMO",
        "ROOSTERRUN_DEMO_STARTING_BALANCE": "12450",
        "ROOSTERRUN_BOOTSTRAP_ADMIN_USERNAME": "approval-owner",
        "ROOSTERRUN_BOOTSTRAP_ADMIN_PASSWORD": "ApprovalDemoOwner123!",
        "ROOSTERRUN_BOOTSTRAP_ADMIN_NAME": "Approval Owner",
        "ROOSTERRUN_OTP_TEST_MODE": "1",
        "ROOSTERRUN_REQUIRE_STREAMING": "0",
    }
)

from manual_payments_server import PaymentService  # noqa: E402


with tempfile.TemporaryDirectory(prefix="roosterrun-approval-", ignore_cleanup_errors=True) as temporary:
    service = PaymentService(Path(temporary), preview_mode=False)
    assert service.operating_mode == "APPROVAL_DEMO"
    assert service.initial_wallet_balance_paise == 1_245_000
    assert service.compliance.health()["operating_mode"] == "APPROVAL_DEMO"

    challenge = service.auth.register_user(
        {"username": "approval.player", "mobile": "9876543210", "password": "ApprovalPlayer123", "confirmPassword": "ApprovalPlayer123"}
    )
    registered = service.auth.register_user(
        {"challenge_id": challenge["challenge_id"], "otp": challenge["preview_otp"]}
    )
    user_id = registered["user"]["id"]
    assert registered["user"]["wallet_balance"] == 12_450

    with service.connect() as connection:
        grant = connection.execute(
            "SELECT amount_paise,metadata_json FROM account_ledger WHERE user_id=? AND reference=?",
            (user_id, f"DEMO-GRANT-{user_id}"),
        ).fetchone()
        assert grant and grant["amount_paise"] == 1_245_000 and '"non_cash": true' in grant["metadata_json"]
        service.compliance.profile(user_id)
        connection.execute(
            "UPDATE compliance_profiles SET legal_name=?,date_of_birth='1990-01-01',state_code='KA',status='VERIFIED',consent_identity=1,consent_privacy=1,updated_at=? WHERE user_id=?",
            ("Approval Player", "2026-09-02T00:00:00+00:00", user_id),
        )

    service.compliance.assert_allowed(user_id, "BET", 10_000)
    service.compliance.assert_allowed(user_id, "DEPOSIT", 10_000)

    media = service.admin_save_banner(
        {
            "title": "Approval highlight",
            "subtitle": "Operator managed video",
            "placement": "HOME_HIGHLIGHT",
            "image_url": "/static/cockfight-highlights-v1.png",
            "media_url": "https://www.youtube.com/watch?v=abcdefghijk",
            "media_type": "YOUTUBE",
            "duration": "4:12",
            "sort_order": 1,
            "active": True,
        }
    )
    assert media["media_type"] == "YOUTUBE" and media["duration"] == "4:12"
    public = service.public_site_config()
    assert public["operating_mode"] == "APPROVAL_DEMO"
    assert isinstance(public["games"], list)
    assert any(item["id"] == media["id"] for item in public["banners"])

os.environ["ROOSTERRUN_OPERATING_MODE"] = "REAL_MONEY"
real_dir = Path(tempfile.gettempdir()) / "roosterrun-real-money-mode"
shutil.rmtree(real_dir, ignore_errors=True)
real = PaymentService(real_dir, preview_mode=False)
assert real.operating_mode == "REAL_MONEY"
assert real.initial_wallet_balance_paise == 0
assert real.compliance.policy()["operating_mode"] == "REAL_MONEY"
assert "demo credits" not in real.compliance.policy()["legal_notice"].lower()
real.compliance._require_legal_mode("deposit")
with real.connect() as connection:
    assert connection.execute("SELECT COUNT(*) FROM payment_accounts WHERE label='Approval demo UPI'").fetchone()[0] == 0
assert real.public_site_config()["operating_mode"] == "REAL_MONEY"

os.environ["ROOSTERRUN_OPERATING_MODE"] = "BOGUS"
try:
    PaymentService(Path(tempfile.gettempdir()) / "roosterrun-invalid-mode", preview_mode=False)
except RuntimeError as error:
    assert "SOCIAL_PREVIEW, APPROVAL_DEMO, or REAL_MONEY" in str(error)
else:
    raise AssertionError("Unknown operating mode must fail before startup")

print("Approval-demo credits, full workflow boundary, home media, and real-money startup checks passed.")
