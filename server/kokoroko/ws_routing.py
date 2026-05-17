from django.urls import re_path
from .ws_consumers import NotificationConsumer, DiceTimerConsumer

websocket_urlpatterns = [
    re_path(r"ws/notifications/$", NotificationConsumer.as_asgi()),
    re_path(r"ws/dice-timer/$", DiceTimerConsumer.as_asgi()),
]
