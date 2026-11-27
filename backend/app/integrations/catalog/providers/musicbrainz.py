"""MusicBrainz público: consultas literales y normalización de campos del núcleo."""
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from uuid import UUID

import httpx
from pydantic import ValidationError

from app.core.config import get_settings
from ..contract import CatalogCapabilities, CatalogError, CatalogPage, MusicCatalogAdapter, Recording
from ..traffic import provider_slot

BASE_URL = "https://musicbrainz.org/ws/2"


def mbid(value: str) -> str:
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise CatalogError("Identificador de MusicBrainz no válido", status=422) from None


def literal(value: str) -> str:
    # Lucene: no interpretar operadores, comillas ni comodines aportados por el usuario.
    return '"' + re.sub(r'([+\-!(){}\[\]^"~*?:\\/&|])', r'\\\1', value) + '"'


def retry_seconds(value: str | None) -> int:
    try:
        if value and value.isdecimal():
            return min(86400, max(2, int(value)))
        when = parsedate_to_datetime(value or "")
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        return min(86400, max(2, int((when - datetime.now(timezone.utc)).total_seconds()) + 1))
    except (TypeError, ValueError, OverflowError):
        return 30


def normalize(raw: dict) -> Recording:
    identifier = mbid(raw.get("id"))
    artists = []
    for credit in raw.get("artist-credit", []):
        if not isinstance(credit, dict):
            continue
        artist = credit.get("artist") or {}
        name = artist.get("name") or credit.get("name")
        if not name:
            continue
        artists.append({"provider_id": mbid(artist["id"]) if artist.get("id") else None,
                        "name": name, "credit": credit.get("name") or name,
                        "join_phrase": credit.get("joinphrase") or ""})
    releases = {}
    for release in raw.get("releases", []):
        if release.get("id") and release.get("title"):
            rid = mbid(release["id"])
            releases[rid] = {"provider_id": rid, "title": release["title"], "date": release.get("date") or None}
    return Recording(
        provider="musicbrainz", provider_id=identifier, title=raw["title"], artists=artists,
        duration_ms=raw.get("length"),
        isrcs=sorted({x for x in raw.get("isrcs", []) if isinstance(x, str) and re.fullmatch(r"[A-Z]{2}[A-Z0-9]{3}\d{7}", x)}),
        releases=list(releases.values()), disambiguation=raw.get("disambiguation") or None,
        original_url=f"https://musicbrainz.org/recording/{identifier}",
        fetched_at=datetime.now(timezone.utc),
    )


class MusicBrainzAdapter(MusicCatalogAdapter):
    code = "musicbrainz"
    capabilities = CatalogCapabilities(search=True, lookup=True)

    def normalize_id(self, value: str) -> str:
        return mbid(value)

    @property
    def enabled(self) -> bool:
        settings = get_settings()
        return settings.musicbrainz_enabled and bool(settings.musicbrainz_contact)

    def _request(self, path: str, params: dict) -> dict:
        settings = get_settings()
        if not self.enabled:
            raise CatalogError("La consulta a MusicBrainz aún no está habilitada. El índice local sigue disponible.")
        with provider_slot(self.code):
            try:
                # Destino fijo. Sin cookies de Mnemosine, credenciales, redirecciones ni URLs del cliente.
                with httpx.Client(timeout=10, follow_redirects=False) as client:
                    with client.stream("GET", BASE_URL + path, params={**params, "fmt": "json"}, headers={
                        "User-Agent": f"Mnemosine/0.5.0 ({settings.musicbrainz_contact})",
                        "Accept": "application/json",
                    }) as response:
                        if response.status_code == 404:
                            raise CatalogError("Grabación no encontrada", status=404)
                        if response.status_code == 429 or response.status_code == 503:
                            raise CatalogError("MusicBrainz está ocupado. Reintenta más tarde.", status=429,
                                               retry_after=retry_seconds(response.headers.get("Retry-After")))
                        if response.status_code != 200:
                            raise CatalogError("MusicBrainz no pudo completar la consulta", status=502)
                        body = bytearray()
                        for chunk in response.iter_bytes(65536):
                            body.extend(chunk)
                            if len(body) > 2 * 1024 * 1024:
                                raise CatalogError("La respuesta del proveedor supera el límite admitido", status=502)
                        import json
                        data = json.loads(body)
                        if not isinstance(data, dict):
                            raise ValueError("respuesta no estructurada")
                        return data
            except (httpx.HTTPError, ValueError):
                raise CatalogError("No se pudo consultar MusicBrainz. Tu biblioteca local sigue disponible.", status=502) from None

    def search(self, title: str, artist: str, *, offset: int, limit: int) -> CatalogPage:
        query = f"recording:{literal(title)}"
        if artist:
            query += f" AND artist:{literal(artist)}"
        raw = self._request("/recording", {"query": query, "offset": offset, "limit": limit})
        try:
            return CatalogPage(items=[normalize(item) for item in raw["recordings"]], total=max(0, int(raw["count"])))
        except (KeyError, TypeError, ValueError, ValidationError, CatalogError):
            raise CatalogError("MusicBrainz devolvió metadatos no válidos", status=502) from None

    def get_reference(self, provider_id: str) -> Recording:
        identifier = mbid(provider_id)
        raw = self._request(f"/recording/{identifier}", {"inc": "artists+releases+isrcs"})
        try:
            result = normalize(raw)
            if result.provider_id != identifier:
                raise ValueError("identidad inesperada")
            return result
        except (KeyError, TypeError, ValueError, ValidationError, CatalogError):
            raise CatalogError("MusicBrainz devolvió metadatos no válidos", status=502) from None
