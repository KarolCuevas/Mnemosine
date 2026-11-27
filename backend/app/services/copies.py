"""Resolución de copias accesibles para un usuario y una acción (Fase 4).

Regla del plan: ninguna entrega de audio sin resolver una copia autorizada,
y la comprobación se repite en CADA solicitud (incluidos rangos). Orden de
preferencia del MVP:

1. copia propia disponible para la acción;
2. copia compartida conmigo (share activo), disponible para la acción;
3. copia PUBLIC disponible (stream y view; download solo con descarga pública
   autorizada y declaración DOWNLOAD).

Una copia con disponibilidad MISSING/ERROR nunca entrega bytes; si falta en
disco se marca MISSING (write-through) y se sigue con la siguiente candidata.
"""

from app.repositories import db
from app.services.permissions import LocationFacts, can
from app.services.storage import get_storage_for_source
from app.storage.contract import ObjectState, StorageError

ACTION_VIEW = "view"
ACTION_STREAM = "stream"
ACTION_DOWNLOAD = "download"


def _candidates(*, track_id: int, user_id: int) -> list[dict]:
    with db.read_only() as cursor:
        cursor.execute(
            "SELECT l.location_id, l.track_id, l.owner_user_id, l.source_id, l.relative_path, l.size_bytes, "
            "       l.mime_type, l.visibility, l.public_download_allowed, l.availability, "
            "       s.can_stream AS share_stream, s.can_download AS share_download "
            "FROM TRACK_LOCATION l "
            "JOIN USER_ACCOUNT owner ON owner.user_id = l.owner_user_id AND owner.is_active = 1 "
            "LEFT JOIN TRACK_SHARE s "
            "       ON s.location_id = l.location_id AND s.recipient_user_id = %s AND s.revoked_at IS NULL "
            "WHERE l.track_id = %s "
            "  AND (l.owner_user_id = %s OR l.visibility = 'PUBLIC' "
            "       OR (s.share_id IS NOT NULL AND (s.can_stream = 1 OR s.can_download = 1)))",
            (user_id, track_id, user_id),
        )
        return list(cursor.fetchall())


def _facts(row: dict) -> LocationFacts:
    return LocationFacts(
        owner_user_id=row["owner_user_id"],
        visibility=row["visibility"],
        public_download_allowed=bool(row["public_download_allowed"]),
        share_stream=bool(row["share_stream"]),
        share_download=bool(row["share_download"]),
        availability=row["availability"],
    )


def _mark_missing(location_id: int) -> None:
    with db.transaction() as cursor:
        cursor.execute(
            "UPDATE TRACK_LOCATION SET availability = 'MISSING' WHERE location_id = %s",
            (location_id,),
        )


def can_view_track(*, track_id: int, user_id: int) -> bool:
    """Autoriza los metadatos/portada sin exigir que el audio esté conectado."""
    return any(can(actor_user_id=user_id, action=ACTION_VIEW, facts=_facts(row))
               for row in _candidates(track_id=track_id, user_id=user_id))


def resolve_for_action(*, track_id: int, user_id: int, action: str) -> tuple[dict | None, str]:
    """Devuelve (copia_o_None, estado).

    estado ∈ {'ok', 'unavailable', 'not_found'}:
    - 'ok': copia resuelta y verificada en disco;
    - 'unavailable': hay copia accesible, pero ninguna entregable (disco o MISSING);
    - 'not_found': ninguna copia accesible para esta acción (404 uniforme).
    """
    candidates = _candidates(track_id=track_id, user_id=user_id)
    if not candidates:
        return None, "not_found"

    allowed = [(row, _facts(row)) for row in candidates if can(actor_user_id=user_id, action=action, facts=_facts(row))]
    if not allowed:
        return None, "not_found"

    # Preferencia: propia > compartida > pública; estable por location_id.
    def rank(item: tuple[dict, LocationFacts]) -> tuple[int, int]:
        row, _ = item
        if row["owner_user_id"] == user_id:
            return (0, row["location_id"])
        if row.get("share_stream") or row.get("share_download"):
            return (1, row["location_id"])
        return (2, row["location_id"])

    any_unavailable = False
    for row, _ in sorted(allowed, key=rank):
        if row["availability"] != "AVAILABLE":
            any_unavailable = True
            continue
        try:
            storage = get_storage_for_source(row["source_id"])
            storage.require("read")
            info = storage.stat(row["relative_path"])
        except StorageError:
            any_unavailable = True
            continue
        if info.state != ObjectState.FOUND:
            if info.state == ObjectState.NOT_FOUND:
                _mark_missing(row["location_id"])
            any_unavailable = True
            continue
        return row, "ok"
    return None, ("unavailable" if any_unavailable else "not_found")


def access_summary(*, track_id: int, user_id: int) -> dict:
    """Resumen de derechos del usuario sobre una canción (para la UI)."""
    summary = {"can_stream": False, "can_download": False, "available": False}
    _, state_stream = resolve_for_action(track_id=track_id, user_id=user_id, action=ACTION_STREAM)
    _, state_download = resolve_for_action(track_id=track_id, user_id=user_id, action=ACTION_DOWNLOAD)
    summary["available"] = state_stream == "ok" or state_download == "ok"
    summary["can_stream"] = state_stream == "ok"
    summary["can_download"] = state_download == "ok"
    return summary
