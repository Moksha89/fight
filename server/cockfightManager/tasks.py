from celery import group
import requests
import json
import subprocess
import os
import signal
from datetime import datetime, timedelta
from celery import shared_task

from decimal import Decimal, ROUND_DOWN

from django.db.models import F
from django.db import transaction
from django.utils import timezone

from apiManager.cockfightManager.serializers import CockfightAutoMatchSerializer
from base.models import Setting
from django.conf import settings
from utility.encryption import decrypt
from wallet.models import WalletHistory
from .models import CockfightAutoMatch, AutoMatchPollingState, CockfightMatch, CockfightMatchBet

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

RECORDING_DIR = '/server/media/match_recordings'


def get_odds_snapshot():
    """Get current odds settings as a JSON dict."""
    odds = {}
    for key in ['R', 'S', 'T', 'U', 'V', 'W']:
        try:
            s = Setting.objects.get(action=key)
            odds[key] = s.actionValue
        except Setting.DoesNotExist:
            odds[key] = ''
    return json.dumps(odds)


from cockfightManager.match_recorder import start_recording, stop_recording, capture_screenshot


def start_match_recording(match):
    """Start video recording of the live stream for this match."""
    if not match.liveUrl:
        match.recordingStatus = 'failed'
        match.save(update_fields=['recordingStatus'])
        return

    rec_info = start_recording(
        match_pk=match.pk,
        match_number=match.matchNumber,
        reference_id=match.referanceId,
        live_url=match.liveUrl
    )

    if rec_info:
        match.recordingFile = f'match_recordings/{rec_info["video_filename"]}'
        match.recordingStatus = 'recording'
    else:
        match.recordingStatus = 'failed'
    match.save(update_fields=['recordingFile', 'recordingStatus'])


def stop_match_recording(match):
    """Stop video recording and capture winning screenshot."""
    video_filename = stop_recording(match.pk)
    screenshot_file = capture_screenshot(match.pk, suffix='win')

    if video_filename:
        match.recordingFile = f'match_recordings/{video_filename}'
        match.recordingStatus = 'completed'
    else:
        match.recordingStatus = 'failed'

    if screenshot_file:
        match.screenshotFile = f'match_recordings/{screenshot_file}'

    update_fields = ['recordingFile', 'recordingStatus', 'screenshotFile']
    match.save(update_fields=update_fields)


# ==========================================================================
# =========== Scheduled Match Management (Pre-Recorded + Live) =============
# ==========================================================================

@shared_task
def manage_scheduled_matches():
    """
    Runs every 10 seconds. Handles:
    1. Pre-recorded matches: auto-open betting 5 min before, auto-close at start,
       auto-go-live at scheduled time
    2. Live RTMP matches: start recording when session goes active
    """
    from cockfightManager.utils import broadcast_manual_match_update
    now = timezone.now()
    changed = False

    # --- Pre-Recorded: Open betting ---
    # Find prerecorded matches where bettingOpensAt <= now and not yet live/betting
    matches_to_open = CockfightMatch.objects.filter(
        match_mode='prerecorded',
        bettingOpensAt__lte=now,
        scheduledStart__gt=now,  # not started yet
        isLive=False,
        isWinnerDeclared=False,
    )
    for match in matches_to_open:
        match.isLive = True
        match.isBettingEnabled = True
        match.bettingOpenedAt = now
        match.save(update_fields=['isLive', 'isBettingEnabled', 'bettingOpenedAt'])
        changed = True

    # --- Pre-Recorded: Close betting + start match ---
    # Find prerecorded matches where scheduledStart <= now and betting still open
    matches_to_start = CockfightMatch.objects.filter(
        match_mode='prerecorded',
        scheduledStart__lte=now,
        isBettingEnabled=True,
        isWinnerDeclared=False,
    )
    for match in matches_to_start:
        match.isBettingEnabled = False
        match.bettingClosedAt = now
        match.save(update_fields=['isBettingEnabled', 'bettingClosedAt'])
        changed = True

    # --- Live RTMP: Check for active sessions, start recording ---
    from .models import LiveSession
    active_sessions = LiveSession.objects.filter(is_active=True, recordingStatus='none')
    for session in active_sessions:
        hls_url = session.hls_url
        session.recordingStatus = 'recording'
        session.save(update_fields=['recordingStatus'])

    if changed:
        try:
            broadcast_manual_match_update()
        except Exception:
            pass

    return f"Checked at {now.isoformat()}"


HISTORY_API_URL = "https://api.cockfightbet.cc/api/cf/game/task/history?pageNum=1&pageSize=10"

API_URL = "https://api.cockfightbet.xyz/api/cf/game/info?gameId=10001"


@shared_task
def poll_auto_match_status():
    from django.db import connection
    with transaction.atomic():
        state = AutoMatchPollingState.objects.select_for_update().filter(id=1).first()
        if not state:
            state = AutoMatchPollingState.objects.create(id=1)
        return _poll_auto_match_inner(state)


def _poll_auto_match_inner(state):

    from base.models import Setting as _Setting
    try:
        _enable_setting = _Setting.objects.get(action="Y")
        _is_enabled = _enable_setting.actionValue.strip().upper() == "Y"
    except _Setting.DoesNotExist:
        _is_enabled = False
    if not _is_enabled:
        state.runningAutoMatchId = None
        state.runningMatchRefId = None
        state.matchNumber = None
        state.isNewMatchUpdated = None
        state.isAcceptingBet = False
        state.liveUrl = None
        state.pastMatchRefId = None
        state.save()
        CockfightAutoMatch.objects.filter(processed=False).update(winTeam=4)
        return "Cockfight match stopped running."

    try:
        response = requests.get(API_URL, timeout=5)
        response.raise_for_status()
        data = response.json()
        latest_match = data['resultData']
        last_match = latest_match.get('lastIssueInfo')
    except Exception as e:
        return f"Failed to fetch data: {e}"

    api_live_url = latest_match.get("liveUrl", "")
    new_match_id = str(latest_match["id"])
    task_num = int(latest_match["taskNum"])
    pastMatchId = str(last_match["id"])
    match_title = f"Match - {task_num} | {datetime.today().strftime('%Y-%m-%d')}"

    try:
        setting_x = Setting.objects.get(action='X')
        if setting_x.actionValue and setting_x.actionValue != 'EMPTY':
            live_url_to_use = decrypt(setting_x.actionValue)
        else:
            live_url_to_use = api_live_url
    except Setting.DoesNotExist:
        live_url_to_use = api_live_url
        setting_x = None

    if state.stampingUrl != api_live_url:
        state.stampingUrl = api_live_url
        state.liveUrl = api_live_url
        state.save()
        if setting_x:
            setting_x.actionValue = 'EMPTY'
            setting_x.save()
    elif state.liveUrl != live_url_to_use:
        state.liveUrl = live_url_to_use
        state.save()

    if not state.runningMatchRefId:
        CockfightAutoMatch.objects.filter(processed=False).update(winTeam=4)
        is_betting = bool(latest_match.get("allowBetting", False))
        runningAutoMatch = CockfightAutoMatch.objects.create(
            matchTitle=match_title,
            referanceId=new_match_id,
            matchNumber=task_num,
            winTeam=0,
            oddsSnapshot=get_odds_snapshot(),
            liveUrl=live_url_to_use,
            bettingOpenedAt=timezone.now() if is_betting else None,
        )
        start_match_recording(runningAutoMatch)
        state.runningMatchRefId = new_match_id
        state.runningAutoMatchId = runningAutoMatch.pk
        state.isNewMatchUpdated = True
        state.liveUrl = live_url_to_use
        state.matchNumber = task_num
        state.pastMatchRefId = pastMatchId
        state.isAcceptingBet = is_betting
        state.save()
        return "Initialized with first match"

    if state.isNewMatchUpdated and last_match and (pastMatchId != state.pastMatchRefId):
        prev_match = CockfightAutoMatch.objects.filter(
            referanceId=str(last_match['id'])).first()
        if prev_match:
            if prev_match.recordingStatus == 'recording':
                stop_match_recording(prev_match)
            if not prev_match.bettingClosedAt:
                prev_match.bettingClosedAt = timezone.now()
                prev_match.save(update_fields=['bettingClosedAt'])
            prev_match.winTeam = last_match.get("winTeam", 0)
            prev_match.save()

            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                "match_result",
                {
                    "type": "send_match_result",
                    "result_type": "auto_match_result",
                    "data": CockfightAutoMatchSerializer(prev_match).data,
                }
            )
        state.pastMatchRefId = pastMatchId
        state.save()

    if state.runningMatchRefId != new_match_id:
        if state.runningAutoMatchId:
            old_match = CockfightAutoMatch.objects.filter(pk=state.runningAutoMatchId).first()
            if old_match and old_match.recordingStatus == 'recording':
                stop_match_recording(old_match)

        is_betting = bool(latest_match.get("allowBetting", False))
        runningAutoMatch = CockfightAutoMatch.objects.create(
            matchTitle=match_title,
            referanceId=new_match_id,
            matchNumber=task_num,
            winTeam=0,
            oddsSnapshot=get_odds_snapshot(),
            liveUrl=live_url_to_use,
            bettingOpenedAt=timezone.now() if is_betting else None,
        )
        start_match_recording(runningAutoMatch)

        state.runningMatchRefId = new_match_id
        state.isNewMatchUpdated = True
        state.runningAutoMatchId = runningAutoMatch.pk
        state.matchNumber = task_num
        state.liveUrl = live_url_to_use
        state.isAcceptingBet = is_betting
        state.save()

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "match_updates",
            {
                "type": "send_accepting_auto_bet_update",
                "data": {
                    "isAcceptingBet": state.isAcceptingBet,
                    "matchNumber": task_num,
                    "matchId": state.runningAutoMatchId,
                    "liveUrl": state.liveUrl,
                },
            }
        )

        return "New match detected and updated"

    isAcceptingBet = bool(latest_match.get("allowBetting", False))
    if state.isNewMatchUpdated and (isAcceptingBet != state.isAcceptingBet):
        state.isAcceptingBet = isAcceptingBet
        state.save()

        if state.runningAutoMatchId:
            current_match = CockfightAutoMatch.objects.filter(pk=state.runningAutoMatchId).first()
            if current_match:
                if isAcceptingBet and not current_match.bettingOpenedAt:
                    current_match.bettingOpenedAt = timezone.now()
                    current_match.save(update_fields=['bettingOpenedAt'])
                elif not isAcceptingBet and not current_match.bettingClosedAt:
                    current_match.bettingClosedAt = timezone.now()
                    current_match.save(update_fields=['bettingClosedAt'])

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "match_updates",
            {
                "type": "send_accepting_auto_bet_update",
                "data": {
                    "isAcceptingBet": isAcceptingBet,
                    "matchNumber": task_num,
                    "matchId": state.runningAutoMatchId,
                    "liveUrl": state.liveUrl,
                },
            }
        )

    return "No new match"


# ==========================================================================
# ============================== Bet Processing ============================
# ==========================================================================

@shared_task
def process_single_winning_bet(bet_id: int):
    try:
        bet = CockfightMatchBet.objects.select_related(
            "customer__wallet").get(id=bet_id)
        wallet = bet.customer.wallet
        base_amount = Decimal(bet.amount)
        ratio_decimal = Decimal(bet.betRatio)
        bonus_amount = (base_amount * ratio_decimal)
        total_credit = base_amount + bonus_amount

        with transaction.atomic():
            wallet.balance = F('balance') + total_credit
            wallet.save()

            WalletHistory.objects.create(
                wallet=wallet,
                transaction_type='F',
                change=total_credit,
                isSuccess=True,
                description=f"Bet win: {base_amount} + {bonus_amount} ({bet.betRatio})"
            )
    except Exception as e:
        return str(e)


@shared_task
def refund_cancelled_bet(bet_id: int):
    try:
        bet = CockfightMatchBet.objects.select_related(
            "customer__wallet").get(id=bet_id)
        wallet = bet.customer.wallet
        refund_amount = Decimal(bet.amount)

        with transaction.atomic():
            wallet.balance = F('balance') + refund_amount
            wallet.save()

            WalletHistory.objects.create(
                wallet=wallet,
                transaction_type='F',
                change=refund_amount,
                isSuccess=True,
                description=f"Match cancelled, bet {refund_amount} refunded"
            )
    except Exception as e:
        return str(e)


@shared_task
def process_cockfight_match_result(match_id: int, matchType: str):
    try:
        if matchType == 'A':
            match = CockfightAutoMatch.objects.get(id=match_id)
        elif matchType == 'M':
            match = CockfightMatch.objects.get(id=match_id)
        else:
            return "Invalid Match Type"

        if match.processed or match.winTeam == 0:
            return "Already processed or unresolved"

        win_team = match.winTeam
        match_ref_id = match.pk
        bets = CockfightMatchBet.objects.filter(
            matchType=matchType, matchId=match_ref_id)

        bets.update(matchWinStatus=win_team)

        ratio_keys = {
            1: 'R',
            2: 'S',
            3: 'T'
        }

        if win_team in ratio_keys:
            winning_bet_ids = bets.filter(
                betTeam=win_team).values_list('id', flat=True)
            task_group = group(process_single_winning_bet.s(
                bet_id) for bet_id in winning_bet_ids)
            task_group.apply_async()

        elif win_team == 4:
            task_group = group(refund_cancelled_bet.s(bet.id) for bet in bets)
            task_group.apply_async()

        match.processed = True
        match.save()

        # Recalculate odds after match completes (for auto matches)
        if matchType == 'A':
            try:
                from cockfightManager.odds_engine import on_match_complete
                on_match_complete()
            except Exception as oe:
                logger.error(f"Odds recalculation error: {oe}")

        return "Processing triggered"
    except CockfightAutoMatch.DoesNotExist:
        return "Match not found"
    except Exception as e:
        return str(e)
