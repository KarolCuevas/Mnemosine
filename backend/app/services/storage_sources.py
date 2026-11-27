"""Inventario autorizado. El inventario LOCAL solo muestra copias registradas del solicitante."""
from dataclasses import asdict

from app.repositories import db
from app.services.storage import get_source, registry
from app.storage.contract import SourceUnavailableError, StorageError


def list_sources(user_id: int) -> list[dict]:
    with db.read_only() as cursor:
        cursor.execute("SELECT * FROM SOURCE WHERE source_id = 9001 OR owner_user_id = %s ORDER BY source_id", (user_id,))
        sources = cursor.fetchall()
    result = []
    for source in sources:
        try:
            capabilities = asdict(registry.resolve(source).capabilities)
        except StorageError:
            capabilities = None
        result.append({"source_id": source["source_id"], "name": source["name"],
                       "provider": source["adapter_code"], "status": source["status"],
                       "capabilities": capabilities})
    return result


def list_objects(user_id: int, source_id: int, *, cursor: str | None, limit: int) -> dict:
    source = get_source(source_id)
    if source_id != 9001 and source["owner_user_id"] != user_id:
        raise SourceUnavailableError("fuente no disponible")
    adapter = registry.resolve(source)
    adapter.require("listing")
    if source["adapter_code"] == "LOCAL":
        # No exponer carpetas físicas ni archivos de otras cuentas en una fuente compartida.
        try:
            after = int(cursor or "0")
        except ValueError:
            raise SourceUnavailableError("página no válida") from None
        with db.read_only() as sql:
            sql.execute("SELECT l.location_id, t.title AS name, l.size_bytes, l.availability "
                        "FROM TRACK_LOCATION l JOIN TRACK t ON t.track_id = l.track_id "
                        "WHERE l.source_id = %s AND l.owner_user_id = %s AND l.location_id > %s "
                        "ORDER BY l.location_id LIMIT %s", (source_id, user_id, after, limit + 1))
            rows = sql.fetchall()
        return {"items": rows[:limit], "next_cursor": str(rows[limit - 1]["location_id"]) if len(rows) > limit else None}
    page = adapter.list_objects(cursor=cursor, limit=limit)
    return {"items": [asdict(item) for item in page.items], "next_cursor": page.next_cursor}
