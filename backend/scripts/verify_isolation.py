"""Pruebas de aislamiento A/B/admin contra una base de datos de prueba.

Crea `mnemosine_test` (en el mismo contenedor Docker), aplica las migraciones,
ejecuta el recorrido completo de la Fase 2 con TestClient (sin servidor) y, al
final, **borra** la base de datos de prueba. La base `mnemosine` no se toca.

Requisitos: Docker Desktop con el contenedor de MySQL levantado y el venv con
las dependencias de requirements.txt (incluye httpx).

Uso desde backend: python -m scripts.verify_isolation
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
os.environ["DB_NAME"] = "mnemosine_test"

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


def main() -> int:
    print("== Preparando base de datos de prueba (mnemosine_test) ==")
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

        admin_client = TestClient(app)
        a_client = TestClient(app)
        b_client = TestClient(app)

        print("== Salud y acceso anónimo ==")
        check("health responde ok", TestClient(app).get("/api/health").json().get("status") == "ok")
        check("/api/auth/me anónimo → 401", TestClient(app).get("/api/auth/me").status_code == 401)

        print("== Login de administrador ==")
        check("login con contraseña errónea → 401",
              admin_client.post("/api/auth/login", json={"identity": "admin", "password": "incorrecta-incorrecta"}).status_code == 401)
        login_admin = admin_client.post("/api/auth/login", json={"identity": "admin", "password": admin_password})
        check("login admin correcto → 200", login_admin.status_code == 200)
        check("la cookie mnemosine_csrf está presente", "mnemosine_csrf" in admin_client.cookies)

        print("== Invitaciones (doble envío CSRF) ==")
        resp = admin_client.post("/api/admin/invitations", json={"expires_in_days": 7})
        check("POST invitaciones sin CSRF → 403", resp.status_code == 403)
        csrf_admin = admin_client.cookies.get("mnemosine_csrf")
        headers = {"X-CSRF-Token": csrf_admin}
        resp = admin_client.post("/api/admin/invitations", json={"expires_in_days": 7}, headers=headers)
        check("POST invitaciones con CSRF → 201", resp.status_code == 201)
        invitation_a = resp.json()["code"] if resp.status_code == 201 else "x" * 12
        resp = admin_client.post("/api/admin/invitations", json={"expires_in_days": 7}, headers=headers)
        invitation_b = resp.json()["code"] if resp.status_code == 201 else "y" * 12

        print("== Registro por invitación ==")
        bad_register = a_client.post(
            "/api/auth/register",
            json={"username": "usuario.a", "email": "a@example.test",
                  "password": "cuenta-demo-123456", "display_name": "Usuario A",
                  "invitation_code": "invitacion-invalida-1234567890"},
        )
        check("registro con invitación inválida → 400", bad_register.status_code == 400)
        short_pw = a_client.post(
            "/api/auth/register",
            json={"username": "usuario.a", "email": "a@example.test",
                  "password": "corta", "invitation_code": invitation_a},
        )
        check("contraseña corta → 422", short_pw.status_code == 422)
        reg_a = a_client.post(
            "/api/auth/register",
            json={"username": "usuario.a", "email": "a@example.test",
                  "password": "cuenta-demo-123456", "display_name": "Usuario A",
                  "invitation_code": invitation_a},
        )
        check("registro de A → 201", reg_a.status_code == 201)
        check("A queda autenticado tras el registro (me → 200)", a_client.get("/api/auth/me").status_code == 200)
        check("la invitación de A no se puede reutilizar → 400",
              b_client.post(
                  "/api/auth/register",
                  json={"username": "usuario.b", "email": "b@example.test",
                        "password": "cuenta-demo-123456", "invitation_code": invitation_a}).status_code == 400)
        reg_b = b_client.post(
            "/api/auth/register",
            json={"username": "usuario.b", "email": "b@example.test",
                  "password": "cuenta-demo-123456", "display_name": "Usuario B",
                  "invitation_code": invitation_b},
        )
        check("registro de B → 201", reg_b.status_code == 201)

        a_id = a_client.get("/api/auth/me").json().get("id")

        print("== Aislamiento por rol (matriz revisada) ==")
        check("A (USER) no puede listar cuentas (admin) → 403",
              a_client.get("/api/admin/users").status_code == 403)
        check("B (USER) no puede desactivar a A → 403",
              b_client.post(f"/api/admin/users/{a_id}/deactivate",
                            headers={"X-CSRF-Token": b_client.cookies.get("mnemosine_csrf")}).status_code == 403)
        check("admin sí puede listar cuentas → 200",
              admin_client.get("/api/admin/users").status_code == 200)

        print("== Sesión y CSRF ==")
        check("logout de A sin CSRF → 403", a_client.post("/api/auth/logout").status_code == 403)
        check("logout de A con CSRF → 200",
              a_client.post("/api/auth/logout", headers={"X-CSRF-Token": a_client.cookies.get("mnemosine_csrf")}).status_code == 200)
        check("A ya no puede usar /me (sesión revocada) → 401", a_client.get("/api/auth/me").status_code == 401)
        check("A puede volver a iniciar sesión → 200",
              a_client.post("/api/auth/login", json={"identity": "usuario.a", "password": "cuenta-demo-123456"}).status_code == 200)

        print("== Desactivación de cuenta ==")
        resp = admin_client.post(
            f"/api/admin/users/{a_id}/deactivate",
            headers={"X-CSRF-Token": admin_client.cookies.get("mnemosine_csrf")},
        )
        check("admin desactiva a A → 200", resp.status_code == 200)
        check("A pierde el acceso en caliente → 401", a_client.get("/api/auth/me").status_code == 401)
        resp = admin_client.post(
            f"/api/admin/users/{a_id}/activate",
            headers={"X-CSRF-Token": admin_client.cookies.get("mnemosine_csrf")},
        )
        check("admin reactiva a A → 200", resp.status_code == 200)
        check("A puede entrar de nuevo → 200",
              a_client.post("/api/auth/login", json={"identity": "usuario.a", "password": "cuenta-demo-123456"}).status_code == 200)

        print("== Rate limiting de login ==")
        rl_client = TestClient(app)
        last_status = 0
        for _ in range(6):
            last_status = rl_client.post(
                "/api/auth/login", json={"identity": "intento-x@example.test", "password": "mala-mala-1"}
            ).status_code
        check("6 intentos fallidos seguidos → 429", last_status == 429)
        check("admin no puede desactivarse a sí mismo → 400",
              admin_client.post(
                  "/api/admin/users/1/deactivate",
                  headers={"X-CSRF-Token": admin_client.cookies.get("mnemosine_csrf")},
              ).status_code == 400)
    finally:
        print("== Eliminando base de datos de prueba ==")
        docker_sql("DROP DATABASE IF EXISTS mnemosine_test;")

    failures = sum(1 for _, ok in RESULTS if not ok)
    print()
    if failures:
        print(f"Aislamiento: {failures} fallo(s) de {len(RESULTS)} comprobaciones.", file=sys.stderr)
        return 1
    print(f"Aislamiento: {len(RESULTS)} comprobaciones correctas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
