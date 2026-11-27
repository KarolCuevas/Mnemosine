"""Ocultar códigos OAuth a los registros de acceso y no cachear credenciales/respuestas."""
from urllib.parse import parse_qs
from starlette.responses import JSONResponse
from app.core.config import get_settings
from app.integrations.google_drive.config import CALLBACK_PATH


class GoogleOAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/api/integrations/google_drive/"):
            return await self.app(scope, receive, send)
        if scope["path"] == CALLBACK_PATH:
            raw = scope.get("query_string", b"")
            scope["query_string"] = b""  # Uvicorn registra scope al enviar la respuesta.
            try:
                parsed = parse_qs(raw.decode("ascii"), max_num_fields=16, keep_blank_values=True)
                scope["google_oauth_query"] = {key: values[0] for key, values in parsed.items()
                                               if key in ("state", "code", "error") and len(values) == 1}
                if len(raw) > 8192:
                    scope["google_oauth_query"] = {}
            except (ValueError, UnicodeError):
                scope["google_oauth_query"] = {}

        async def private_send(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend([(b"cache-control", b"private, no-store"), (b"pragma", b"no-cache"),
                                (b"referrer-policy", b"no-referrer"), (b"x-content-type-options", b"nosniff"),
                                (b"cross-origin-resource-policy", b"same-origin")])
                message = {**message, "headers": headers}
            await send(message)

        headers = dict(scope.get("headers", []))
        if scope["method"] not in ("GET", "HEAD", "OPTIONS"):
            origin = headers.get(b"origin")
            if (headers.get(b"sec-fetch-site") == b"cross-site"
                    or (origin and origin.decode("latin1") != get_settings().google_app_origin)):
                return await JSONResponse({"detail": "Origen no permitido."}, status_code=403)(scope, receive, private_send)
        await self.app(scope, receive, private_send)
