"""Biblioteca privada, búsqueda y resolución de copias (Fase 3)."""

from app.repositories import db


def mark_availability(*, location_id: int, track_id: int, availability: str) -> None:
    """Escribe disponibilidad real tras una comprobación en disco (nunca sin verificarla)."""
    with db.transaction() as cursor:
        cursor.execute(
            "UPDATE TRACK_LOCATION SET availability = %s WHERE location_id = %s AND track_id = %s",
            (availability, location_id, track_id),
        )


def list_library(*, owner_id: int, q: str | None, page: int, page_size: int) -> dict:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    offset = (page - 1) * page_size

    with db.read_only() as cursor:
        if q:
            where = (
                "l.owner_user_id = %s AND (LOCATE(%s, t.title) > 0 OR LOCATE(%s, ar.name) > 0 "
                "OR (a.title IS NOT NULL AND LOCATE(%s, a.title) > 0))"
            )
            params = (owner_id, q, q, q)
        else:
            where = "l.owner_user_id = %s"
            params = (owner_id,)

        cursor.execute(
            f"SELECT COUNT(DISTINCT l.location_id) AS total "
            f"FROM TRACK_LOCATION l JOIN TRACK t ON t.track_id = l.track_id "
            f"LEFT JOIN ALBUM a ON a.album_id = t.album_id "
            f"JOIN TRACK_ARTIST ta ON ta.track_id = t.track_id JOIN ARTIST ar ON ar.artist_id = ta.artist_id "
            f"WHERE {where}",
            params,
        )
        total = cursor.fetchone()["total"]

        cursor.execute(
            f"SELECT l.location_id, l.track_id, t.title, t.duration_seconds, t.track_number, "
            f"       a.title AS album, l.size_bytes, l.availability, l.visibility, l.created_at AS added_at, "
            f"       GROUP_CONCAT(DISTINCT ar.name ORDER BY ta.position SEPARATOR ', ') AS artists "
            f"FROM TRACK_LOCATION l JOIN TRACK t ON t.track_id = l.track_id "
            f"LEFT JOIN ALBUM a ON a.album_id = t.album_id "
            f"JOIN TRACK_ARTIST ta ON ta.track_id = t.track_id JOIN ARTIST ar ON ar.artist_id = ta.artist_id "
            f"WHERE {where} "
            f"GROUP BY l.location_id, l.track_id, t.title, t.duration_seconds, t.track_number, a.title, "
            f"         l.size_bytes, l.availability, l.visibility, l.created_at "
            f"ORDER BY l.created_at DESC LIMIT %s OFFSET %s",
            (*params, page_size, offset),
        )
        items = cursor.fetchall()
        for item in items:
            item["available"] = item["availability"] == "AVAILABLE"

    return {"items": items, "total": total, "page": page, "page_size": page_size}


def get_track_detail(*, track_id: int, user_id: int) -> dict | None:
    """Detalle de canción si el solicitante posee al menos una copia; si no, None."""
    with db.read_only() as cursor:
        cursor.execute(
            "SELECT t.track_id, t.title, t.duration_seconds, t.track_number, t.disc_number, "
            "       a.title AS album, a.release_year, "
            "       GROUP_CONCAT(DISTINCT ar.name ORDER BY ta.position SEPARATOR ', ') AS artists "
            "FROM TRACK t "
            "LEFT JOIN ALBUM a ON a.album_id = t.album_id "
            "JOIN TRACK_ARTIST ta ON ta.track_id = t.track_id JOIN ARTIST ar ON ar.artist_id = ta.artist_id "
            "WHERE t.track_id = %s "
            "GROUP BY t.track_id, t.title, t.duration_seconds, t.track_number, t.disc_number, a.title, a.release_year",
            (track_id,),
        )
        track = cursor.fetchone()
        if track is None:
            return None
        cursor.execute(
            "SELECT location_id, size_bytes, mime_type, visibility, availability, sha256, created_at "
            "FROM TRACK_LOCATION WHERE track_id = %s AND owner_user_id = %s ORDER BY created_at",
            (track_id, user_id),
        )
        track["copies"] = list(cursor.fetchall())
        if not track["copies"]:
            return None  # mismo 404 que "no existe": no revelar existencia
        return track


def resolve_owned_copy(*, track_id: int, user_id: int) -> dict | None:
    """Copia del dueño preferentemente disponible; None si no posee ninguna."""
    with db.read_only() as cursor:
        cursor.execute(
            "SELECT location_id, relative_path, size_bytes, mime_type, availability, visibility "
            "FROM TRACK_LOCATION "
            "WHERE track_id = %s AND owner_user_id = %s "
            "ORDER BY (availability = 'AVAILABLE') DESC, created_at LIMIT 1",
            (track_id, user_id),
        )
        return cursor.fetchone()
