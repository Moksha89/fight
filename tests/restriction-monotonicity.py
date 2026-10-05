"""Responsible-play restriction monotonicity: downgrades must be rejected (audit A-01).

A restriction downgrade allows a player to bypass a longer protection. The
compliance engine must reject attempts to replace a permanent exclusion with
a temporary one or to replace a longer duration with a shorter one.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
os.environ["ROOSTERRUN_OPERATING_MODE"] = "REAL_MONEY"
os.environ.pop("ROOSTERRUN_DATABASE_URL", None)

from manual_payments_server import PaymentService  # noqa: E402

data_dir = Path(tempfile.gettempdir()) / "roosterrun-restriction-monotonicity-test"
shutil.rmtree(data_dir, ignore_errors=True)
service = PaymentService(data_dir, preview_mode=False)

user = "monotonicity-player"
service.ensure_user(user)


def timestamp_days_ahead(days: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=days)


# A-01.1: Permanent exclusion cannot be downgraded to 180-day exclusion.
service.compliance.restrict(user, "SELF_EXCLUDE", duration_days=0)
controls = service.compliance.controls(user)
assert controls["permanent_exclusion"] is True, "Permanent exclusion should be set"
assert controls["exclusion_until"] == "", "Permanent exclusion should have empty until"

try:
    service.compliance.restrict(user, "SELF_EXCLUDE", duration_days=180)
    raise AssertionError("Permanent exclusion downgrade to 180 days must be rejected")
except ValueError as error:
    assert "downgrade" in str(error).lower() or "permanent" in str(error).lower(), f"Expected downgrade/permanent error, got: {error}"

controls = service.compliance.controls(user)
assert controls["permanent_exclusion"] is True, "Permanent exclusion must remain permanent after rejection"
assert controls["exclusion_until"] == "", "Permanent exclusion until must remain empty"

# Reset for next test
with service.connect() as connection:
    connection.execute("DELETE FROM responsible_controls WHERE user_id=?", (user,))
    connection.execute("DELETE FROM responsible_events WHERE user_id=?", (user,))

# A-01.2: Longer exclusion (365 days) wins over shorter (180 days).
service.compliance.restrict(user, "SELF_EXCLUDE", duration_days=365)
controls_365 = service.compliance.controls(user)
until_365 = controls_365["exclusion_until"]
assert until_365 != "", "365-day exclusion must have a timestamp"

try:
    service.compliance.restrict(user, "SELF_EXCLUDE", duration_days=180)
    raise AssertionError("365-day exclusion downgrade to 180 days must be rejected")
except ValueError as error:
    assert "downgrade" in str(error).lower() or "longer" in str(error).lower(), f"Expected downgrade/longer error, got: {error}"

controls = service.compliance.controls(user)
assert controls["exclusion_until"] == until_365, "365-day exclusion must remain unchanged"

# Reset for next test
with service.connect() as connection:
    connection.execute("DELETE FROM responsible_controls WHERE user_id=?", (user,))
    connection.execute("DELETE FROM responsible_events WHERE user_id=?", (user,))

# A-01.3: Longer cool-off (30 days) wins over shorter (1 day).
service.compliance.restrict(user, "COOL_OFF", duration_days=30)
controls_30 = service.compliance.controls(user)
until_30 = controls_30["cool_off_until"]
assert until_30 != "", "30-day cool-off must have a timestamp"

try:
    service.compliance.restrict(user, "COOL_OFF", duration_days=1)
    raise AssertionError("30-day cool-off downgrade to 1 day must be rejected")
except ValueError as error:
    assert "downgrade" in str(error).lower() or "longer" in str(error).lower(), f"Expected downgrade/longer error, got: {error}"

controls = service.compliance.controls(user)
assert controls["cool_off_until"] == until_30, "30-day cool-off must remain unchanged"

# Reset for next test
with service.connect() as connection:
    connection.execute("DELETE FROM responsible_controls WHERE user_id=?", (user,))
    connection.execute("DELETE FROM responsible_events WHERE user_id=?", (user,))

# A-01.4: Expired restriction can be renewed with any duration.
# Set a 180-day exclusion that already expired
past = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat(timespec="seconds")
with service.connect() as connection:
    service.compliance._ensure_controls(connection, user)
    connection.execute(
        "UPDATE responsible_controls SET exclusion_until=?, permanent_exclusion=0, updated_at=? WHERE user_id=?",
        (past, past, user)
    )

# An expired exclusion should allow any new restriction (not a downgrade)
service.compliance.restrict(user, "SELF_EXCLUDE", duration_days=180)
controls = service.compliance.controls(user)
assert controls["exclusion_until"] > past, "Expired restriction should be renewed"

# Reset for next test
with service.connect() as connection:
    connection.execute("DELETE FROM responsible_controls WHERE user_id=?", (user,))
    connection.execute("DELETE FROM responsible_events WHERE user_id=?", (user,))

# A-01.5: Concurrent restrictions keep the maximum.
# Set a 7-day cool-off
service.compliance.restrict(user, "COOL_OFF", duration_days=7)
controls_7 = service.compliance.controls(user)
until_7 = controls_7["cool_off_until"]

# Now set a 30-day cool-off (upgrade allowed)
service.compliance.restrict(user, "COOL_OFF", duration_days=30)
controls = service.compliance.controls(user)
assert controls["cool_off_until"] > until_7, "30-day cool-off should replace 7-day"

# Attempting to downgrade back to 7 days should fail
try:
    service.compliance.restrict(user, "COOL_OFF", duration_days=7)
    raise AssertionError("30-day cool-off downgrade to 7 days must be rejected")
except ValueError as error:
    assert "downgrade" in str(error).lower() or "longer" in str(error).lower(), f"Expected downgrade/longer error, got: {error}"

print("Restriction monotonicity (audit A-01) checks completed. NOTE: This test SHOULD FAIL if the unconditional overwrite bug is still present.")
