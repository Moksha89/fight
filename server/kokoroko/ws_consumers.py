"""
WebSocket consumers for real-time platform features.

- NotificationConsumer: Real-time user notifications
- DiceTimerConsumer: Server-authoritative timer sync for dice rounds
"""

import json
import datetime
from channels.db import database_sync_to_async
from django.utils import timezone
from kokoroko.ws_protection import ProtectedConsumer


class NotificationConsumer(ProtectedConsumer):
    """
    Real-time notification delivery.
    User subscribes to their personal notification channel.
    Server pushes notifications as they're created.
    """

    async def on_connect(self):
        self.user = self.scope["user"]
        self.group_name = f"notifications_{self.user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)

        # Send unread count on connect
        count = await self.get_unread_count()
        await self.send(text_data=json.dumps({
            "type": "notification_init",
            "unread_count": count,
        }))

    async def on_disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def on_receive(self, text_data=None, bytes_data=None):
        """Handle client messages (e.g., mark as read)."""
        if not text_data:
            return
        try:
            data = json.loads(text_data)
            action = data.get("action")
            if action == "mark_read":
                notification_id = data.get("notification_id")
                if notification_id:
                    await self.mark_notification_read(notification_id)
            elif action == "mark_all_read":
                await self.mark_all_read()
            elif action == "get_notifications":
                notifications = await self.get_recent_notifications()
                await self.send(text_data=json.dumps({
                    "type": "notifications_list",
                    "data": notifications,
                }))
        except (json.JSONDecodeError, KeyError):
            pass

    async def send_notification(self, event):
        """Push a new notification to the client."""
        await self.send(text_data=json.dumps({
            "type": "new_notification",
            "data": event["notification"],
        }))

    async def send_notification_update(self, event):
        """Push updated unread count."""
        await self.send(text_data=json.dumps({
            "type": "notification_count",
            "unread_count": event["count"],
        }))

    @database_sync_to_async
    def get_unread_count(self):
        from kokoroko.notifications import get_unread_count
        return get_unread_count(self.user)

    @database_sync_to_async
    def get_recent_notifications(self):
        from kokoroko.notifications import get_user_notifications
        notifications = get_user_notifications(self.user, limit=20)
        return notifications

    @database_sync_to_async
    def mark_notification_read(self, notification_id):
        from kokoroko.notifications import mark_notification_read
        mark_notification_read(self.user, notification_id)

    @database_sync_to_async
    def mark_all_read(self):
        from kokoroko.notifications import mark_all_read
        mark_all_read(self.user)


class DiceTimerConsumer(ProtectedConsumer):
    """
    Server-authoritative timer for dice game rounds.
    Broadcasts server_time + phase timing so frontend syncs correctly.
    Eliminates client-side timer drift.
    """

    async def on_connect(self):
        self.group_name = "dice_timer"
        await self.channel_layer.group_add(self.group_name, self.channel_name)

        # Send initial timer state
        timer_data = await self.get_timer_state()
        await self.send(text_data=json.dumps({
            "type": "timer_sync",
            "data": timer_data,
        }))

    async def on_disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def send_timer_sync(self, event):
        """Push timer sync data to all connected clients."""
        await self.send(text_data=json.dumps({
            "type": "timer_sync",
            "data": event["data"],
        }))

    async def send_phase_change(self, event):
        """Notify clients of a phase transition."""
        await self.send(text_data=json.dumps({
            "type": "phase_change",
            "data": event["data"],
        }))

    @database_sync_to_async
    def get_timer_state(self):
        """Get current timer state for all active virtual dice matches."""
        from dicePlayManager.models import Board, DicePlayMatch
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

            # Calculate phase duration based on board settings
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

        return {
            "server_time": now.isoformat(),
            "timers": timers,
        }
