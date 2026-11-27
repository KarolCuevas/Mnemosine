"""Entrada de producción: API y Vue compilado bajo el mismo origen."""
import os
from pathlib import Path

import mysql.connector
from fastapi import HTTPException as APIException
from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles


class FrontendFiles(StaticFiles):
    async def get_response(self, path, scope):
        parts = Path(path).parts
        # Una ruta API desconocida o un archivo privado nunca recibe el HTML de la SPA.
        if parts and (parts[0] == "api" or any(part.startswith(".") and part != "." for part in parts)):
            raise HTTPException(404)
        try:
            response = await super().get_response(path, scope)
        except HTTPException as error:
            headers = dict(scope.get("headers", []))
            if (error.status_code != 404 or scope["method"] not in ("GET", "HEAD")
                    or (parts and parts[0] == "assets")
                    or b"text/html" not in headers.get(b"accept", b"")):
                raise
            response = await super().get_response("index.html", scope)
        if response.headers.get("content-type", "").startswith("text/html"):
            response.headers["Cache-Control"] = "no-cache"
        elif parts and parts[0] == "assets":
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


def create_application():
    from app.main import app
    from app.repositories import db
    from app.core.config import get_settings

    directory = Path(os.environ.get("FRONTEND_DIST", Path(__file__).resolve().parents[2] / "frontend" / "dist"))
    if not (directory / "index.html").is_file():
        raise RuntimeError("Falta compilar el frontend de producción.")

    @app.get("/api/ready", include_in_schema=False)
    def ready():
        try:
            with db.read_only() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            if not Path(get_settings().storage_root or "").is_dir():
                raise OSError()
        except (mysql.connector.Error, OSError):
            raise APIException(503, "Servicio temporalmente no disponible.") from None
        return {"status": "ready"}

    app.mount("/", FrontendFiles(directory=directory, html=True), name="frontend")
    return app
