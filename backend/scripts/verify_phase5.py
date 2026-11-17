"""Verificación de la Fase 5 (H5): fuentes, escaneos y administración.

Crea `mnemosine_test` con un scan_root temporal, migra, crea admin e invita a A,
crea una fuente con 2 WAV sintetizados, escanea y comprueba: alta, reescaneo sin
duplicados, disponibilidad MISSING/AVAILABLE tras borrar/restaurar, fuente
desconectada, registro de operaciones, cambio de rol ADMIN y moderación (unpublish).

Uso desde backend: python -m scripts.verify_phase5
"""

import io
import math
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
STORAGE_TMP = tempfile.mkdtemp(prefix="mnemosine_test_storage_")
SCAN_TMP = tempfile.mkdtemp(prefix="mnemosine_test_scan_")

os.environ["DB_NAME"] = "mnemosine_test"
os.environ["STORAGE_ROOT"] = STORAGE_TMP
os.environ["SCAN_ROOT"] = SCAN_TMP

RESULTS: list[tuple[str, bool]] = []


def check(label: str, condition: bool) -> None:
    RESULTS.append((label, bool(condition)))
    print(f"  {'ok   ' if condition else 'FALLO'} {label}")


def docker_sql(sql: str) -> None:
    subprocess.run(
        ["docker", "compose", "exec", "-T", "db", "sh", "-c", 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD"'],
        input=sql.encode("utf-8"),
        check=True,
        cwd=ROOT,
        capture_output=True,
    )


def make_wav_bytes(freq: int) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(8000)
        frames = bytearray()
        for index in range(8000):
            sample = int(0.25 * 32767 * math.sin(2 * math.pi * freq * index / 8000))
            frames += struct.pack("<h", sample)
        handle.writeframes(bytes(frames))
    return buffer.getvalue()


def main() -> int:
    scan_dir = Path(SCAN_TMP) / "biblioteca-demo"
    scan_dir.mkdir(parents=True)
    (scan_dir / "tono-a.wav").write_bytes(make_wav_bytes(440))
    (scan_dir / "tono-b.wav").write_bytes(make_wav_bytes(660))
    (scan_dir / "notas.txt").write_text("esto no es audio", encoding="utf-8")

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

        from fastapi.testclient import TestClient

        from app.main import app
        from app.repositories import db as repos_db
        from app.security import passwords

        admin_password = "admin-demo-password-1"
        with repos_db.transaction() as cursor:
            cursor.execute(
                "INSERT INTO USER_ACCOUNT (username, email, password_hash, role) "
                "VALUES (%s, %s, %s, 'ADMIN')",
                ("admin", "admin@example.test", passwords.hash_password(admin_password)),
            )
        admin = TestClient(app)
        admin.post("/api/auth/login", json={"identity": "admin", "password": admin_password})
        csrf_admin = admin.cookies.get("mnemosine_csrf")
        headers_admin = {"X-CSRF-Token": csrf_admin}
        invitation = admin.post("/api/admin/invitations", json={"expires_in_days": 7}, headers=headers_admin).json()["code"]

        a = TestClient(app)
        a.post("/api/auth/register", json={"username": "usuario.a", "email": "a@example.test",
                                           "password": "cuenta-demo-123456", "invitation_code": invitation})
        a_id = a.get("/api/auth/me").json()["id"]

        print("== Registrar fuente ==")
        crear = admin.post("/api/admin/sources",
                           json={"name": "Biblioteca demo", "base_relative_path": "biblioteca-demo"},
                           headers=headers_admin)
        check("crear fuente → 201", crear.status_code == 201)
        source_id = crear.json()["source_id"] if crear.status_code == 201 else -1
        escape = admin.post("/api/admin/sources",
                            json={"name": "Escape", "base_relative_path": "../fuera"},
                            headers=headers_admin)
        check("fuente con '..' → 422", escape.status_code == 422)
        absolute = admin.post("/api/admin/sources",
                              json={"name": "Absoluta", "base_relative_path": "C:/fuera"},
                              headers=headers_admin)
        check("fuente absoluta → 422", absolute.status_code == 422)

        print("== Escaneo (propietario explícito) ==")
        scan = admin.post(f"/api/admin/sources/{source_id}/scan",
                          json={"owner_user_id": a_id},
                          headers=headers_admin)
        check("lanzar escaneo → 202", scan.status_code == 202)
        job_id = scan.json()["scan_job_id"]

        import time
        deadline = time.time() + 60
        job = None
        while time.time() < deadline:
            job = admin.get(f"/api/admin/scan-jobs/{job_id}").json()
            if job["status"] in ("COMPLETED", "FAILED", "CANCELLED"):
                break
            time.sleep(0.3)
        check("el trabajo termina COMPLETED", job is not None and job["status"] == "COMPLETED")
        check("se encontraron 2 audios (el .txt se ignora)", job is not None and job["files_found"] == 2)
        check("se añadieron 2 copias", job is not None and job["files_added"] == 2)

        print("== Reescaneo: sin duplicados ni cambios de dueño ==")
        scan2 = admin.post(f"/api/admin/sources/{source_id}/scan",
                           json={"owner_user_id": a_id},
                           headers=headers_admin).json()
        job2_id = scan2["scan_job_id"]
        deadline = time.time() + 60
        job2 = None
        while time.time() < deadline:
            job2 = admin.get(f"/api/admin/scan-jobs/{job2_id}").json()
            if job2["status"] in ("COMPLETED", "FAILED"):
                break
            time.sleep(0.3)
        check("segundo escaneo: 0 añadidas, 2 omitidas",
              job2 is not None and job2["files_added"] == 0 and job2["files_skipped"] == 2)
        with repos_db.read_only() as cursor:
            cursor.execute(
                "SELECT COUNT(*) AS n FROM TRACK_LOCATION WHERE source_id = %s AND owner_user_id = %s",
                (source_id, a_id),
            )
            check("todas las copias pertenecen a A (sin cambios de dueño)",
                  cursor.fetchone()["n"] == 2)

        print("== Disponibilidad: borrar/restaurar ==")
        (scan_dir / "tono-a.wav").unlink()
        scan3 = admin.post(f"/api/admin/sources/{source_id}/scan",
                           json={"owner_user_id": a_id},
                           headers=headers_admin).json()
        job3_id = scan3["scan_job_id"]
        deadline = time.time() + 60
        job3 = None
        while time.time() < deadline:
            job3 = admin.get(f"/api/admin/scan-jobs/{job3_id}").json()
            if job3["status"] in ("COMPLETED", "FAILED"):
                break
            time.sleep(0.3)
        with repos_db.read_only() as cursor:
            cursor.execute(
                "SELECT relative_path, availability FROM TRACK_LOCATION WHERE source_id = %s",
                (source_id,),
            )
            availability = {row["relative_path"]: row["availability"] for row in cursor.fetchall()}
        check("tono-a.wav queda MISSING tras borrarlo", availability.get("tono-a.wav") == "MISSING")
        check("tono-b.wav sigue AVAILABLE", availability.get("tono-b.wav") == "AVAILABLE")
        (scan_dir / "tono-a.wav").write_bytes(make_wav_bytes(440))
        scan4 = admin.post(f"/api/admin/sources/{source_id}/scan",
                           json={"owner_user_id": a_id},
                           headers=headers_admin).json()
        job4_id = scan4["scan_job_id"]
        deadline = time.time() + 60
        while time.time() < deadline:
            job4 = admin.get(f"/api/admin/scan-jobs/{job4_id}").json()
            if job4["status"] in ("COMPLETED", "FAILED"):
                break
            time.sleep(0.3)
        with repos_db.read_only() as cursor:
            cursor.execute(
                "SELECT COUNT(*) AS n FROM TRACK_LOCATION WHERE source_id = %s AND availability = 'MISSING'",
                (source_id,),
            )
            check("tono-a.wav vuelve a AVAILABLE tras restaurarlo", cursor.fetchone()["n"] == 0)

        print("== Fuente desconectada conserva catálogo ==")
        off = admin.post(f"/api/admin/sources/{source_id}/status",
                         json={"status": "DISCONNECTED"}, headers=headers_admin)
        check("desconectar fuente → 200", off.status_code == 200)
        refused = admin.post(f"/api/admin/sources/{source_id}/scan",
                             json={"owner_user_id": a_id}, headers=headers_admin)
        check("escanear fuente desconectada → 422", refused.status_code == 422)
        with repos_db.read_only() as cursor:
            cursor.execute("SELECT COUNT(*) AS n FROM TRACK_LOCATION WHERE source_id = %s", (source_id,))
            check("el catálogo se conserva al desconectar", cursor.fetchone()["n"] == 2)

        print("== Operaciones y auditoría ==")
        operations = admin.get("/api/admin/operations", params={"type": "SCAN", "page": 1, "page_size": 10}).json()
        check("operaciones SCAN registradas", operations["total"] >= 1)
        audit_page = admin.get("/api/admin/permission-audit", params={"page": 1, "page_size": 10}).json()
        check("la auditoría de permisos responde", audit_page["total"] >= 0)

        print("== Cambio de rol y moderación ==")
        own_role = admin.post("/api/admin/users/1/role", json={"role": "USER"}, headers=headers_admin)
        check("admin no puede cambiar su propio rol → 400", own_role.status_code == 400)
        promote = admin.post(f"/api/admin/users/{a_id}/role", json={"role": "ADMIN"}, headers=headers_admin)
        check("A promovido a ADMIN → 200", promote.status_code == 200 and promote.json()["role"] == "ADMIN")
        demote = admin.post(f"/api/admin/users/{a_id}/role", json={"role": "USER"}, headers=headers_admin)
        check("A degradado a USER → 200", demote.status_code == 200 and demote.json()["role"] == "USER")
        with repos_db.read_only() as cursor:
            cursor.execute(
                "SELECT COUNT(*) AS n FROM PERMISSION_AUDIT WHERE action = 'ROLE_CHANGE' AND target_user_id = %s",
                (a_id,),
            )
            check("ROLE_CHANGE queda auditado", cursor.fetchone()["n"] >= 2)

        # Moderación: publicar y luego despublicar con rol ADMIN
        with repos_db.read_only() as cursor:
            cursor.execute(
                "SELECT location_id FROM TRACK_LOCATION WHERE owner_user_id = %s LIMIT 1",
                (a_id,),
            )
            location_id = cursor.fetchone()["location_id"]
        with repos_db.transaction() as cursor:
            cursor.execute(
                "UPDATE TRACK_LOCATION SET visibility = 'PUBLIC' WHERE location_id = %s",
                (location_id,),
            )
        moderate = admin.post(f"/api/admin/locations/{location_id}/unpublish", headers=headers_admin)
        check("ADMIN modera: despublica → 200",
              moderate.status_code == 200 and moderate.json()["visibility"] == "PRIVATE")
        with repos_db.read_only() as cursor:
            cursor.execute(
                "SELECT COUNT(*) AS n FROM PERMISSION_AUDIT WHERE action = 'UNPUBLISH' AND location_id = %s",
                (location_id,),
            )
            check("UNPUBLISH por moderación queda auditado", cursor.fetchone()["n"] == 1)

        print("== Aislamiento: USER no usa el panel admin ==")
        check("A (USER) no puede listar fuentes → 403", a.get("/api/admin/sources").status_code == 403)
    finally:
        docker_sql("DROP DATABASE IF EXISTS mnemosine_test;")
        shutil.rmtree(STORAGE_TMP, ignore_errors=True)
        shutil.rmtree(SCAN_TMP, ignore_errors=True)

    failures = sum(1 for _, ok in RESULTS if not ok)
    print()
    if failures:
        print(f"Verificación H5: {failures} fallo(s) de {len(RESULTS)} comprobaciones.", file=sys.stderr)
        return 1
    print(f"Verificación H5: {len(RESULTS)} comprobaciones correctas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
