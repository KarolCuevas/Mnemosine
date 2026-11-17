"""Listas privadas ordenadas (Fase 4 / H4).

Pertenecer a una lista NUNCA otorga derechos sobre el audio: la autorización
se resuelve siempre vía TRACK_LOCATION (regla 2 del plan). Solo el dueño
crea/consulta/cambia contenido y orden. La misma canción aparece una sola vez
por lista (PK PLAYLIST_TRACK) y la posición es única por lista
(UNIQUE(playlist_id, position)); reordenar usa posiciones temporales negativas
dentro de una transacción.
"""

from app.repositories import db
from app.services.errors import ServiceError


class PlaylistNotFoundError(ServiceError):
    pass


def create_playlist(*, owner_id: int, name: str, description: str | None = None) -> dict:
    name = name.strip()
    if not name:
        raise ServiceError("el nombre no puede estar vacío")
    if len(name) > 255:
        raise ServiceError("el nombre es demasiado largo")
    with db.transaction() as cursor:
        cursor.execute(
            "INSERT INTO PLAYLIST (owner_user_id, name, description) VALUES (%s, %s, %s)",
            (owner_id, name, (description or "").strip() or None),
        )
        playlist_id = cursor.lastrowid
        cursor.execute(
            "SELECT playlist_id, name, description, created_at, updated_at "
            "FROM PLAYLIST WHERE playlist_id = %s",
            (playlist_id,),
        )
        created = cursor.fetchone()
    return created


def list_playlists(*, owner_id: int) -> list[dict]:
    with db.read_only() as cursor:
        cursor.execute(
            "SELECT p.playlist_id, p.name, p.description, p.created_at, p.updated_at, "
            "       COUNT(pt.track_id) AS item_count "
            "FROM PLAYLIST p LEFT JOIN PLAYLIST_TRACK pt ON pt.playlist_id = p.playlist_id "
            "WHERE p.owner_user_id = %s "
            "GROUP BY p.playlist_id, p.name, p.description, p.created_at, p.updated_at "
            "ORDER BY p.updated_at DESC",
            (owner_id,),
        )
        return list(cursor.fetchall())


def _owned_playlist(cursor, *, playlist_id: int, owner_id: int) -> dict:
    cursor.execute(
        "SELECT playlist_id, name, description FROM PLAYLIST WHERE playlist_id = %s AND owner_user_id = %s LIMIT 1",
        (playlist_id, owner_id),
    )
    row = cursor.fetchone()
    if row is None:
        raise PlaylistNotFoundError("lista no encontrada")
    return row


def get_playlist_detail(*, owner_id: int, playlist_id: int) -> dict:
    with db.read_only() as cursor:
        playlist = _owned_playlist(cursor, playlist_id=playlist_id, owner_id=owner_id)
        cursor.execute(
            "SELECT pt.position, t.track_id, t.title, t.duration_seconds, t.track_number, "
            "       a.title AS album, "
            "       GROUP_CONCAT(DISTINCT ar.name ORDER BY ta.position SEPARATOR ', ') AS artists "
            "FROM PLAYLIST_TRACK pt "
            "JOIN TRACK t ON t.track_id = pt.track_id "
            "LEFT JOIN ALBUM a ON a.album_id = t.album_id "
            "JOIN TRACK_ARTIST ta ON ta.track_id = t.track_id "
            "JOIN ARTIST ar ON ar.artist_id = ta.artist_id "
            "WHERE pt.playlist_id = %s "
            "GROUP BY pt.position, t.track_id, t.title, t.duration_seconds, t.track_number, a.title "
            "ORDER BY pt.position",
            (playlist_id,),
        )
        playlist["tracks"] = list(cursor.fetchall())
        return playlist


def update_playlist(*, owner_id: int, playlist_id: int, name: str | None, description: str | None) -> dict:
    if name is not None and not name.strip():
        raise ServiceError("el nombre no puede estar vacío")
    with db.transaction() as cursor:
        playlist = _owned_playlist(cursor, playlist_id=playlist_id, owner_id=owner_id)
        new_name = name.strip() if name is not None else playlist["name"]
        new_description = (description if description is not None else playlist["description"] or "") or None
        cursor.execute(
            "UPDATE PLAYLIST SET name = %s, description = %s WHERE playlist_id = %s",
            (new_name, (new_description or "").strip() or None, playlist_id),
        )
        playlist["name"] = new_name
        playlist["description"] = (new_description or "").strip() or None
    return playlist


def delete_playlist(*, owner_id: int, playlist_id: int) -> None:
    with db.transaction() as cursor:
        _owned_playlist(cursor, playlist_id=playlist_id, owner_id=owner_id)
        cursor.execute("DELETE FROM PLAYLIST WHERE playlist_id = %s", (playlist_id,))


def add_track(*, owner_id: int, playlist_id: int, track_id: int) -> dict:
    from app.services import copies

    # Primero la propiedad de la lista (404 uniforme, sin revelar existencia);
    # después el acceso a la canción.
    with db.transaction() as cursor:
        _owned_playlist(cursor, playlist_id=playlist_id, owner_id=owner_id)
    copies_visible = copies.access_summary(track_id=track_id, user_id=owner_id)
    if not copies_visible["can_stream"] and not copies_visible["can_download"]:
        # Ni siquiera puede ver la canción: la lista no debe referenciarla.
        raise ServiceError("no tienes acceso a esa canción")
    with db.transaction() as cursor:
        _owned_playlist(cursor, playlist_id=playlist_id, owner_id=owner_id)
        cursor.execute("SELECT track_id FROM TRACK WHERE track_id = %s LIMIT 1", (track_id,))
        if cursor.fetchone() is None:
            raise ServiceError("la canción no existe")
        cursor.execute(
            "SELECT COALESCE(MAX(position), 0) AS last_position FROM PLAYLIST_TRACK WHERE playlist_id = %s",
            (playlist_id,),
        )
        next_position = cursor.fetchone()["last_position"] + 1
        try:
            cursor.execute(
                "INSERT INTO PLAYLIST_TRACK (playlist_id, track_id, position) VALUES (%s, %s, %s)",
                (playlist_id, track_id, next_position),
            )
        except Exception as error:
            raise ServiceError("la canción ya está en la lista") from error
    return {"playlist_id": playlist_id, "track_id": track_id, "position": next_position}


def remove_track(*, owner_id: int, playlist_id: int, track_id: int) -> dict:
    with db.transaction() as cursor:
        _owned_playlist(cursor, playlist_id=playlist_id, owner_id=owner_id)
        cursor.execute(
            "DELETE FROM PLAYLIST_TRACK WHERE playlist_id = %s AND track_id = %s",
            (playlist_id, track_id),
        )
        if cursor.rowcount != 1:
            raise PlaylistNotFoundError("la canción no está en la lista")
        # Re-numerar posiciones densas 1..N tras quitar un elemento.
        cursor.execute(
            "SELECT track_id FROM PLAYLIST_TRACK WHERE playlist_id = %s ORDER BY position",
            (playlist_id,),
        )
        rows = cursor.fetchall()
        for index, row in enumerate(rows, start=1):
            cursor.execute(
                "UPDATE PLAYLIST_TRACK SET position = -%s WHERE playlist_id = %s AND track_id = %s",
                (index, playlist_id, row["track_id"]),
            )
        for index, row in enumerate(rows, start=1):
            cursor.execute(
                "UPDATE PLAYLIST_TRACK SET position = %s WHERE playlist_id = %s AND track_id = %s",
                (index, playlist_id, row["track_id"]),
            )
    return {"playlist_id": playlist_id, "track_id": track_id, "removed": True}


def reorder_tracks(*, owner_id: int, playlist_id: int, ordered_track_ids: list[int]) -> dict:
    if not ordered_track_ids:
        raise ServiceError("la lista no puede quedar vacía por esta vía; usa el borrado de elementos")
    with db.transaction() as cursor:
        _owned_playlist(cursor, playlist_id=playlist_id, owner_id=owner_id)
        cursor.execute(
            "SELECT track_id FROM PLAYLIST_TRACK WHERE playlist_id = %s",
            (playlist_id,),
        )
        current = {row["track_id"] for row in cursor.fetchall()}
        if set(ordered_track_ids) != current or len(ordered_track_ids) != len(current):
            raise ServiceError("el orden debe contener exactamente las canciones de la lista")
        # Fase 1: posiciones temporales negativas (evita violar UNIQUE(playlist_id, position)).
        for index, track_id in enumerate(ordered_track_ids, start=1):
            cursor.execute(
                "UPDATE PLAYLIST_TRACK SET position = -%s WHERE playlist_id = %s AND track_id = %s",
                (index, playlist_id, track_id),
            )
        # Fase 2: posiciones definitivas.
        for index, track_id in enumerate(ordered_track_ids, start=1):
            cursor.execute(
                "UPDATE PLAYLIST_TRACK SET position = %s WHERE playlist_id = %s AND track_id = %s",
                (index, playlist_id, track_id),
            )
    return {"playlist_id": playlist_id, "order": ordered_track_ids}
