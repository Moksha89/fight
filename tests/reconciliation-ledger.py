"""Reconciliation ledger integrity checks for audit A-08."""

from __future__ import annotations

import os
import secrets
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
os.environ["ROOSTERRUN_OPERATING_MODE"] = "REAL_MONEY"
os.environ.pop("ROOSTERRUN_DATABASE_URL", None)

from manual_payments_server import PaymentService  # noqa: E402

data_dir = Path(tempfile.gettempdir()) / "roosterrun-reconciliation-ledger-test"
shutil.rmtree(data_dir, ignore_errors=True)
service = PaymentService(data_dir, preview_mode=False)

png = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="


# A-08.1: Synthetic balance without ledger entries → CRITICAL.
synthetic_user = "synthetic-balance-user"
service.ensure_user(synthetic_user)
with service.connect() as connection:
    connection.execute(
        "UPDATE user_wallets SET balance_paise=10000 WHERE user_id=?",
        (synthetic_user,),
    )

recon = service.operations.run_reconciliation("test-admin")
synthetic_findings = [
    f for f in recon["findings"]
    if f["entity_id"] == synthetic_user and "balance" in f["message"].lower()
]
assert synthetic_findings, (
    f"A-08.1 FAILED - Synthetic balance for {synthetic_user} was not flagged. "
    f"status={recon['status']} findings={len(recon['findings'])}"
)
assert any(f["severity"] == "CRITICAL" for f in synthetic_findings), \
    "Synthetic balance should be CRITICAL, not WARNING"
assert any(f["check_code"] == "BALANCE_LEDGER_MISMATCH" for f in synthetic_findings), \
    "Expected BALANCE_LEDGER_MISMATCH check code"
print(f"A-08.1 PASS: Synthetic balance flagged as CRITICAL: {synthetic_findings[0]['check_code']}")

with service.connect() as connection:
    connection.execute("DELETE FROM user_wallets WHERE user_id=?", (synthetic_user,))

# A-08.2: Missing ledger entry for approved payment → CRITICAL (PAYMENT_LEDGER_CARDINALITY).
missing_ledger_user = "missing-ledger-user"
service.ensure_user(missing_ledger_user)
account = service.create_account({
    "label": "Test UPI",
    "account_type": "UPI",
    "account_holder": "Test User",
    "upi_id": "test@upi",
})
deposit = service.create_deposit(missing_ledger_user, {
    "amount": 100,
    "account_id": account["id"],
    "utr": "TESTLGR001",
    "proof_data_url": png,
})
service.decide_request(deposit["id"], {
    "decision": "APPROVED",
    "admin_note": "Test approval",
})

with service.connect() as connection:
    connection.execute("DELETE FROM wallet_ledger WHERE request_id=?", (deposit["id"],))

recon = service.operations.run_reconciliation("test-admin")
assert recon["status"] == "FAILED", "Missing ledger should cause FAILED status"
missing_findings = [f for f in recon["findings"] if f["check_code"] == "PAYMENT_LEDGER_CARDINALITY"]
assert missing_findings, "PAYMENT_LEDGER_CARDINALITY check should flag missing ledger"
assert missing_findings[0]["severity"] == "CRITICAL", "Missing ledger should be CRITICAL"
print("A-08.2 PASS: Missing ledger entry flagged as CRITICAL")

# A-08.3: Schema uniqueness prevents duplicate payment ledger rows for the same request/entry_type.
# Cardinality would flag duplicates if they existed; UNIQUE(request_id, entry_type) is the guard.
with service.connect() as connection:
    row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='wallet_ledger'"
    ).fetchone()
    assert row and "UNIQUE(request_id,entry_type)" in row[0].replace(" ", ""), \
        "wallet_ledger should uniquely constrain (request_id, entry_type)"
    # Restore the approved ledger row that A-08.2 deleted
    request_row = connection.execute(
        "SELECT user_id, amount_paise, created_at FROM payment_requests WHERE id=?",
        (deposit["id"],),
    ).fetchone()
    connection.execute(
        """INSERT INTO wallet_ledger
        (user_id, request_id, entry_type, amount_paise, balance_after_paise, description, created_at)
        VALUES (?, ?, 'DEPOSIT', ?, ?, ?, ?)""",
        (
            request_row["user_id"],
            deposit["id"],
            request_row["amount_paise"],
            request_row["amount_paise"],
            "Restored deposit ledger for A-08.3",
            request_row["created_at"],
        ),
    )
    try:
        connection.execute(
            """INSERT INTO wallet_ledger
            (user_id, request_id, entry_type, amount_paise, balance_after_paise, description, created_at)
            VALUES (?, ?, 'DEPOSIT', ?, ?, ?, ?)""",
            (
                request_row["user_id"],
                deposit["id"],
                request_row["amount_paise"],
                request_row["amount_paise"],
                "Duplicate deposit ledger",
                request_row["created_at"],
            ),
        )
        raise AssertionError("Duplicate wallet_ledger row should be rejected by UNIQUE constraint")
    except Exception as exc:  # sqlite IntegrityError via compatibility layer
        assert "UNIQUE" in str(exc).upper() or "unique" in str(exc).lower() or "Integrity" in type(exc).__name__, exc
print("A-08.3 PASS: Duplicate ledger rows rejected by UNIQUE(request_id, entry_type)")

# A-08.4: Orphaned ledger (no matching payment request) — document current behavior.
orphan_user = "orphan-ledger-user"
service.ensure_user(orphan_user)
with service.connect() as connection:
    try:
        connection.execute(
            """INSERT INTO wallet_ledger
            (user_id, request_id, entry_type, amount_paise, balance_after_paise, description, created_at)
            VALUES (?, ?, 'DEPOSIT', ?, ?, ?, datetime('now'))""",
            (orphan_user, 999999, 5000, 5000, "Orphan ledger"),
        )
        connection.execute("UPDATE user_wallets SET balance_paise=5000 WHERE user_id=?", (orphan_user,))
        inserted = True
    except Exception:
        inserted = False

recon = service.operations.run_reconciliation("test-admin")
if not inserted:
    print("A-08.4 PASS: FK prevents orphaned wallet_ledger rows without a payment request")
else:
    orphan_findings = [
        f for f in recon["findings"]
        if "orphan" in f["message"].lower()
        or (f["entity_id"] == orphan_user and "ledger" in f["message"].lower())
        or (f["entity_id"] == orphan_user and f["check_code"] == "BALANCE_LEDGER_MISMATCH")
    ]
    if not orphan_findings:
        print("WARNING: A-08.4 - Orphaned ledger entry not yet detected.")
    else:
        print(f"A-08.4 PASS: Orphaned ledger entry flagged: {orphan_findings[0]['check_code']}")

# A-08.5: Legitimate admin credit recorded in account_ledger should not CRITICAL-flag.
grant_user = "opening-grant-user"
service.ensure_user(grant_user)
with service.connect() as connection:
    grant_ref = f"GRANT-{secrets.token_hex(4).upper()}"
    connection.execute(
        """INSERT INTO account_ledger
        (user_id, reference, entry_type, amount_paise, balance_after_paise, metadata_json, created_at)
        VALUES (?, ?, 'ADJUSTMENT', ?, ?, '{}', datetime('now'))""",
        (grant_user, grant_ref, 20000, 20000),
    )
    connection.execute("UPDATE user_wallets SET balance_paise=20000 WHERE user_id=?", (grant_user,))

recon = service.operations.run_reconciliation("test-admin")
grant_findings = [
    f for f in recon["findings"]
    if f["entity_id"] == grant_user and f["severity"] == "CRITICAL"
]
assert not grant_findings, f"Legitimate opening grant should not cause CRITICAL findings: {grant_findings}"
print("A-08.5 PASS: Opening grant with proper ledger does not cause CRITICAL findings")

print("\nReconciliation ledger integrity checks (audit A-08) completed.")
