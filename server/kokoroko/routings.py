from wallet.routing import websocket_urlpatterns as wallet_ws
from cockfightManager.routing import websocket_urlpatterns as cockfight_ws
from dicePlayManager.routing import websocket_urlpatterns as dice_play_ws
from kokoroko.ws_routing import websocket_urlpatterns as platform_ws

websocket_urlpatterns = [
    *wallet_ws,
    *cockfight_ws,
    *dice_play_ws,
    *platform_ws,
]
