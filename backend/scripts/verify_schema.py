"""Verificación de restricciones contra MySQL real.

Ejecutar desde backend tras migrar: python -m scripts.verify_schema

Ejecuta pruebas negativas y positivas dentro de UNA transacción que se
revierte al final: no deja datos en la base. Las restricciones CHECK no
se pueden probar con triggers de sesión; aquí se validan las de las tablas.
MySQL puede hacer commit implícito en DDL: este script solo usa DML.
"""
import sys

import mysql.connector

from app.core.config import get_settings

USER_A = "verify_user_a"
USER_B = "verify_user_b"
SHA256_OK = "a" * 64
SHA256_OTHER = "b" * 64


def expect_error(cursor, sql: str, params: tuple, label: str) -> bool:
    try:
        cursor.execute(sql, params)
    except mysql.connector.Error:
        print(f"  ok    {label}: rechazado como se esperaba")
        return True
    print(f"  FALLO {label}: el valor inválido fue aceptado")
    return False


def main() -> int:
    settings = get_settings()
    connection = mysql.connector.connect(
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
        connection_timeout=5,
        autocommit=False,
    )
    results: list[bool] = []
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO USER_ACCOUNT (username, email, password_hash, role) VALUES (%s, %s, %s, 'USER')",
                (USER_A, f"{USER_A}@example.test", "hash-demo-a"),
            )
            user_a = cursor.lastrowid
            cursor.execute(
                "INSERT INTO USER_ACCOUNT (username, email, password_hash, role) VALUES (%s, %s, %s, 'USER')",
                (USER_B, f"{USER_B}@example.test", "hash-demo-b"),
            )
            user_b = cursor.lastrowid

            # Cuentas únicas
            results.append(expect_error(
                cursor,
                "INSERT INTO USER_ACCOUNT (username, email, password_hash) VALUES (%s, %s, %s)",
                (USER_A, "otro@example.test", "hash-x"),
                "USERNAME duplicado",
            ))

            # Sesiones únicas
            cursor.execute(
                "INSERT INTO USER_SESSION (user_id, token_hash, expires_at) VALUES (%s, %s, NOW() + INTERVAL 1 DAY)",
                (user_a, "c" * 64),
            )
            results.append(expect_error(
                cursor,
                "INSERT INTO USER_SESSION (user_id, token_hash, expires_at) VALUES (%s, %s, NOW() + INTERVAL 1 DAY)",
                (user_b, "c" * 64),
                "TOKEN_HASH duplicado",
            ))

            # Fuente y ruta relativa únicas por fuente
            cursor.execute("INSERT INTO DEVICE (name, kind) VALUES ('verify-device', 'SERVER')")
            device_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO SOURCE (device_id, name, base_relative_path) VALUES (%s, 'verify-source', 'verify')",
                (device_id,),
            )
            source_id = cursor.lastrowid

            cursor.execute("INSERT INTO ARTIST (name) VALUES ('verify-artist')")
            artist_id = cursor.lastrowid
            cursor.execute("INSERT INTO ALBUM (title) VALUES ('verify-album')")
            album_id = cursor.lastrowid
            cursor.execute("INSERT INTO TRACK (title, duration_seconds, album_id) VALUES ('verify-track', 100, %s)", (album_id,))
            track_id = cursor.lastrowid

            cursor.execute(
                "INSERT INTO TRACK_LOCATION (track_id, owner_user_id, source_id, relative_path, sha256, size_bytes, mime_type) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (track_id, user_a, source_id, "verify/song.mp3", SHA256_OK, 12345, "audio/mpeg"),
            )
            location_a = cursor.lastrowid
            # Mismos bytes, otra ruta: permitido (sin unicidad global de hash)
            cursor.execute(
                "INSERT INTO TRACK_LOCATION (track_id, owner_user_id, source_id, relative_path, sha256, size_bytes, mime_type) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (track_id, user_b, source_id, "verify/copia.mp3", SHA256_OK, 12345, "audio/mpeg"),
            )
            print("  ok    SHA-256 duplicado permitido para otra copia")
            # Misma ruta en la misma fuente: rechazada
            results.append(expect_error(
                cursor,
                "INSERT INTO TRACK_LOCATION (track_id, owner_user_id, source_id, relative_path, sha256, size_bytes, mime_type) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (track_id, user_a, source_id, "verify/song.mp3", SHA256_OTHER, 1, "audio/mpeg"),
                "UNIQUE(fuente, ruta)",
            ))
            # CHECK de longitud de hash
            results.append(expect_error(
                cursor,
                "INSERT INTO TRACK_LOCATION (track_id, owner_user_id, source_id, relative_path, sha256, size_bytes, mime_type) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (track_id, user_a, source_id, "verify/otro.mp3", "x" * 63, 1, "audio/mpeg"),
                "CHECK longitud SHA-256",
            ))
            # FK inexistente
            results.append(expect_error(
                cursor,
                "INSERT INTO TRACK_LOCATION (track_id, owner_user_id, source_id, relative_path, sha256, size_bytes, mime_type) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (track_id, user_a, 999999, "verify/fk.mp3", SHA256_OTHER, 1, "audio/mpeg"),
                "FK fuente inexistente",
            ))
            # RESTRICT al borrar dueño con copia
            results.append(expect_error(
                cursor,
                "DELETE FROM USER_ACCOUNT WHERE user_id = %s",
                (user_a,),
                "RESTRICT al borrar dueño con copias",
            ))

            # Listas: (lista, canción) y (lista, posición) únicas
            cursor.execute("INSERT INTO PLAYLIST (owner_user_id, name) VALUES (%s, 'verify-playlist')", (user_a,))
            playlist_id = cursor.lastrowid
            cursor.execute("INSERT INTO PLAYLIST_TRACK (playlist_id, track_id, position) VALUES (%s, %s, 1)", (playlist_id, track_id))
            results.append(expect_error(
                cursor,
                "INSERT INTO PLAYLIST_TRACK (playlist_id, track_id, position) VALUES (%s, %s, 2)",
                (playlist_id, track_id),
                "PLAYLIST_TRACK duplicada (lista, canción)",
            ))
            cursor.execute("INSERT INTO ARTIST (name) VALUES ('verify-artist-2')")
            artist2 = cursor.lastrowid
            cursor.execute("INSERT INTO TRACK (title, duration_seconds) VALUES ('verify-track-2', 90)")
            track2 = cursor.lastrowid
            results.append(expect_error(
                cursor,
                "INSERT INTO PLAYLIST_TRACK (playlist_id, track_id, position) VALUES (%s, %s, 1)",
                (playlist_id, track2),
                "PLAYLIST_TRACK posición duplicada",
            ))

            # Compartir: un share activo por (copia, destinatario)
            cursor.execute(
                "INSERT INTO TRACK_SHARE (location_id, recipient_user_id, can_stream, can_download, granted_by, declaration) "
                "VALUES (%s, %s, 1, 0, %s, 'verify')",
                (location_a, user_b, user_a),
            )
            results.append(expect_error(
                cursor,
                "INSERT INTO TRACK_SHARE (location_id, recipient_user_id, can_stream, can_download, granted_by, declaration) "
                "VALUES (%s, %s, 0, 1, %s, 'verify')",
                (location_a, user_b, user_a),
                "TRACK_SHARE duplicado (copia, destinatario)",
            ))

            # Autorización asociada a la copia: kind válido / inválido
            cursor.execute(
                "INSERT INTO AUTHORIZATION_DECLARATION (location_id, kind, declaration, declared_by) "
                "VALUES (%s, 'PUBLICATION', 'verify-publicacion', %s)",
                (location_a, user_a),
            )
            print("  ok    AUTHORIZATION_DECLARATION PUBLICATION insertada")
            results.append(expect_error(
                cursor,
                "INSERT INTO AUTHORIZATION_DECLARATION (location_id, kind, declaration, declared_by) "
                "VALUES (%s, 'BOGUS', 'verify', %s)",
                (location_a, user_a),
                "AUTHORIZATION_DECLARATION kind fuera de catálogo",
            ))

            # ENUM inválido
            results.append(expect_error(
                cursor,
                "INSERT INTO PERMISSION_AUDIT (actor_user_id, action, details) VALUES (%s, 'BOGUS', 'verify')",
                (user_a,),
                "PERMISSION_AUDIT acción fuera de catálogo",
            ))
        connection.rollback()
    finally:
        connection.close()

    failed = results.count(False)
    print()
    if failed:
        print(f"Verificación: {failed} de {len(results)} comprobaciones FALLARON.", file=sys.stderr)
        return 1
    print(f"Verificación: {len(results)} comprobaciones correctas (transacción revertida, sin datos residuales).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
