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

## Fase 4 — Compartición, descubrimiento, revocación y listas (H4)

- `0008` (AUTHORIZATION_DECLARATION) + `0009` (fuente central) + **`0010`**:
  `PLAYLIST_TRACK.position` pasa a INT con signo para reordenar con posiciones
  temporales negativas en una transacción (CHECK ajustado; DER actualizado).
- Permisos de copia solo del dueño: `GET/POST /api/locations/{id}` (publicar/
  despublicar con declaración `PUBLICATION` asociada a la copia;
  `public_download_allowed` con declaración `DOWNLOAD`; compartir por
  destinatario con streams/descarga y declaración; revocar en caliente;
  `PERMISSION_AUDIT` en todas; re-conceder reactiva con nuevos flags).
- Descubrimiento con sesión: `GET /api/discovery` (cuentas con copias PUBLIC
  disponibles) y `GET /api/discovery/{username}` (solo PUBLIC; descarga pública
  solo con `public_download_allowed`); `GET /api/library/shared` (compartidas
  conmigo). PUBLIC nunca implica anónimo.
- Entrega unificada propia/compartida/pública en `services/copies.py`
  (preferencia propia > compartida > pública; MISSING escribe y se salta la
  copia; rangos verifican disco en cada solicitud).
- Detalle visible sin copia propia cuando hay acceso (PUBLIC o share); el
  SHA-256 solo se muestra al dueño.
- Listas privadas ordenadas: CRUD + añadir/quitar/reordenar atómico (CHECK ≥ 1
  visible; temporales negativos permitidos por 0010); borrado de la lista no
  borra canciones; solo el dueño lee/modifica.
- Verificación: `scripts/verify_sharing` — **37/37** sobre `mnemosine_test`
  (declaraciones obligatorias, PUBLISH/UNPUBLISH con audit, descubrimiento,
  descarga pública autorizada, share + revocación en caliente, ADMIN sin
  privilegios de contenido, listas, no-borrado físico). Sin regresiones:
  `verify_journey` 23/23, `verify_isolation` 26/26, `verify_schema` 11/11.
- Frontend: nav con Mi biblioteca / Descubrir / Listas; sección «Compartidas
  contigo»; Descubrir + Colección pública (descarga solo con autorización); Listas
  (crear, renombrar, eliminar, ordenar con subir/bajar, añadir desde la
  biblioteca y por detalle); panel de permisos en el detalle (declaraciones,
  compartir/revocar, descarga pública). `npm run build` correcto (47 módulos).
- Backend en vivo: 27 rutas; `uvicorn --reload` NO recargó los cambios sobre
  OneDrive en este equipo — conviene arrancarlo sin `--reload` y reiniciarlo
  al editar.

## Incidencia: página en blanco (17/11/2026)

- Síntoma: la web se veía en blanco salvo el reproductor; replicado con
  Playwright: Vue no montaba; `GET /src/assets/main.css` → 500
  (`@tailwindcss/vite:generate:serve`: «Cannot convert undefined or null to
  object»).
- Causa: `node_modules` en disco traía `@tailwindcss/vite@4.0.0` con
  `@tailwindcss/node`/`oxide@4.3.5` (el árbol quedó desalineado respecto al
  lock tras operaciones locales de npm).
- Solución: alinear la familia Tailwind a **4.3.5** (`tailwindcss` +
  `@tailwindcss/vite` en package.json y lock); `npm run build` y dev server
  correctos; `npm ls` sin marcas `invalid`.
- También: `uvicorn --reload` sigue sin ser fiable aquí (OneDrive); el 8000
  se cayó con un fallo de terminal y se rearranca manualmente sin `--reload`.
- `@playwright/test` queda como dependencia dev (D11, e2e en H6); jsdom
  temporal retirado.

## Fase 5 — Fuentes, escaneos, disponibilidad y administración (H5)

- `0011_fuente_scan_device.sql`: dispositivo lógico «Servidor de fuentes» para
  fuentes registradas por el administrador (la fuente central 9001 sigue para
  cargas).
- Refactor: sonda de audio compartida (`services/audio.py`: probe + etiquetas
  fáciles de mutagen) y catálogo compartida (`services/catalog.py`); sin
  duplicar lógica entre carga y escaneo.
- Fuentes (`POST/GET /api/admin/sources`): rutas RELATIVAS a `SCAN_ROOT`
  (por defecto `<repo>/storage`); rechazan absolutas, unidades y `..` (422).
  Crear la fuente valida la carpeta; desconexión vía `POST .../status`
  (conserva el catálogo).
- Escaneo (`POST .../scan` → 202 + hilo de fondo; `GET /api/admin/scan-jobs/{id}`):
  propietario EXPLÍCITO obligatorio (D7); etiquetas fáciles de mutagen para
  título/artista/álbum/pista (fallback: nombre de archivo y «Desconocido»);
  SHA-256, tamaño, MIME real; transacción por archivo; FALLOS por archivo no
  abortan el lote; contadores y `FILE_OPERATION(SCAN)`; la disponibilidad se
  reconcilia al final (detecta MISSING restaurados).
- Reescanear NO duplica rutas ni cambia dueños/permisos
  (UNIQUE(source_id, relative_path)) — verificado 0 añadidas/2 omitidas en la
  segunda pasada.
- Disponibilidad: borrar el archivo → MISSING; restaurarlo → AVAILABLE; la
  fuente desconectada conserva el catálogo y rechaza escaneos (422).
- Administración completa: `GET /api/admin/operations` (filtro UPLOAD/DOWNLOAD/
  SCAN, paginado) y `GET /api/admin/permission-audit` (paginado); cambio de rol
  `POST /api/admin/users/{id}/role` (ROLE_CHANGE auditado; no puedes cambiar tu
  propio rol); moderación `POST /api/admin/locations/{id}/unpublish`
  (despublica cualquier copia PUBLIC, auditada como UNPUBLISH).
- Verificación: `scripts/verify_phase5` — **24/24** (fuente, escapes rechazados,
  escaneo completo, reescaneo idempotente, MISSING/AVAILABLE, catálogo
  conservado, operaciones/auditoría, roles auditados, moderación, USER sin
  acceso al panel). Sin regresiones: journey 23/23, sharing 37/37.
- Frontend: `/admin` con 4 pestañas (Cuentas, Fuentes y escaneos con progreso
  en vivo y elección de propietario, Operaciones, Auditoría); visible solo para
  ADMIN; `npm run build` correcto (48 módulos); nav con enlace de administración
  solo para ADMIN.
- Modo `uvicorn --reload` sigue sin ser fiable (OneDrive): el proceso de
  desarrollo se reinicia manualmente sin `--reload`.

## Incidencias de Fase 5 reportadas por el usuario y corregidas (17/11/2026)

1. **«Intento activar las cuentas y no ocurre nada»**: todas las cuentas estaban
   activas; la vista las mostraba desactivadas porque `UserOut` no incluía
   `is_active` (undefined → «Desactivada»). Corregido (`schemas/auth.py`) y
   commiteado con la app; el panel cambia a Activar/Desactivar correctamente.
2. **«Las copias escaneadas aparecen no disponibles»**: el escaneo guardaba
   `relative_path` sin el prefijo de la fuente, por lo que la entrega las daba
   por inexistentes y las marcaba `MISSING` al primer intento de reproducción.
   Corregido: las copias importadas referencian rutas relativas a la raíz de
   audio **con el prefijo de la fuente**; migración `0012_prefijo_origen_copias.sql`
   reescribe las rutas ya importadas en bases existentes. Tras el arreglo, un
   reescaneo restaura la disponibilidad. Ya NO existe `SCAN_ROOT`: las fuentes
   deben vivir dentro de `storage_root` (misma raíz servible por la entrega).
3. **«Quiero el detalle de los escaneos (nombres, duración, etc.)»**: nueva tabla
   `SCAN_JOB_FILE` (migración `0013_informe_escaneo.sql`) con ruta, resultado
   (`ADDED`/`SKIPPED`/`MISSING`/`FAILED`), track, título, artista, álbum y
   duración. Panel de administración: botón «Ver detalle» en cada fuente con
   historial; endpoints `GET /api/admin/scan-jobs` y
   `GET /api/admin/scan-jobs/{id}/files`.
4. Verificación: `verify_phase5` ampliado a **29/29** (informe ADDED/SKIPPED/
   MISSING incluido). Reparación de disponibilidad tras restaurar un archivo
   revalidada. Docker hubo que levantarlo de nuevo tras un cierre inesperado;
   todas las verificaciones re-ejecutadas y en verde.

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
