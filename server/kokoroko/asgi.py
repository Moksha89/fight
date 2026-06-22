import os
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kokoroko.settings")

django_asgi_app = get_asgi_application()

# Move import here — AFTER get_asgi_application()
from userManager.middleware import JWTAuthMiddlewareStack

from kokoroko.routings import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": JWTAuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})
