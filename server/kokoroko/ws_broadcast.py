"""
Broadcast utilities for WebSocket events.

Call these from views, tasks, or signals to push real-time updates.
"""

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone


def broadcast_wallet_update(user_id, balance, bonus_debt=0):
    """
    Push wallet balance update to a specific user.
    Called automatically by wallet post_save signal,
    but can also be triggered manually for immediate feedback.
    """
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"user_{user_id}_wallet",
        {
            "type": "send_wallet_update",
            "balance": str(balance),
            "bonusDebt": str(bonus_debt),
            "updated_at": timezone.now().isoformat(),
        }
    )


def broadcast_notification(user_id, notification_data):
    """
    Push a new notification to a specific user's notification channel.
    Called from notifications.create_notification().
    """
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"notifications_{user_id}",
        {
            "type": "send_notification",
            "notification": notification_data,
        }
    )


def broadcast_notification_count(user_id, count):
    """Push updated unread notification count."""
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"notifications_{user_id}",
        {
            "type": "send_notification_update",
            "count": count,
        }
    )


def broadcast_dice_timer_sync():
    """
    Broadcast current timer state for all active dice matches.
    Called from manage_virtual_dice_rounds task every 5 seconds.
    """
    from dicePlayManager.models import Board, DicePlayMatch
    import datetime

    now = timezone.now()
    timers = []

    active_matches = DicePlayMatch.objects.filter(
        match_type="V",
        board__is_active=True,
        board__is_virtual=True,
    ).exclude(virtual_phase="done").select_related("board")

    for match in active_matches:
        phase = match.virtual_phase or "betting"
        phase_start = match.phase_started_at or match.liveDate or match.created_at

        if phase == "betting":
            duration = match.board.virtual_betting_seconds or 120
        elif phase == "shuffling":
            duration = match.board.virtual_shuffle_seconds or 30
        elif phase == "result":
            duration = match.board.virtual_result_seconds or 15
        elif phase == "betting_closed":
            duration = 3
        elif phase == "settlement":
            duration = 5
        else:
            duration = 0

        elapsed = (now - phase_start).total_seconds() if phase_start else 0
        remaining = max(0, duration - elapsed)

        timers.append({
            "match_id": match.id,
            "board_id": match.board_id,
            "game_number": match.daily_match_number,
            "phase": phase,
            "phase_duration": duration,
            "elapsed": round(elapsed, 1),
            "remaining": round(remaining, 1),
            "phase_started_at": phase_start.isoformat() if phase_start else None,
            "phase_ends_at": (phase_start + datetime.timedelta(seconds=duration)).isoformat() if phase_start else None,
        })

    data = {
        "server_time": now.isoformat(),
        "timers": timers,
    }

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "dice_timer",
        {
            "type": "send_timer_sync",
            "data": data,
        }
    )


def broadcast_dice_phase_change(match_id, board_id, game_number, new_phase, phase_duration, phase_started_at):
    """
    Broadcast a phase change event for a specific dice match.
    Called when phase transitions occur in tasks.py.
    """
    channel_layer = get_channel_layer()
    import datetime

    phase_ends_at = None
    if phase_started_at and phase_duration > 0:
        phase_ends_at = (phase_started_at + datetime.timedelta(seconds=phase_duration)).isoformat()

    async_to_sync(channel_layer.group_send)(
        "dice_timer",
        {
            "type": "send_phase_change",
            "data": {
                "match_id": match_id,
                "board_id": board_id,
                "game_number": game_number,
                "phase": new_phase,
                "phase_duration": phase_duration,
                "phase_started_at": phase_started_at.isoformat() if phase_started_at else None,
                "phase_ends_at": phase_ends_at,
                "server_time": timezone.now().isoformat(),
            }
        }
    )
