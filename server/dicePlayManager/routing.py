from django.urls import re_path
from .consumers import DiceMatchConsumer, DiceMatchResultConsumer

websocket_urlpatterns = [
    re_path(r"ws/dice-match-updates/$", DiceMatchConsumer.as_asgi()),
    re_path(r"ws/dice-match-result/$", DiceMatchResultConsumer.as_asgi()),
]
