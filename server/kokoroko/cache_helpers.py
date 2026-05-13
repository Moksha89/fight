"""
Redis cache helpers for safe read-heavy data.

All functions fall back to DB transparently if Redis is unavailable.
Cache keys use namespaced prefixes for easy invalidation.
"""

import logging

from django.core.cache import cache

logger = logging.getLogger("kokoroko.cache")

# ─── Cache Key Prefixes ─────────────────────────────────────────────────────

KEYS = {
    "settings": "kk:settings:list",
    "banners": "kk:banners:list",
    "highlights": "kk:highlights:list",
    "statuses": "kk:statuses:list",
    "odds_config": "kk:odds:config",
    "zones": "kk:cockfight:zones",
    "boards": "kk:dice:boards",
    "dice_results": "kk:dice:results:{board_id}",
    "cockfight_results": "kk:cockfight:results",
    "admin_sidebar": "kk:admin:sidebar_counts",
    "admin_dashboard": "kk:admin:dashboard:{days}",
}

# ─── TTLs (seconds) ─────────────────────────────────────────────────────────

TTL = {
    "settings": 60,
    "banners": 300,
    "highlights": 300,
    "statuses": 300,
    "odds_config": 15,
    "zones": 60,
    "boards": 60,
    "dice_results": 10,
    "cockfight_results": 10,
    "admin_sidebar": 15,
    "admin_dashboard": 30,
    "payment_options": 30,
}


# ─── Core Helper ─────────────────────────────────────────────────────────────

def get_cached_or_set(cache_key, fetcher, timeout):
    """
    Return cached value or call fetcher() to populate.
    Falls back to fetcher() if Redis is unavailable.
    """
    try:
        value = cache.get(cache_key)
        if value is not None:
            return value
    except Exception:
        logger.warning("cache_get_failed key=%s", cache_key)

    value = fetcher()

    try:
        cache.set(cache_key, value, timeout=timeout)
    except Exception:
        logger.warning("cache_set_failed key=%s", cache_key)

    return value


# ─── Invalidation Helpers ────────────────────────────────────────────────────

def _safe_delete(key):
    try:
        cache.delete(key)
    except Exception:
        logger.warning("cache_delete_failed key=%s", key)


def invalidate_settings():
    _safe_delete(KEYS["settings"])
    logger.info("cache_invalidated key=settings")


def invalidate_banners():
    _safe_delete(KEYS["banners"])
    logger.info("cache_invalidated key=banners")


def invalidate_highlights():
    _safe_delete(KEYS["highlights"])
    logger.info("cache_invalidated key=highlights")


def invalidate_statuses():
    _safe_delete(KEYS["statuses"])
    logger.info("cache_invalidated key=statuses")


def invalidate_odds():
    _safe_delete(KEYS["odds_config"])
    logger.info("cache_invalidated key=odds_config")


def invalidate_zones():
    _safe_delete(KEYS["zones"])
    logger.info("cache_invalidated key=zones")


def invalidate_boards():
    _safe_delete(KEYS["boards"])
    logger.info("cache_invalidated key=boards")


def invalidate_dice_results(board_id=None):
    if board_id:
        _safe_delete(KEYS["dice_results"].format(board_id=board_id))
    else:
        _safe_delete(KEYS["dice_results"].format(board_id="all"))
    logger.info("cache_invalidated key=dice_results board_id=%s", board_id)


def invalidate_cockfight_results():
    _safe_delete(KEYS["cockfight_results"])
    logger.info("cache_invalidated key=cockfight_results")


def invalidate_admin_counts():
    _safe_delete(KEYS["admin_sidebar"])
    for days in (0, 1, 7, 30):
        _safe_delete(KEYS["admin_dashboard"].format(days=days))
    logger.info("cache_invalidated key=admin_counts")


def invalidate_game_cache():
    invalidate_zones()
    invalidate_boards()
    invalidate_dice_results()
    invalidate_cockfight_results()


def invalidate_all():
    invalidate_settings()
    invalidate_banners()
    invalidate_highlights()
    invalidate_statuses()
    invalidate_odds()
    invalidate_game_cache()
    invalidate_admin_counts()
    logger.info("cache_invalidated key=ALL")
