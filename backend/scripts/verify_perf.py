"""Medición de rendimiento con 10.000 canciones (SRS: búsqueda habitual ≤ 2 s).

Crea `mnemosine_test`, inserta un catálogo sintético de 10.000 canciones con
permisos representativos, mide los tiempos de las consultas/búsquedas y del
endpoint /api/library?q= (EXTEND incluso la consulta COUNT y la página
profunda). Al terminar, elimina la base de prueba; la base `mnemosine` no se toca.

Uso desde backend: python -m scripts.verify_perf
"""

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
os.environ["DB_NAME"] = "mnemosine_test"
os.environ["STORAGE_ROOT"] = str(ROOT / "storage")  # solo lectura para el pool; no escribe archivos

RESULTS: list[tuple[str, float, bool]] = []


def record(label: str, seconds: float, threshold: float) -> None:
    ok = seconds <= threshold
    RESULTS.append((label, seconds, ok))
    print(f"  {'ok  ' if ok else 'FALLO'} {label}: {seconds * 1000:.1f} ms (umbral {threshold * 1000:.0f} ms)")


def docker_sql(sql: str) -> None:
    subprocess.run(
        ["docker", "compose", "exec", "-T", "db", "sh", "-c", 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD"'],
        input=sql.encode("utf-8"),
        check=True,
        cwd=ROOT,
        capture_output=True,
    )


def timed(cursor, sql: str, params: tuple) -> float:
    start = time.perf_counter()
    cursor.execute(sql, params)
    cursor.fetchall()
    return time.perf_counter() - start


def main() -> int:
    print("== Preparando base de datos de prueba ==")
    docker_sql(
        "DROP DATABASE IF EXISTS mnemosine_test; "
        "CREATE DATABASE mnemosine_test CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci; "
        "GRANT ALL PRIVILEGES ON mnemosine_test.* TO 'mnemosine_app'@'%'; FLUSH PRIVILEGES;"
    )
    try:
        subprocess.run(
            [sys.executable, "-m", "scripts.migrate"],
            cwd=BACKEND,
            check=True,
            env={**os.environ},
            capture_output=True,
        )

        from app.repositories import db as repos_db
        from app.security import passwords

        admin_password = "admin-demo-password-1"
        with repos_db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO USER_ACCOUNT (username, email, password_hash, role) "
                "VALUES (%s, %s, %s, 'ADMIN')",
                ("perf", "perf@example.test", passwords.hash_password(admin_password)),
            )
            admin_id = cursor.lastrowid

        print("== Insertando 10.000 canciones sintéticas ==")
        start = time.perf_counter()
        with repos_db.transaction() as cursor:
            for index in range(50):
                cursor.execute("INSERT INTO ARTIST (name) VALUES (%s)", (f"Artista {index:03d}",))
            for index in range(200):
                cursor.execute("INSERT INTO ALBUM (title, release_year) VALUES (%s, %s)", (f"Álbum {index:04d}", 2000 + index % 26))
            track_rows = []
            location_rows = []
            for i in range(10000):
                artist_id = (i % 50) + 1
                album_id = (i % 200) + 1
                title = f"Canción {i:05d}"
                if i % 1000 == 0:
                    title = f"Sonido {i:05d}"
                track_rows.append((title, 180 + (i % 40) * 3, (i % 12) + 1, album_id))
                location_rows.append((None, admin_id, 9001, f"perf/{i:05d}.mp3",
                                      "a" * 64, 4_000_000 + (i * 7919) % 40_000_000, "audio/mpeg",
                                      "PUBLIC" if i % 10 == 0 else "PRIVATE", "AVAILABLE"))
            for i in range(0, 10000, 500):
                cursor.executemany(
                    "INSERT INTO TRACK (title, duration_seconds, track_number, album_id) VALUES (%s, %s, %s, %s)",
                    track_rows[i:i + 500],
                )
            cursor.execute("SELECT track_id FROM TRACK ORDER BY track_id")
            track_ids = [row["track_id"] for row in cursor.fetchall()]
            assert len(track_ids) == 10000
            for i in range(0, 10000, 500):
                cursor.executemany(
                    "INSERT INTO TRACK_ARTIST (track_id, artist_id, position, role) VALUES (%s, %s, 1, 'MAIN')",
                    [(track_ids[j], (j % 50) + 1) for j in range(i, min(i + 500, 10000))],
                )
                cursor.executemany(
                    "INSERT INTO TRACK_LOCATION (track_id, owner_user_id, source_id, relative_path, sha256, "
                    "size_bytes, mime_type, visibility, availability) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    [(track_ids[j], *location_rows[j][1:]) for j in range(i, min(i + 500, 10000))],
                )
        inserted_in = time.perf_counter() - start
        print(f"  inserts: {inserted_in:.1f} s")

        with repos_db.read_only() as cursor:
            cursor.execute("SELECT COUNT(*) AS n FROM TRACK")
            print(f"  TOTAL TRACK = {cursor.fetchone()['n']}")
            cursor.execute("SELECT COUNT(*) AS n FROM TRACK_LOCATION")
            print(f"  TOTAL LOCATIONS = {cursor.fetchone()['n']}")

            library_sql = (
                "SELECT l.location_id, t.track_id, t.title, t.duration_seconds, "
                "       GROUP_CONCAT(DISTINCT ar.name ORDER BY ta.position SEPARATOR ', ') AS artists, "
                "       a.title AS album "
                "FROM TRACK_LOCATION l JOIN TRACK t ON t.track_id = l.track_id "
                "LEFT JOIN ALBUM a ON a.album_id = t.album_id "
                "JOIN TRACK_ARTIST ta ON ta.track_id = t.track_id JOIN ARTIST ar ON ar.artist_id = ta.artist_id "
                "WHERE l.owner_user_id = %s"
            )
            record("conteo biblioteca (COUNT(DISTINCT))", timed(cursor,
                f"SELECT COUNT(DISTINCT l.location_id) AS n FROM TRACK_LOCATION l WHERE l.owner_user_id = %s",
                (admin_id,)), 2.0)
            record("búsqueda por título (‘Canción 00042’)", timed(cursor,
                library_sql + " AND LOCATE(%s, t.title) > 0 GROUP BY l.location_id, t.track_id, t.title, t.duration_seconds, a.title ORDER BY l.location_id DESC LIMIT 24",
                (admin_id, "Canción 00042")), 2.0)
            record("búsqueda parcial (‘Sonido’)", timed(cursor,
                library_sql + " AND LOCATE(%s, t.title) > 0 GROUP BY l.location_id, t.track_id, t.title, t.duration_seconds, a.title ORDER BY l.location_id DESC LIMIT 24",
                (admin_id, "Sonido")), 2.0)
            record("búsqueda por artista", timed(cursor,
                library_sql + " AND LOCATE(%s, ar.name) > 0 GROUP BY l.location_id, t.track_id, t.title, t.duration_seconds, a.title ORDER BY l.location_id DESC LIMIT 24",
                (admin_id, "Artista 001")), 2.0)
            record("búsqueda por álbum", timed(cursor,
                library_sql + " AND (a.title IS NOT NULL AND LOCATE(%s, a.title) > 0) GROUP BY l.location_id, t.track_id, t.title, t.duration_seconds, a.title ORDER BY l.location_id DESC LIMIT 24",
                (admin_id, "Álbum 0007")), 2.0)
            record("página profunda (página 400, 25 por página)", timed(cursor,
                library_sql + " GROUP BY l.location_id, t.track_id, t.title, t.duration_seconds, a.title ORDER BY l.location_id DESC LIMIT 25 OFFSET 9975",
                (admin_id,)), 2.0)

        print("== Medición vía HTTP (incluye sesión, SQL y JSON) ×5, mediana ==")
        from fastapi.testclient import TestClient
        import statistics

        from app.main import app

        client = TestClient(app)
        login = client.post("/api/auth/login", json={"identity": "perf", "password": admin_password})
        assert login.status_code == 200
        for label, params in [
            ("GET /api/library?q=Canción 00042", {"q": "Canción 00042"}),
            ("GET /api/library?q=Artista 001", {"q": "Artista 001"}),
            ("GET /api/library?page=400", {"page": 400, "page_size": 25}),
        ]:
            samples = []
            for _ in range(5):
                start = time.perf_counter()
                response = client.get("/api/library", params=params)
                elapsed = time.perf_counter() - start
                assert response.status_code == 200
                samples.append(elapsed)
            record(label, statistics.median(samples), 2.0)
    finally:
        print("== Eliminando base de datos de prueba ==")
        docker_sql("DROP DATABASE IF EXISTS mnemosine_test;")

    failures = sum(1 for _, _, ok in RESULTS if not ok)
    print()
    if failures:
        print(f"Rendimiento: {failures} medición(es) superaron el umbral.", file=sys.stderr)
        return 1
    print(f"Rendimiento: {len(RESULTS)} mediciones dentro del umbral del SRS (≤ 2 s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
