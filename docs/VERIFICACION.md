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

## Fase 3 — Primer recorrido funcional (H3)

- Migración `0009_fuente_central.sql`: DEVICE/SOURCE «Almacenamiento central»
  (IDs fijos 9001) para asociar las copias subidas por usuarios.
- Carga de extremo a extremo (`POST /api/tracks/upload`, multipart): streaming a
  temporal, validación real (extensión + magic bytes con `filetype` + mutagen
  para contenedor/códec y duración; los renombrados se rechazan con 422), SHA-256,
  cuota 5 GB y límite 50 MB por archivo (D3), movimiento atómico
  `storage/audio/<user_id>/<uuid>.<ext>`, transacción SQL (ARTIST/ALBUM find-or-create,
  TRACK siempre nuevo, TRACK_LOCATION PRIVATE + FILE_OPERATION UPLOAD) con
  compensación si la BD falla tras publicar el archivo; recuperación de
  temporales interrumpidos.
- `GET /api/library` (paginada, búsqueda por título/artista/álbum con LOCATE,
  sin wildcards), `GET /api/tracks/{id}` (detalle propio; 404 uniforme),
  `GET /api/tracks/{id}/audio` con Range (206/416, `Accept-Ranges`,
  comprobación de existencia en disco en cada solicitud y escritura de
  disponibilidad MISSING si falta), `GET /api/tracks/{id}/download`
  (Content-Disposition attachment; FILE_OPERATION DOWNLOAD registrada — la
  recepción por el cliente no es verificable y así queda anotado).
- Permisos integrados en la entrega: resolución de copia del dueño +
  `services/permissions.can()` (servido solo al dueño en H3).
- Verificación: `scripts/verify_journey` — **23/23 comprobaciones** sobre
  `mnemosine_test` (subida WAV sintético, búsqueda, detalle, rangos,
  descarga, FILE_OPERATION, aislamiento A/B, CSRF). Base de prueba y audio
  temporal eliminados al terminar; la base `mnemosine` no se tocó.
- Frontend: BibliotecaView completa (búsqueda con debounce, lista accesible,
  estados vacíos/error/carga, paginación), CargarView (formulario + progreso
  nativo `<progress>`, título sugerido desde el nombre), DetalleView (metadatos,
  SHA-256, copias, reproducir/descargar), PlayerBar persistente (cola de la
  biblioteca, atajos por teclado con botones nativos, `<input range>` accesible,
  volumen), títulos de documento por ruta, `npm run build` correcto.
- Backend en vivo (uvicorn): health 200, `/api/auth/me` 401 sin sesión y 14 rutas
  expuestas (`/api/tracks/*`, `/api/library`).
- Sin comprobación visual en navegador; el recorrido debe validarse a ojo antes de la demo.

## Pendiente

- Demo del recorrido H3 en navegador (registro → carga → biblioteca → búsqueda →
  reproducción → descarga) como aceptación visual del usuario.
- Fase 4: compartición y visibilidad PUBLIC (publicar exige declaración
  `PUBLICATION`; descarga pública autorizada exige declaración `DOWNLOAD` +
  `public_download_allowed`), listas privadas ordenadas.
- Fase 5: fuentes, escaneos, duplicados, administración completa.
- Decisiones con efecto en H3 ya aprobadas: D3 (formatos/límites), D11 (Playwright),
  D12 (Pinia), D13 (mutagen para lectura técnica del audio).
- Contraseña de los usuarios A/B/admin de la base de desarrollo: la base real
  `mnemosine` contiene una cuenta ADMIN creada por el usuario
  (`python -m scripts.create_admin`); los usuarios A/B deben crearse por invitación
  cuando se quiera probar el aislamiento en el navegador.
