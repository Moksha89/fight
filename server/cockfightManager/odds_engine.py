"""
Odds Engine — computes Meron/Wala/Draw odds based on active system.

Four systems:
1. Manual       — admin sets min/max ratios directly
2. Dynamic      — auto-adjusts after every match based on rolling win rates
3. Pool-Based   — parimutuel: odds derived from bet pool distribution per match
4. Rebalance    — auto-adjusts every N matches with fixed house edge
"""

from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone


def get_odds_config():
    from cockfightManager.models import OddsConfig
    config, _ = OddsConfig.objects.get_or_create(id=1)
    return config


def get_current_odds():
    """Return current odds dict for the active system."""
    config = get_odds_config()

    if config.odds_system == 'manual':
        return {
            'meron_min': config.manual_meron_min,
            'meron_max': config.manual_meron_max,
            'wala_min': config.manual_wala_min,
            'wala_max': config.manual_wala_max,
            'draw_min': config.manual_draw_min,
            'draw_max': config.manual_draw_max,
            'system': 'manual',
        }
    else:
        return {
            'meron_min': config.current_meron_min,
            'meron_max': config.current_meron_max,
            'wala_min': config.current_wala_min,
            'wala_max': config.current_wala_max,
            'draw_min': config.current_draw_min,
            'draw_max': config.current_draw_max,
            'system': config.odds_system,
        }


def _clamp(value, lo, hi):
    return max(lo, min(hi, value))


def recalculate_dynamic_odds(config=None):
    """
    Dynamic Win-Rate Odds:
    - Look at last N matches
    - Calculate win percentage for each team
    - Set max_ratio = (1 / win_rate) * (1 - house_edge) - 1
    - Min ratio = floor value
    """
    from cockfightManager.models import CockfightAutoMatch
    if config is None:
        config = get_odds_config()

    lookback = config.dynamic_lookback
    house_edge = float(config.dynamic_house_edge)
    floor = config.dynamic_min_ratio
    cap = config.dynamic_max_ratio

    matches = CockfightAutoMatch.objects.filter(
        processed=True, winTeam__in=[1, 2, 3]
    ).order_by('-id')[:lookback]

    total = len(matches)
    if total < 5:
        return  # not enough data

    meron_wins = sum(1 for m in matches if m.winTeam == 1)
    wala_wins = sum(1 for m in matches if m.winTeam == 2)
    draw_count = sum(1 for m in matches if m.winTeam == 3)

    meron_pct = meron_wins / total if total else 0.5
    wala_pct = wala_wins / total if total else 0.5
    draw_pct_val = draw_count / total if total else 0.04

    # Fair odds = 1/probability, then apply house edge
    # max_ratio = (1/win_rate) * (1 - house_edge) - 1
    if meron_pct > 0:
        meron_max = Decimal(str(round((1 / meron_pct) * (1 - house_edge) - 1, 2)))
    else:
        meron_max = cap

    if wala_pct > 0:
        wala_max = Decimal(str(round((1 / wala_pct) * (1 - house_edge) - 1, 2)))
    else:
        wala_max = cap

    config.current_meron_min = floor
    config.current_meron_max = _clamp(meron_max, floor, cap)
    config.current_wala_min = floor
    config.current_wala_max = _clamp(wala_max, floor, cap)
    config.current_draw_min = config.dynamic_draw_min
    config.current_draw_max = config.dynamic_draw_max

    config.meron_win_pct = Decimal(str(round(meron_pct * 100, 2)))
    config.wala_win_pct = Decimal(str(round(wala_pct * 100, 2)))
    config.draw_pct = Decimal(str(round(draw_pct_val * 100, 2)))
    config.last_recalculated = timezone.now()
    config.save()


def get_pool_odds_for_match(match_id):
    """
    Pool-Based (Parimutuel) Odds:
    - Total pool = all bets on this match
    - Odds for team = (total_pool / team_pool) * (1 - house_cut) - 1
    - Returns live odds for the CURRENT match
    """
    from cockfightManager.models import CockfightMatchBet
    config = get_odds_config()
    house_cut = float(config.pool_house_cut)

    bets = CockfightMatchBet.objects.filter(
        matchType='A', matchId=str(match_id)
    )

    total_pool = sum(b.amount for b in bets) or 0
    meron_pool = sum(b.amount for b in bets if b.betTeam == 1) or 0
    wala_pool = sum(b.amount for b in bets if b.betTeam == 2) or 0

    base_ratio = Decimal('0.80')

    if total_pool > 0 and meron_pool > 0:
        meron_ratio = Decimal(str(round(
            (total_pool / meron_pool) * (1 - house_cut) - 1, 2
        )))
    else:
        meron_ratio = base_ratio

    if total_pool > 0 and wala_pool > 0:
        wala_ratio = Decimal(str(round(
            (total_pool / wala_pool) * (1 - house_cut) - 1, 2
        )))
    else:
        wala_ratio = base_ratio

    MIN_POOL = Decimal('0.10')
    MAX_POOL = Decimal('5.00')

    return {
        'meron_min': _clamp(meron_ratio, MIN_POOL, MAX_POOL),
        'meron_max': _clamp(meron_ratio, MIN_POOL, MAX_POOL),
        'wala_min': _clamp(wala_ratio, MIN_POOL, MAX_POOL),
        'wala_max': _clamp(wala_ratio, MIN_POOL, MAX_POOL),
        'draw_min': config.pool_draw_min,
        'draw_max': config.pool_draw_max,
        'total_pool': total_pool,
        'meron_pool': meron_pool,
        'wala_pool': wala_pool,
        'system': 'pool',
    }


def recalculate_rebalance_odds(config=None):
    """
    Fixed Rebalance Odds:
    - Same formula as Dynamic, but only runs every N matches
    - Provides more stable odds (less fluctuation)
    """
    from cockfightManager.models import CockfightAutoMatch
    if config is None:
        config = get_odds_config()

    config.matches_since_rebalance += 1

    if config.matches_since_rebalance < config.rebalance_interval:
        config.save()
        return  # not time yet

    # Time to rebalance
    lookback = config.rebalance_lookback
    house_edge = float(config.rebalance_house_edge)
    floor = config.rebalance_min_ratio
    cap = config.rebalance_max_ratio

    matches = CockfightAutoMatch.objects.filter(
        processed=True, winTeam__in=[1, 2, 3]
    ).order_by('-id')[:lookback]

    total = len(matches)
    if total < 5:
        config.save()
        return

    meron_wins = sum(1 for m in matches if m.winTeam == 1)
    wala_wins = sum(1 for m in matches if m.winTeam == 2)
    draw_count = sum(1 for m in matches if m.winTeam == 3)

    meron_pct = meron_wins / total if total else 0.5
    wala_pct = wala_wins / total if total else 0.5
    draw_pct_val = draw_count / total if total else 0.04

    if meron_pct > 0:
        meron_max = Decimal(str(round((1 / meron_pct) * (1 - house_edge) - 1, 2)))
    else:
        meron_max = cap

    if wala_pct > 0:
        wala_max = Decimal(str(round((1 / wala_pct) * (1 - house_edge) - 1, 2)))
    else:
        wala_max = cap

    config.current_meron_min = floor
    config.current_meron_max = _clamp(meron_max, floor, cap)
    config.current_wala_min = floor
    config.current_wala_max = _clamp(wala_max, floor, cap)
    config.current_draw_min = config.rebalance_draw_min
    config.current_draw_max = config.rebalance_draw_max

    config.meron_win_pct = Decimal(str(round(meron_pct * 100, 2)))
    config.wala_win_pct = Decimal(str(round(wala_pct * 100, 2)))
    config.draw_pct = Decimal(str(round(draw_pct_val * 100, 2)))
    config.matches_since_rebalance = 0
    config.last_recalculated = timezone.now()
    config.save()


def on_match_complete():
    """Called after each auto match completes. Triggers appropriate recalculation."""
    config = get_odds_config()

    if config.odds_system == 'dynamic':
        recalculate_dynamic_odds(config)
    elif config.odds_system == 'rebalance':
        recalculate_rebalance_odds(config)
    # manual and pool don't need post-match recalculation
