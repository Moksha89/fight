
from django.urls import re_path
from .consumers import *

websocket_urlpatterns = [
    re_path(r"ws/match-updates/$", MatchConsumer.as_asgi()),
    re_path(r"ws/match-result/$", MatchResultConsumer.as_asgi()),
]
