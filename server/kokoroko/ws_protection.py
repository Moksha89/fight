"""
WebSocket protection middleware and base consumer.

Provides:
- Per-user connection limit (max 5 concurrent WS connections)
- Reconnect spam detection (>10 connects/min per user)
- Incoming message size limit (4KB)
- Server-initiated ping/heartbeat with stale connection cleanup
- Safe logging (no JWT tokens)
"""

import asyncio
import logging
import time

from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger("kokoroko.ws")

# ── Configuration ──────────────────────────────────────────────────────────────

WS_MAX_CONNECTIONS_PER_USER = 5
WS_MAX_MESSAGE_SIZE = 4096  # 4KB
WS_PING_INTERVAL = 30  # seconds
WS_PONG_TIMEOUT = 90  # seconds without pong/activity → disconnect
WS_RECONNECT_WINDOW = 60  # seconds
WS_RECONNECT_MAX = 10  # max connects per window
WS_CONN_KEY_PREFIX = "ws:conn:"
WS_CONN_TTL = 300  # 5 min auto-expire (safety net)
WS_RECONNECT_KEY_PREFIX = "ws:reconn:"


# ── Direct Redis operations for atomic counters ───────────────────────────────

_redis_client = None


def _get_redis():
    """Get a direct Redis client (same DB as Django cache)."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        import redis
        from django.conf import settings
        location = settings.CACHES.get("default", {}).get("LOCATION", "redis://localhost:6379/1")
        _redis_client = redis.Redis.from_url(location)
        _redis_client.ping()
        return _redis_client
    except Exception:
        return None


def _conn_key(user_id):
    return f"{WS_CONN_KEY_PREFIX}{user_id}"


def _reconnect_key(user_id):
    return f"{WS_RECONNECT_KEY_PREFIX}{user_id}"


def increment_user_connections(user_id):
    """Atomically increment connection count. Returns new count."""
    key = _conn_key(user_id)
    try:
        r = _get_redis()
        if r is None:
            return 1
        val = r.incr(key)
        r.expire(key, WS_CONN_TTL)
        return val
    except Exception:
        return 1


def decrement_user_connections(user_id):
    """Atomically decrement connection count."""
    key = _conn_key(user_id)
    try:
        r = _get_redis()
        if r is None:
            return
        val = r.decr(key)
        if val <= 0:
            r.delete(key)
    except Exception:
        pass


def check_reconnect_spam(user_id):
    """Atomically check if user is reconnecting too fast."""
    key = _reconnect_key(user_id)
    try:
        r = _get_redis()
        if r is None:
            return False
        val = r.incr(key)
        if val == 1:
            r.expire(key, WS_RECONNECT_WINDOW)
        return val > WS_RECONNECT_MAX
    except Exception:
        return False


# ── Protected Base Consumer ───────────────────────────────────────────────────

class ProtectedConsumer(AsyncWebsocketConsumer):
    """
    Base consumer with built-in protections.
    Subclass and override on_connect(), on_disconnect(), on_receive().
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ping_task = None
        self._last_activity = None
        self._user_id = None
        self._counted = False

    async def connect(self):
        user = self.scope.get("user")
        if not user or user.is_anonymous:
            await self.close(code=4001)
            return

        self._user_id = str(user.id)

        # Check reconnect spam
        if check_reconnect_spam(self._user_id):
            logger.warning(
                "WS reconnect spam: user=%s path=%s",
                self._user_id, self.scope.get("path", "?"),
            )
            await self.close(code=4008)
            return

        # Check per-user connection limit (atomic increment)
        count = increment_user_connections(self._user_id)
        self._counted = True
        if count > WS_MAX_CONNECTIONS_PER_USER:
            logger.warning(
                "WS connection limit exceeded: user=%s count=%d max=%d",
                self._user_id, count, WS_MAX_CONNECTIONS_PER_USER,
            )
            decrement_user_connections(self._user_id)
            self._counted = False
            await self.close(code=4002)
            return

        self._last_activity = time.monotonic()
        await self.accept()

        # Start ping/heartbeat loop
        self._ping_task = asyncio.ensure_future(self._ping_loop())

        # Call subclass hook
        await self.on_connect()

    async def disconnect(self, close_code):
        # Cancel ping task
        if self._ping_task and not self._ping_task.done():
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass

        # Decrement connection counter
        if self._counted and self._user_id:
            decrement_user_connections(self._user_id)
            self._counted = False

        await self.on_disconnect(close_code)

    async def receive(self, text_data=None, bytes_data=None):
        self._last_activity = time.monotonic()

        # Check message size
        payload = text_data or bytes_data
        if payload and len(payload) > WS_MAX_MESSAGE_SIZE:
            logger.warning(
                "WS oversized message: user=%s size=%d max=%d path=%s",
                self._user_id, len(payload), WS_MAX_MESSAGE_SIZE,
                self.scope.get("path", "?"),
            )
            await self.send(text_data='{"error":"message_too_large"}')
            return

        await self.on_receive(text_data=text_data, bytes_data=bytes_data)

    async def send(self, text_data=None, bytes_data=None, close=False):
        """Override send to track activity for heartbeat."""
        self._last_activity = time.monotonic()
        await super().send(text_data=text_data, bytes_data=bytes_data, close=close)

    async def _ping_loop(self):
        """Send WebSocket ping frames and detect stale connections."""
        try:
            while True:
                await asyncio.sleep(WS_PING_INTERVAL)

                # Check for stale connection
                if self._last_activity:
                    idle = time.monotonic() - self._last_activity
                    if idle > WS_PONG_TIMEOUT:
                        logger.info(
                            "WS heartbeat timeout: user=%s idle=%.0fs path=%s",
                            self._user_id, idle, self.scope.get("path", "?"),
                        )
                        await self.close(code=4003)
                        return

                # Send application-level ping
                try:
                    await self.send(text_data='{"type":"ping"}')
                except Exception:
                    return
        except asyncio.CancelledError:
            pass

    # ── Subclass hooks ────────────────────────────────────────────────────────

    async def on_connect(self):
        """Override in subclass for connect logic (after auth + limits pass)."""
        pass

    async def on_disconnect(self, close_code):
        """Override in subclass for disconnect cleanup."""
        pass

    async def on_receive(self, text_data=None, bytes_data=None):
        """Override in subclass for message handling."""
        pass
