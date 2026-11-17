"""Descubrimiento y biblioteca pública (Fase 4 / H4).

PUBLIC nunca implica acceso anónimo: estos endpoints exigen sesión. Solo se
exponen copias PUBLIC y disponibles; nada de copias privadas ni de existencia
de usuarios que no publican.
"""

from app.repositories import db


def accounts_with_public_copies() -> list[dict]:
    with db.read_only() as cursor:
        cursor.execute(
            "SELECT u.username, u.display_name, COUNT(*) AS public_copies "
            "FROM TRACK_LOCATION l JOIN USER_ACCOUNT u ON u.user_id = l.owner_user_id "
            "WHERE l.visibility = 'PUBLIC' AND l.availability = 'AVAILABLE' AND u.is_active = 1 "
            "GROUP BY u.user_id, u.username, u.display_name "
            "ORDER BY u.username"
        )
        return list(cursor.fetchall())


def public_catalog(*, username: str) -> dict | None:
    """Catálogo público de una cuenta (solo PUBLIC + disponible). None si no existe."""
    with db.read_only() as cursor:
        cursor.execute(
            "SELECT user_id, username, display_name FROM USER_ACCOUNT WHERE username = %s AND is_active = 1 LIMIT 1",
            (username.strip().lower(),),
        )
        owner = cursor.fetchone()
        if owner is None:
            return None
        cursor.execute(
            "SELECT l.location_id, l.track_id, t.title, t.duration_seconds, t.track_number, "
            "       a.title AS album, l.size_bytes, l.mime_type, l.public_download_allowed, "
            "       l.created_at AS added_at, "
            "       GROUP_CONCAT(DISTINCT ar.name ORDER BY ta.position SEPARATOR ', ') AS artists "
            "FROM TRACK_LOCATION l "
            "JOIN TRACK t ON t.track_id = l.track_id "
            "LEFT JOIN ALBUM a ON a.album_id = t.album_id "
            "JOIN TRACK_ARTIST ta ON ta.track_id = t.track_id "
            "JOIN ARTIST ar ON ar.artist_id = ta.artist_id "
            "WHERE l.owner_user_id = %s AND l.visibility = 'PUBLIC' AND l.availability = 'AVAILABLE' "
            "GROUP BY l.location_id, l.track_id, t.title, t.duration_seconds, t.track_number, "
            "         a.title, l.size_bytes, l.mime_type, l.public_download_allowed, l.created_at "
            "ORDER BY l.created_at DESC",
            (owner["user_id"],),
        )
        items = list(cursor.fetchall())
    return {"username": owner["username"], "display_name": owner["display_name"], "items": items}
