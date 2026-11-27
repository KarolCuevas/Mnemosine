"""Consultas explícitas al proveedor, índice progresivo y colección privada."""
import base64
import hashlib
import hmac
import json
import time
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from app.core.config import get_settings
from app.integrations.catalog.contract import CatalogError
from app.integrations.catalog.providers.musicbrainz import MusicBrainzAdapter
from app.integrations.catalog.registry import MusicCatalogRegistry
from app.repositories import db, external_catalog as repository

registry = MusicCatalogRegistry()
registry.register("musicbrainz", MusicBrainzAdapter)


def providers() -> list[dict]:
    return [{"code": adapter.code, "name": "MusicBrainz" if adapter.code == "musicbrainz" else adapter.code,
             "kind": "catalog", "enabled": adapter.enabled,
             "capabilities": asdict(adapter.capabilities)} for adapter in registry.all()]


def _digest(value: str) -> str:
    return hmac.new(get_settings().secret_key.encode(), value.encode(), hashlib.sha256).hexdigest()


def _query_key(provider: str, title: str, artist: str, limit: int) -> str:
    # No se guardan términos ni búsquedas vinculadas a usuarios en el índice compartido.
    return _digest(json.dumps([provider, title, artist, limit], ensure_ascii=False))


def make_cursor(offset: int, query_key: str) -> str:
    payload = base64.urlsafe_b64encode(json.dumps([offset, query_key, int(time.time()) + 86400]).encode()).decode().rstrip("=")
    return payload + "." + _digest(payload)


def cursor_offset(cursor: str | None, query_key: str) -> int:
    if not cursor:
        return 0
    try:
        payload, signature = cursor.split(".", 1)
        if not hmac.compare_digest(_digest(payload), signature):
            raise ValueError()
        offset, key, expires = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if key != query_key or expires < time.time() or type(offset) is not int or not 0 <= offset <= 10000:
            raise ValueError()
        return offset
    except (ValueError, TypeError, KeyError):
        raise CatalogError("Página caducada o no válida; vuelve a buscar", status=422) from None


def search(provider: str, *, title: str, artist: str, cursor: str | None, limit: int) -> dict:
    adapter = registry.resolve(provider)
    title, artist = title.strip(), artist.strip()
    if not title or any(ord(c) < 32 for c in title + artist):
        raise CatalogError("Escribe un título válido", status=422)
    key = _query_key(provider, title, artist, limit)
    offset = cursor_offset(cursor, key)
    cache_key = _digest(f"{key}:{offset}")
    cached = repository.get_cached_search(cache_key)
    if cached is None:
        page = adapter.search(title, artist, offset=offset, limit=limit)
        repository.cache_search(cache_key, page.items, page.total)
        data = {"items": [item.model_dump(mode="json") for item in page.items], "total": page.total}
    else:
        data = cached
    next_offset = offset + limit
    return {**data, "origin": "cache" if cached is not None else "provider",
            "next_cursor": make_cursor(next_offset, key) if data["items"] and next_offset < data["total"] and next_offset <= 10000 else None}


def lookup(provider: str, identifier: str, *, refresh: bool = False):
    adapter = registry.resolve(provider)
    identifier = adapter.normalize_id(identifier)
    cached = repository.get_record(provider, identifier)
    if not refresh and cached and cached[1] and cached[1] > datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=get_settings().catalog_record_ttl_days):
        return cached[0]
    record = adapter.get_reference(identifier)
    with db.transaction() as cursor:
        repository.upsert(cursor, record, detailed=True)
    return record


def save(user_id: int, provider: str, identifier: str) -> dict:
    # No aceptar título, URL ni permisos del navegador: lookup verificado o caché de lookup.
    return repository.save_reference(user_id, lookup(provider, identifier))
