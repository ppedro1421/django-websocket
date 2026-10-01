from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed, InvalidToken, TokenError


class JWTAuthMiddleware:
    """Autentica WebSockets por JWT sem remover o suporte a sessão."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        scope = dict(scope)
        raw_token = self.get_raw_token(scope)

        if raw_token:
            try:
                scope["user"] = await self.get_user(raw_token)
            except (AuthenticationFailed, InvalidToken, TokenError):
                scope["user"] = AnonymousUser()

        return await self.app(scope, receive, send)

    @staticmethod
    def get_raw_token(scope):
        headers = dict(scope.get("headers", []))
        authorization = headers.get(b"authorization", b"")
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == b"bearer":
            return parts[1]

        query = parse_qs(scope.get("query_string", b"").decode())
        tokens = query.get("access_token")
        if tokens:
            return tokens[0].encode()
        return None

    @database_sync_to_async
    def get_user(self, raw_token):
        authentication = JWTAuthentication()
        validated_token = authentication.get_validated_token(raw_token)
        return authentication.get_user(validated_token)
