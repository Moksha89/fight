"""Admin game categories: fixed China 24/7 toggle, custom categories, per-game visibility, player filtering."""

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

from china_feed_engine import ChinaFeedEngine  # noqa: E402
from manual_payments_server import CHINA_CATEGORY_SLUG, PaymentService  # noqa: E402

data_dir = Path(tempfile.gettempdir()) / "roosterrun-game-categories-test"
shutil.rmtree(data_dir, ignore_errors=True)
service = PaymentService(data_dir, preview_mode=False)

FEED = {"info": None, "history": {"success": True, "resultData": {"list": []}}}


def fake_fetch(url: str, timeout: int) -> dict:
    return FEED["history"] if "history" in url else FEED["info"]


feed = ChinaFeedEngine(service, fetcher=fake_fetch)
service.china_feed = feed


def stamp(minutes: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M")


def manual_game(title: str, **extra: object) -> dict:
    payload = {
        "title": title, "arena": "Test Arena", "status": "SCHEDULED", "stream_type": "VIDEO",
        "stream_url": "https://cdn.example.test/replay.mp4", "team_a_name": "Red", "team_b_name": "Blue",
        "team_a_odds": 1.9, "draw_odds": 6, "team_b_odds": 1.9,
        "betting_opens_at": stamp(5), "betting_closes_at": stamp(30), "scheduled_at": stamp(35),
    }
    payload.update(extra)
    return service.admin_save_game(payload)


def visible_ids() -> set[int]:
    return {game["id"] for game in service.public_site_config()["games"]}


# China 24/7 is a protected built-in category, off until the feed is enabled.
categories = service.admin_game_categories()
china = next(item for item in categories if item["slug"] == CHINA_CATEGORY_SLUG)
assert china["builtin"] and china["visible"] is False and china["kind"] == "CHINA_FEED"
try:
    service.admin_delete_game_category(china["id"])
    raise AssertionError("built-in category must not be deletable")
except ValueError:
    pass

# Turning the China category on enables the feed; off cancels and hides it.
service.admin_save_game_category({"visible": True}, china["id"])
assert feed.settings()["enabled"] is True
FEED["info"] = {"success": True, "resultData": {"id": 501, "taskNum": "7", "winTeam": 0, "allowBetting": True,
                                                 "liveUrl": "https://live.example.test/501.html", "lastIssueInfo": {}}}
feed.poll_once()
china_game = feed.current()["match"]
assert china_game["category_slug"] == CHINA_CATEGORY_SLUG and china_game["visible"] is True
assert china_game["id"] in visible_ids()
site = service.public_site_config()
assert any(item["slug"] == CHINA_CATEGORY_SLUG for item in site["categories"])

# Manual games cannot be filed under the automatic China category.
try:
    manual_game("Sneaky China", category_slug=CHINA_CATEGORY_SLUG)
    raise AssertionError("manual games must not join the China feed category")
except ValueError:
    pass

# Admin creates a custom category with a prerecorded-video game and a live-stream game.
custom = service.admin_save_game_category({"name": "Manila Arena", "description": "Weekend derby"})
assert custom["slug"] == "manila-arena" and custom["visible"] is True and custom["builtin"] is False
try:
    service.admin_save_game_category({"name": "Manila Arena"})
    raise AssertionError("duplicate category names must be rejected")
except ValueError:
    pass
try:
    manual_game("Orphan", category_slug="does-not-exist")
    raise AssertionError("unknown category must be rejected")
except ValueError:
    pass

replay = manual_game("Derby replay", category_slug=custom["slug"])
live = manual_game("Derby live", category_slug=custom["slug"], stream_type="HLS", stream_url="https://cdn.example.test/live.m3u8")
assert replay["category_slug"] == custom["slug"] and replay["visible"] is True and replay["stream_type"] == "VIDEO"
assert live["stream_type"] == "HLS"
assert {replay["id"], live["id"]} <= visible_ids()
assert next(item for item in service.admin_game_categories() if item["id"] == custom["id"])["game_count"] == 2

# Per-game toggle hides one game only.
hidden = service.admin_set_game_visibility(replay["id"], False)
assert hidden["visible"] is False
assert replay["id"] not in visible_ids() and live["id"] in visible_ids()
service.admin_set_game_visibility(replay["id"], True)
assert replay["id"] in visible_ids()

# Category toggle hides every game in it, and the category disappears from the player config.
service.admin_save_game_category({"visible": False}, custom["id"])
assert not ({replay["id"], live["id"]} & visible_ids())
assert all(item["slug"] != custom["slug"] for item in service.public_site_config()["categories"])
service.admin_save_game_category({"visible": True, "name": "Manila Derby"}, custom["id"])
assert {replay["id"], live["id"]} <= visible_ids()
assert service.admin_game_categories()[-1]["name"] in {"Manila Derby", "China 24/7"}

# Hidden games refuse bets even if betting is open.
user = "category-player"
service.ensure_user(user)
with service.connect() as connection:
    connection.execute("UPDATE user_wallets SET balance_paise=100000 WHERE user_id=?", (user,))
quote = service.cockfight.quote_bet(user, {"game_id": china_game["id"], "outcome": "RED", "stake": 100})
assert quote["quote_id"]
service.admin_set_game_visibility(china_game["id"], False)
try:
    service.cockfight.quote_bet(user, {"game_id": china_game["id"], "outcome": "RED", "stake": 100})
    raise AssertionError("hidden game must refuse quotes")
except ValueError:
    pass
service.admin_set_game_visibility(china_game["id"], True)

# A hidden featured game is never the public featured selection.
service.admin_save_game({"featured": True}, replay["id"])
service.admin_set_game_visibility(replay["id"], False)
featured = service.public_site_config()["featured_game"]
assert featured is None or featured["id"] != replay["id"]

# Deleting a custom category keeps its games but uncategorises them.
service.admin_delete_game_category(custom["id"])
assert all(item["slug"] != custom["slug"] for item in service.admin_game_categories())
assert next(g for g in service.admin_games() if g["id"] == live["id"])["category_slug"] == ""

# Switching China 24/7 off cancels the mirrored fight and hides the category.
service.admin_save_game_category({"visible": False}, china["id"])
assert feed.settings()["enabled"] is False
assert all(item["slug"] != CHINA_CATEGORY_SLUG for item in service.public_site_config()["categories"])
assert china_game["id"] not in visible_ids()

print("Game category, China 24/7 toggle, per-game visibility, and player filtering checks passed.")
