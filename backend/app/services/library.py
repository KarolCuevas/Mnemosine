"""Biblioteca privada, búsqueda y resolución de copias (Fase 3)."""

from app.repositories import db
from app.services.metadata import attach_cover_urls


def list_shared_with_me(*, user_id: int) -> list[dict]:
    """Copias compartidas conmigo (share activo), siempre disponibles para su acción."""
    with db.read_only() as cursor:
        cursor.execute(
            "SELECT l.location_id, l.track_id, t.title, t.duration_seconds, t.track_number, "
            "       a.title AS album, l.size_bytes, l.availability, l.mime_type, "
            "       s.can_stream, s.can_download, u.username AS owner_username, "
            "       GROUP_CONCAT(DISTINCT ar.name ORDER BY ta.position SEPARATOR ', ') AS artists "
            "FROM TRACK_SHARE s "
            "JOIN TRACK_LOCATION l ON l.location_id = s.location_id "
            "JOIN TRACK t ON t.track_id = l.track_id "
            "LEFT JOIN ALBUM a ON a.album_id = t.album_id "
            "JOIN USER_ACCOUNT u ON u.user_id = l.owner_user_id "
            "JOIN TRACK_ARTIST ta ON ta.track_id = t.track_id "
            "JOIN ARTIST ar ON ar.artist_id = ta.artist_id "
            "WHERE s.recipient_user_id = %s AND s.revoked_at IS NULL "
            "GROUP BY l.location_id, l.track_id, t.title, t.duration_seconds, t.track_number, a.title, "
            "         l.size_bytes, l.availability, l.mime_type, s.can_stream, s.can_download, u.username "
            "ORDER BY s.granted_at DESC",
            (user_id,),
        )
        items = list(cursor.fetchall())
    attach_cover_urls(items)
    return items


def list_library(*, owner_id: int, q: str | None, page: int, page_size: int) -> dict:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    offset = (page - 1) * page_size

    def _where(q_value: str | None, owner: int) -> tuple[str, tuple]:
        # LOCATE no se beneficia de índices; EXISTS se corta al primer
        # artista/álbum que coincida y evita evaluar todo el join.
        if q_value:
            return (
                "l.owner_user_id = %s AND (LOCATE(%s, t.title) > 0 "
                "OR EXISTS (SELECT 1 FROM TRACK_ARTIST ta JOIN ARTIST ar ON ar.artist_id = ta.artist_id "
                "           WHERE ta.track_id = t.track_id AND LOCATE(%s, ar.name) > 0) "
                "OR EXISTS (SELECT 1 FROM ALBUM a WHERE t.album_id = a.album_id "
                "           AND a.title IS NOT NULL AND LOCATE(%s, a.title) > 0))",
                (owner, q_value, q_value, q_value),
            )
        return ("l.owner_user_id = %s", (owner,))

    with db.read_only() as cursor:
        q_value = (q or "").strip() or None
        where, params = _where(q_value, owner_id)

        cursor.execute(
            f"SELECT COUNT(*) AS total "
            f"FROM TRACK_LOCATION l JOIN TRACK t ON t.track_id = l.track_id "
            f"WHERE {where}",
            params,
        )
        total = cursor.fetchone()["total"]

        cursor.execute(
            f"SELECT l.location_id, l.track_id, t.title, t.duration_seconds, t.track_number, "
            f"       a.title AS album, l.size_bytes, l.availability, l.visibility, l.created_at AS added_at, "
            f"       (SELECT GROUP_CONCAT(DISTINCT ar.name ORDER BY ta.position SEPARATOR ', ') "
            f"        FROM TRACK_ARTIST ta JOIN ARTIST ar ON ar.artist_id = ta.artist_id "
            f"        WHERE ta.track_id = t.track_id) AS artists "
            f"FROM TRACK_LOCATION l JOIN TRACK t ON t.track_id = l.track_id "
            f"LEFT JOIN ALBUM a ON a.album_id = t.album_id "
            f"WHERE {where} "
            f"ORDER BY l.location_id DESC LIMIT %s OFFSET %s",
            (*params, page_size, offset),
        )
        items = cursor.fetchall()
        for item in items:
            item["available"] = item["availability"] == "AVAILABLE"

    attach_cover_urls(items)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def get_track_detail(*, track_id: int, user_id: int) -> dict | None:
    """Detalle de canción si el solicitante puede verla (dueño, copia PUBLIC o
    compartida con él); si no, None (mismo 404, sin revelar existencia)."""
    from app.services import copies

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

    access = copies.access_summary(track_id=track_id, user_id=user_id)
    if not track["copies"] and not access["can_stream"] and not access["can_download"]:
        # Sin copia propia y sin acceso por share ni PUBLIC: 404 uniforme.
        return None
    track["access"] = access
    with db.read_only() as cursor:
        cursor.execute("SELECT album_artist, genre, release_year, cover_jpeg IS NOT NULL AS has_cover "
                       "FROM TRACK_METADATA WHERE track_id = %s", (track_id,))
        metadata = cursor.fetchone()
    if metadata:
        track.update({key: metadata[key] for key in ("album_artist", "genre", "release_year")})
    track["cover_url"] = f"/api/tracks/{track_id}/cover" if metadata and metadata["has_cover"] else None
    return track
