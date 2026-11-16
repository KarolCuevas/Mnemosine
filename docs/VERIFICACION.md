# Verificación de la base, Fase 1 y Fase 2

Fecha: 16 de noviembre de 2026.

## Entorno

- Docker reparado por el usuario (WSL); `mnemosine-db-1` healthy (MySQL 8.4.13,
  127.0.0.1:3307).

## Fase 1 — Base de datos y migraciones

- Ejecutor `scripts.migrate`: corregido un fallo de lectura de filas en
  `GET_LOCK`/`RELEASE_LOCK` ("Unread result found"). Tras el arreglo, dry-run,
  aplicación real, segunda ejecución idempotente (0 pendientes) y detección de
  alteraciones por checksum funcionan.
- Migraciones 0001–0008 aplicadas; `scripts.check_db`: conexión OK, 19 tablas.
- `scripts.verify_schema`: 11 comprobaciones correctas contra MySQL real en una
  transacción revertida (UNIQUE, FK RESTRICT, CHECKs, ENUMs).
- Seeds sintéticos aplicados (1 dispositivo, 1 fuente, 2 artistas, 2 álbumes,
  4 canciones). Sin usuarios ni audio.
- Adaptador de almacenamiento local: ciclo save→commit→stream con offset/length,
  no-sobrescritura, límite de tamaño, recuperación de temporales (pruebas ad hoc en verde).

## Fase 2 — Cuentas y aislamiento (con ajustes D4, D8, D13)

- `0008_autorizacion_copia.sql`: `AUTHORIZATION_DECLARATION` (PUBLICATION/DOWNLOAD,
  ligada a TRACK_LOCATION) y `TRACK_LOCATION.public_download_allowed`. Ajuste D8.
- Sesiones: cookie `mnemosine_session` HttpOnly + SameSite=Lax + `Secure` según
  `SESSION_COOKIE_SECURE`; CSRF por doble envío con HMAC (`mnemosine_csrf` /
  `X-CSRF-Token`); expiración deslizante 7 d y límite absoluto 30 d
  (`SESSION_SLIDING_DAYS`/`SESSION_ABSOLUTE_DAYS`); desactivación revoca sesiones
  en caliente. Ajuste D4.
- Registro por invitación de un solo uso (hash SHA-256 del código), roles
  USER/ADMIN, hashing argon2 (D5); primer ADMIN por `scripts.create_admin`.
- Admin sin bypass de contenido: el servicio de permisos (`services/permissions.py`)
  no recibe el rol; matriz revisada — descarga pública autorizada y shares
  aplican igual a un ADMIN que a cualquier usuario. Ajuste matriz.
- `scripts/verify_permissions`: 13 escenarios correctos (dueño, PUBLIC, shares,
  MISSING/ERROR, admin sin bypass/con dueño/con share).
- `scripts/verify_isolation`: **26 comprobaciones correctas** end-to-end con
  TestClient sobre una base `mnemosine_test` temporal (creada, migrada y
  eliminada en el propio script; la base `mnemosine` no se toca). Cubre: health,
  registro (invitación inválida, contraseña corta, 201, auto-login, invitación
  no reutilizable), CSRF (403 sin token, logout 200), aislamiento por rol
  (403 USER en /api/admin/*, admin 200), cierre/reapertura de sesión,
  desactivación en caliente (401) y reactivación, rate limiting 429,
  auto-desactivación admin 400.
- Dependencias nuevas: `argon2-cffi`, `httpx` (solo para tests; Starlette 1.10
  avisa que TestClient pasa de httpx a httpx2 — funciona, revisar en H3/H6).
  `requirements.lock.txt` regenerado; `pip check` limpio.
- Frontend: pinia + vue-router añadidos; cliente API (cookies same-origin,
  doble envío CSRF, ApiError), store auth, router con guarda de sesión,
  vista /acceso (login + registro por invitación) y /biblioteca (estado vacío +
  logout). `npm run build` correcto.
- Backend en vivo (uvicorn): `/api/health` 200; rutas expuestas:
  /api/auth/{register,login,logout,me}, /api/admin/{invitations,users,...}.
- Sin revisión visual en navegador.

## Pendiente

- Fase 3: carga privada, biblioteca, búsqueda y reproductor (H3).
- Decisiones con efecto en H3 ya aprobadas: D3 (formatos/límites), D11 (Playwright),
  D12 (Pinia), D13 (mutagen para lectura técnica del audio).
- Contraseña de los usuarios A/B/admin de la base de desarrollo: la base real
  `mnemosine` no contiene cuentas todavía; crea la primera con
  `python -m scripts.create_admin`.
