from urllib.parse import parse_qs
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import UntypedToken
from jwt import decode as jwt_decode, DecodeError
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.conf import settings
from django.contrib.auth import get_user_model
from asgiref.sync import sync_to_async
from channels.auth import AuthMiddlewareStack

User = get_user_model()

class JWTAuthMiddleware:
    """
    Custom JWT authentication middleware for Channels WebSocket connections.
    Extracts JWT token from query string (?token=...) and authenticates the user.
    """

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        # Extract token from query string
        query_string = scope.get("query_string", b"").decode()
        token = parse_qs(query_string).get("token", [None])[0]

        # Make a mutable copy of scope to add the user
        scope = dict(scope)

        # Authenticate user asynchronously
        scope["user"] = await self.get_user(token)

        # Call the inner application with updated scope and all ASGI args
        return await self.inner(scope, receive, send)

    @staticmethod
    async def get_user(token):
        if token is None:
            return AnonymousUser()

        try:
            # Validate token signature and expiration
            UntypedToken(token)

            # Decode token payload to get user_id
            decoded = jwt_decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user_id = decoded.get("user_id")

            # Fetch user asynchronously
            user = await sync_to_async(User.objects.get)(id=user_id)
            return user

        except (InvalidToken, TokenError, User.DoesNotExist, DecodeError):
            return AnonymousUser()


def JWTAuthMiddlewareStack(inner):
    """
    Helper to create the middleware stack with default AuthMiddlewareStack inside.
    """
    return JWTAuthMiddleware(AuthMiddlewareStack(inner))
