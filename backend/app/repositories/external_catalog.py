"""Índice público y referencias privadas. SQL parametrizado; ninguna ruta de audio."""
import json
import unicodedata
from datetime import datetime, timezone

from app.core.config import get_settings
from app.integrations.catalog.contract import Recording
from . import db


def search_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _json(value):
    return json.loads(value) if isinstance(value, (str, bytes)) else value


def _item(row: dict) -> dict:
    item = Recording.model_validate(_json(row["metadata"])).model_dump(mode="json")
    if "external_track_id" in row:
        item["reference_id"] = row["external_track_id"]
        item["saved_at"] = row["created_at"].replace(tzinfo=timezone.utc).isoformat()
    return item


def upsert(cursor, record: Recording, *, detailed: bool = False) -> int:
    # Las páginas de búsqueda son parciales: no degradan un lookup completo ya guardado.
    cursor.execute(
        "INSERT INTO CATALOG_RECORD (provider, entity_type, provider_id, title, title_search, artist_search, "
        "metadata, fetched_at, lookup_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) "
        "ON DUPLICATE KEY UPDATE "
        "title = IF(lookup_at IS NULL OR %s, VALUES(title), title), "
        "title_search = IF(lookup_at IS NULL OR %s, VALUES(title_search), title_search), "
        "artist_search = IF(lookup_at IS NULL OR %s, VALUES(artist_search), artist_search), "
        "metadata = IF(lookup_at IS NULL OR %s, VALUES(metadata), metadata), "
        "fetched_at = IF(lookup_at IS NULL OR %s, VALUES(fetched_at), fetched_at), "
        "lookup_at = IF(%s, VALUES(lookup_at), lookup_at)",
        (record.provider, record.entity_type, record.provider_id, record.title, search_text(record.title),
         search_text(" ".join(a.name + " " + a.credit for a in record.artists)),
         record.model_dump_json(), record.fetched_at.replace(tzinfo=None),
         record.fetched_at.replace(tzinfo=None) if detailed else None, *([detailed] * 6)),
    )
    cursor.execute("SELECT catalog_record_id FROM CATALOG_RECORD WHERE provider = %s AND entity_type = %s AND provider_id = %s",
                   (record.provider, record.entity_type, record.provider_id))
    return cursor.fetchone()["catalog_record_id"]


def get_record(provider: str, provider_id: str) -> tuple[Recording, datetime | None] | None:
    with db.read_only() as cursor:
        cursor.execute("SELECT metadata, lookup_at FROM CATALOG_RECORD WHERE provider = %s AND entity_type = 'recording' AND provider_id = %s",
                       (provider, provider_id))
        row = cursor.fetchone()
        return (Recording.model_validate(_json(row["metadata"])), row["lookup_at"]) if row else None


def get_cached_search(key: str) -> dict | None:
    with db.read_only() as cursor:
        cursor.execute("SELECT record_ids, total FROM CATALOG_QUERY_CACHE WHERE cache_key = %s AND expires_at > UTC_TIMESTAMP(6)", (key,))
        cached = cursor.fetchone()
        if not cached:
            return None
        ids = _json(cached["record_ids"])
        if not ids:
            return {"items": [], "total": cached["total"]}
        placeholders = ",".join(["%s"] * len(ids))
        cursor.execute(f"SELECT catalog_record_id, metadata FROM CATALOG_RECORD WHERE catalog_record_id IN ({placeholders})", tuple(ids))
        records = {row["catalog_record_id"]: _item(row) for row in cursor.fetchall()}
        if any(rid not in records for rid in ids):
            return None
        return {"items": [records[rid] for rid in ids], "total": cached["total"]}


def cache_search(key: str, records: list[Recording], total: int) -> None:
    with db.transaction() as cursor:
        ids = [upsert(cursor, record) for record in records]
        cursor.execute("DELETE FROM CATALOG_QUERY_CACHE WHERE expires_at <= UTC_TIMESTAMP(6) LIMIT 100", ())
        cursor.execute(
            "INSERT INTO CATALOG_QUERY_CACHE (cache_key, record_ids, total, expires_at) "
            "VALUES (%s,%s,%s,TIMESTAMPADD(SECOND,%s,UTC_TIMESTAMP(6))) "
            "ON DUPLICATE KEY UPDATE record_ids = VALUES(record_ids), total = VALUES(total), expires_at = VALUES(expires_at)",
            (key, json.dumps(ids), total, get_settings().catalog_cache_seconds),
        )


def local_search(*, title: str, artist: str, page: int, page_size: int) -> dict:
    title, artist = search_text(title), search_text(artist)
    with db.read_only() as cursor:
        where = "entity_type = 'recording' AND LOCATE(%s, title_search) > 0 AND LOCATE(%s, artist_search) > 0"
        cursor.execute(f"SELECT COUNT(*) AS total FROM CATALOG_RECORD WHERE {where}", (title, artist))
        total = cursor.fetchone()["total"]
        cursor.execute(f"SELECT metadata FROM CATALOG_RECORD WHERE {where} ORDER BY catalog_record_id DESC LIMIT %s OFFSET %s",
                       (title, artist, page_size, (page - 1) * page_size))
        return {"items": [_item(row) for row in cursor.fetchall()], "total": total,
                "page": page, "page_size": page_size, "origin": "local"}


def save_reference(user_id: int, record: Recording) -> dict:
    with db.transaction() as cursor:
        cursor.execute("SELECT user_id FROM USER_ACCOUNT WHERE user_id = %s AND is_active = 1 FOR UPDATE", (user_id,))
        if cursor.fetchone() is None:
            from app.integrations.catalog.contract import CatalogError
            raise CatalogError("No autenticado", status=401)
        rid = upsert(cursor, record, detailed=True)
        cursor.execute("INSERT INTO EXTERNAL_TRACK (owner_user_id, catalog_record_id) VALUES (%s,%s) "
                       "ON DUPLICATE KEY UPDATE external_track_id = LAST_INSERT_ID(external_track_id)", (user_id, rid))
        cursor.execute("SELECT e.external_track_id, e.created_at, c.metadata FROM EXTERNAL_TRACK e "
                       "JOIN CATALOG_RECORD c ON c.catalog_record_id = e.catalog_record_id "
                       "WHERE e.owner_user_id = %s AND e.catalog_record_id = %s", (user_id, rid))
        return _item(cursor.fetchone())


def list_references(user_id: int, *, page: int, page_size: int) -> dict:
    with db.read_only() as cursor:
        cursor.execute("SELECT COUNT(*) AS total FROM EXTERNAL_TRACK WHERE owner_user_id = %s", (user_id,))
        total = cursor.fetchone()["total"]
        cursor.execute("SELECT e.external_track_id, e.created_at, c.metadata FROM EXTERNAL_TRACK e "
                       "JOIN CATALOG_RECORD c ON c.catalog_record_id = e.catalog_record_id "
                       "WHERE e.owner_user_id = %s ORDER BY e.external_track_id DESC LIMIT %s OFFSET %s",
                       (user_id, page_size, (page - 1) * page_size))
        return {"items": [_item(row) for row in cursor.fetchall()], "total": total, "page": page, "page_size": page_size}


def delete_reference(user_id: int, reference_id: int) -> bool:
    with db.transaction() as cursor:
        cursor.execute("DELETE FROM EXTERNAL_TRACK WHERE external_track_id = %s AND owner_user_id = %s", (reference_id, user_id))
        return cursor.rowcount > 0
