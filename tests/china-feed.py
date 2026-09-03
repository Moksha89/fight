"""China 24/7 feed engine: mirroring, lifecycle, settlement, recovery, failure handling."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
os.environ["ROOSTERRUN_OPERATING_MODE"] = "REAL_MONEY"
os.environ.pop("ROOSTERRUN_DATABASE_URL", None)

from china_feed_engine import ChinaFeedEngine, FeedError  # noqa: E402
from manual_payments_server import PaymentService  # noqa: E402

data_dir = Path(tempfile.gettempdir()) / "roosterrun-china-feed-test"
shutil.rmtree(data_dir, ignore_errors=True)
service = PaymentService(data_dir, preview_mode=False)

FEED = {"info": None, "history": {"success": True, "resultData": {"list": []}}, "fail": False, "calls": 0}


def fake_fetch(url: str, timeout: int) -> dict:
    FEED["calls"] += 1
    if FEED["fail"]:
        raise FeedError("simulated outage")
    return FEED["history"] if "history" in url else FEED["info"]


def info(ref_id: int, task: str, allow: bool, win: int = 0, last: dict | None = None) -> dict:
    return {"success": True, "resultData": {
        "id": ref_id, "taskNum": task, "leftTeamName": "MERON", "rightTeamName": "WALA", "midTeamName": "TIE",
        "winTeam": win, "allowBetting": allow, "liveUrl": f"https://live.example.test/{ref_id}.html",
        "lastIssueInfo": last or {},
    }}


feed = ChinaFeedEngine(service, fetcher=fake_fetch)
service.china_feed = feed

# Disabled by default: nothing happens.
assert feed.poll_once() == {"skipped": "disabled"}
assert FEED["calls"] == 0

settings = feed.update_settings({"enabled": True, "team_a_odds": 1.9, "draw_odds": 6.5, "team_b_odds": 1.8})
assert settings["enabled"] and settings["team_a_odds"] == 1.9

# Match 100 appears with betting open.
FEED["info"] = info(1001, "100", True)
tick = feed.poll_once()
assert any(action.startswith("opened 1001") for action in tick["actions"]), tick
current = feed.current()
game = current["match"]
assert game["status"] == "BETTING_OPEN" and game["source"] == "CHINA_FEED" and game["match_number"] == "100"
assert game["stream_type"] == "IFRAME" and game["stream_url"].endswith("/1001.html")
assert game["featured"] is True and game["team_a_odds"] == 1.9
odds = service.cockfight.current_odds(game["id"])
assert odds["market_status"] == "OPEN" and odds["team_a_odds"] == 1.9
site = service.public_site_config()
assert site["featured_game"]["id"] == game["id"] and site["china_feed"]["allow_betting"] is True

# Player places a bet on Meron through the normal quote flow.
user = "china-player"
service.ensure_user(user)
with service.connect() as connection:
    connection.execute("UPDATE user_wallets SET balance_paise=100000 WHERE user_id=?", (user,))
quote = service.cockfight.quote_bet(user, {"game_id": game["id"], "outcome": "RED", "stake": 500})
bet = service.cockfight.place_bet(user, {"quote_id": quote["quote_id"]})
assert bet["status"] == "pending", bet

# Upstream closes betting: market suspends and match goes live.
FEED["info"] = info(1001, "100", False)
tick = feed.poll_once()
assert "betting closed" in tick["actions"], tick
game = feed.current()["match"]
assert game["status"] == "LIVE"
assert service.cockfight.current_odds(game["id"])["market_status"] == "SUSPENDED"
try:
    service.cockfight.quote_bet(user, {"game_id": game["id"], "outcome": "RED", "stake": 100})
except Exception as error:  # noqa: BLE001
    assert "not" in str(error).lower() or "closed" in str(error).lower() or "suspend" in str(error).lower(), error
else:
    raise AssertionError("Quotes must be refused once upstream betting closes")

# Next match arrives, carrying the previous result (Meron won) in lastIssueInfo.
FEED["info"] = info(1002, "101", True, last={"id": 1001, "taskNum": "100", "winTeam": 1})
tick = feed.poll_once()
assert "settled 1001" in tick["actions"], tick
with service.connect() as connection:
    settled = connection.execute("SELECT status,result FROM admin_games WHERE id=?", (game["id"],)).fetchone()
    balance = connection.execute("SELECT balance_paise FROM user_wallets WHERE user_id=?", (user,)).fetchone()["balance_paise"]
    others_featured = connection.execute("SELECT COUNT(*) FROM admin_games WHERE featured=1").fetchone()[0]
assert settled["status"] == "SETTLED" and settled["result"] == "RED"
assert balance == 100000 - 50000 + int(50000 * 1.9), balance
assert others_featured == 1
history = service.cockfight.history(5)
assert history[0]["matchNumber"] == "100" and history[0]["winTeam"] == 1 and history[0]["source"] == "CHINA_FEED"
new_game = feed.current()["match"]
assert new_game["status"] == "BETTING_OPEN" and new_game["match_number"] == "101"

# Repeated identical poll is idempotent.
before = service.cockfight.events(0)
tick = feed.poll_once()
assert tick["actions"] == [], tick
assert len(service.cockfight.events(0)) == len(before)

# Upstream outage: the market is suspended after N failures, never crashes.
FEED["fail"] = True
for _ in range(feed.settings()["suspend_after_failures"]):
    result = feed.poll_once()
assert result["market_suspended"] is True and result["consecutive_failures"] == feed.settings()["suspend_after_failures"]
assert feed.current()["match"]["status"] == "BETTING_CLOSED"
assert feed.health()["status"] == "attention"
FEED["fail"] = False

# Feed skips straight to match 103 (we never saw 1002's result live): history recovery settles it.
FEED["history"] = {"success": True, "resultData": {"list": [{"id": 1002, "taskNum": "101", "winTeam": 3}, {"id": 1001, "winTeam": 1}]}}
FEED["info"] = info(1003, "103", False)
tick = feed.poll_once()
with service.connect() as connection:
    recovered = connection.execute("SELECT status,result FROM admin_games WHERE id=?", (new_game["id"],)).fetchone()
    feed_row = connection.execute("SELECT win_team,result_source FROM china_feed_matches WHERE ref_id='1002'").fetchone()
assert recovered["status"] == "SETTLED" and recovered["result"] == "DRAW", dict(recovered)
assert feed_row["win_team"] == 3 and feed_row["result_source"] == "HISTORY"
live_game = feed.current()["match"]
assert live_game["status"] == "LIVE" and live_game["match_number"] == "103"

# Cancelled upstream fight refunds stakes.
FEED["info"] = info(1003, "103", False, win=4)
feed.poll_once()
with service.connect() as connection:
    cancelled = connection.execute("SELECT status,result FROM admin_games WHERE id=?", (live_game["id"],)).fetchone()
assert cancelled["status"] == "SETTLED" and cancelled["result"] == "CANCELLED", dict(cancelled)

# Stream override replaces the upstream URL.
feed.update_settings({"stream_url_override": "https://cdn.example.test/override.html"})
FEED["info"] = info(1004, "104", True)
feed.poll_once()
assert feed.current()["match"]["stream_url"] == "https://cdn.example.test/override.html"

# Disabling the feed cancels/refunds the open match and clears state.
feed.update_settings({"enabled": False})
state = feed.state()
assert state["current_ref_id"] == "" and state["current_game_id"] is None
with service.connect() as connection:
    last = connection.execute("SELECT status,result FROM admin_games WHERE external_ref='1004'").fetchone()
assert last["result"] == "CANCELLED" and last["status"] == "SETTLED", dict(last)

# Validation.
for bad in ({"poll_seconds": 1}, {"team_a_odds": 0.5}, {"info_url": "ftp://x"}, {"arena": ""}):
    try:
        feed.update_settings(bad)
    except ValueError:
        pass
    else:
        raise AssertionError(f"Expected rejection for {bad}")

admin = feed.admin_view()
assert len(admin["recent_matches"]) == 4 and admin["settings"]["enabled"] is False
print("China 24/7 feed mirroring, lifecycle, settlement, recovery, outage suspension, and settings checks passed.")
