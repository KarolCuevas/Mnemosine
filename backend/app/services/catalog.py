"""Helpers compartidos para alta de metadatos de catálogo (find-or-create)."""


def find_or_create_artist(cursor, name: str) -> int:
    artist = name.strip()
    cursor.execute("SELECT artist_id FROM ARTIST WHERE LOWER(name) = LOWER(%s) LIMIT 1", (artist,))
    row = cursor.fetchone()
    if row:
        return row["artist_id"]
    cursor.execute("INSERT INTO ARTIST (name, sort_name) VALUES (%s, %s)", (artist, artist))
    return cursor.lastrowid


def find_or_create_album(cursor, title: str | None, release_year: int | None = None) -> int | None:
    album = (title or "").strip()
    if not album:
        return None
    cursor.execute("SELECT album_id FROM ALBUM WHERE LOWER(title) = LOWER(%s) LIMIT 1", (album,))
    row = cursor.fetchone()
    if row:
        return row["album_id"]
    cursor.execute(
        "INSERT INTO ALBUM (title, sort_title, release_year) VALUES (%s, %s, %s)",
        (album, album, release_year),
    )
    return cursor.lastrowid


def ensure_album_artist(cursor, album_id: int | None, artist_id: int) -> None:
    if album_id is None:
        return
    cursor.execute(
        "INSERT INTO ALBUM_ARTIST (album_id, artist_id) VALUES (%s, %s) "
        "ON DUPLICATE KEY UPDATE artist_id = artist_id",
        (album_id, artist_id),
    )
