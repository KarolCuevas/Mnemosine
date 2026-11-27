# Verificación de la base, Fase 1 y Fase 2

## Integraciones — 25 de noviembre de 2026

Primera entrega del plan: I0, bases de I1 e I5. No equivale a aceptar las fases
Drive I2–I4 ni la entrega integrada I6. Detalle en [INTEGRACIONES.md](INTEGRACIONES.md).

- `unittest discover`: **8 pruebas correctas** (lista blanca de metadatos, ediciones,
  escape de búsquedas, cursores firmados, 401/403/404/429/5xx, Retry-After,
  compatibilidad de rutas y temporales locales).
- `scripts.verify_integrations`: **45 comprobaciones correctas** sobre una base
  MySQL única y temporal: migración 0013→0015 sin cambiar ruta/hash/dueño,
  idempotencia, búsqueda/caché/índice, referencia privada A/B/admin, CSRF,
  refresh, colección sin audio, bloqueo compartido entre procesos, carga inválida,
  cuota con dos cargas simultáneas, fuente desconectada y módulo de solo lectura
  usado por inventario y entrega comunes. Se simula HTTP externo en esta suite.
- Regresión: permisos **13 escenarios**, aislamiento **26**, recorrido H3 **30**,
  compartición H4 **37**, fuentes H5 **29**, todos correctos.
- `npm run build`: correcto (51 módulos).
- Playwright: **2 pruebas correctas**; login/logout real contra API de prueba y
  referencias con respuestas de catálogo controladas: búsqueda explícita, guardar,
  consultar/quitar de colección, aviso de 429 y recuperación. Sin errores de página.
- Capturas de escritorio y móvil 390×844 revisadas. Sin desbordamiento horizontal;
  referencias sin botones de audio y sin barra vacía. El reproductor de la biblioteca
  puede seguir visible si hay una canción propia seleccionada.
- Prueba externa real: búsqueda `Clair de lune` / `Claude Debussy`, cinco registros
  de MusicBrainz indexados. Lookup real del MBID
  `bfb01dcd-7001-4164-9173-4db504600896` correcto (una edición conocida).
  El primer lookup agotó su timeout; una repetición posterior respondió correctamente.
- Configuración local: MusicBrainz habilitado con `czmprojects@gmail.com` en `.env`
  excluido de Git; `.env.example` lo deja desactivado para otras instalaciones.
- Respaldo previo: `backups/integrations-before-0014/20261125-231531`, 20 tablas,
  12 archivos, 90.228.542 bytes. Restauración verificada en base separada
  `mnemosine_restore_i0_b2b119`; script existente comprobó checksum del dump,
  conteos de filas y cantidad de archivos (no una comparación byte a byte del audio).
- Migraciones 0014 y 0015 aplicadas al MySQL local tras esa restauración de prueba.

Pendiente: Google Cloud, OAuth/Picker, credenciales cifradas, adaptador y trabajador
Drive, copias remotas/recuperación y aceptación con dos cuentas reales. Las advertencias
de deprecación de Starlette/TestClient siguen presentes; no impidieron las pruebas.

---

Las secciones siguientes son el registro histórico de H1–H6; sus pendientes deben
leerse con la fecha de cada fase.

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

## Fase 6 — Validación y entrega (H6)

- Rendimiento con 10.000 canciones (`scripts.verify_perf`): la COUNT tenía un
  plan pésimo (join temprano + ref=const, ~2,1 s); reescrita con EXISTS
  (cierre al primer match, ~80 ms) y `ORDER BY location_id DESC` (índice).
  Todas las mediciones bajo el umbral SRS (≤ 2 s): SQL entre 5–77 ms; vía HTTP
  (×5, mediana): búsqueda por título 208 ms, artista 160 ms, página profunda 131 ms.
  La biblioteca devuelve resultados en ~60–200 ms; el objetivo del SRS se cumple.
- Respaldo verificado de punta a punta: `scripts.backup` (mysqldump + audio +
  manifiesto con COUNT(*) exacto por tabla y sha256 del dump) →
  `scripts.restore` verifica sha256, replica en `mnemosine_restore` nuevo y
  compara **los 20 conteos y los 12 archivos de audio** con el manifiesto →
  «RESTAURACIÓN VERIFICADA». Antes, el manifiesto usaba
  information_schema.TABLE_ROWS (estimado) y daba falsos «DIFIERE»; corregido.
- Migración `0012`/`0013` aplicadas en este equipo; `check_db` reporta 20 tablas.
- Journey: añadida la sección «dos usuarios, mismos bytes» (permisos
  independientes, copias independientes, hash idéntico) → **30/30**.
- e2e con Playwright (D11): entorno temporal aislado (mnemosine_e2e :8010/:5174)
  con login → /biblioteca → logout → /acceso, sin errores de página.
  `python -m scripts.e2e` orquesta y limpia todo al terminar.
- Documentación: `docs/MANUAL.md` (recorrido completo) y `docs/DESPLIEGUE.md`
  (HTTPS con Caddy/nginx, `SESSION_COOKIE_SECURE`, checklist de publicación,
  actualización).
- Limitación conocida y documentada: la DDL de migraciones no promete rollback
  transaccional (commit implícito de MySQL); el ejecutor se detiene ante fallos.

## Rediseño UX/UI — 27 de noviembre de 2026

- Estructura común de navegación: lateral en escritorio y desplegable en móvil;
  el contenido ocupa el ancho disponible y el reproductor tiene su propia fila,
  sin tapar controles al final de las páginas.
- Biblioteca con lista/tarjetas, búsqueda, reintento de errores y estados vacíos;
  acceso, carga, listas, descubrimiento, referencias y detalle con el mismo tema.
- Tablas de administración con desplazamiento dentro de su región, menú usable
  con teclado, foco al navegar, respeto de movimiento reducido y controles de
  formulario de 16 px en móvil.
- `npm run build`: correcto. `python -m scripts.e2e`: **13/13 pruebas**.
  Incluye acceso real contra `mnemosine_e2e` y las referencias existentes.
  La base temporal se elimina al finalizar; la biblioteca real no se modifica.
- Nueva suite `frontend/e2e/ui.spec.js`: nueve pantallas a **320, 390, 768, 1024,
  1440, 1920 y 2560 px**, sin desbordamiento horizontal de la página ni del
  contenido, y sin superposición del reproductor. Capturas revisadas en Chromium.
  Los datos de biblioteca y las respuestas de subida de esta suite son sintéticos;
  la reproducción utiliza un WAV de prueba y el elemento de audio del navegador.
- Interacciones comprobadas: menú móvil por teclado, creación de listas, búsqueda,
  vista de tarjetas, registro y subida, errores/reintento, canción correcta cuando
  hay archivos no disponibles, persistencia al navegar y parada al cerrar sesión.

## Pendiente

- Aceptación visual en el dispositivo habitual del usuario; la matriz de tamaños
  anterior ya se verificó en Chromium, pendiente contraste en otros navegadores.
- Commit y push de Fase 6 (pendiente de tu ok: `main` va por delante de origin).
- La decisión D11 (Playwright) ya tiene su primer e2e; H6 deja el terreno para
  la suite completa.


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

## Integraciones y preparación de Google — 27/11/2026

- `python -m unittest discover -s ../tests/unit -p test_integrations.py -v`:
  **8/8 correctas**. La primera ejecución tuvo una restricción de permisos al
  crear un enlace duro temporal; la ejecución con los permisos necesarios pasó.
- `python -m scripts.verify_integrations`: **45/45 comprobaciones correctas**
  después de que el usuario encendiera Docker. Verifica migraciones, catálogo,
  referencias privadas entre A/B/ADMIN, CSRF, caché, límites, cuota concurrente,
  archivos locales y adaptador de solo lectura. Crea una base única y audio
  temporal, y elimina sus propios datos al terminar; no altera la biblioteca real.
- La suite usa respuestas simuladas del proveedor externo. Estos resultados no
  representan pruebas reales de OAuth, Picker ni almacenamiento de Google Drive.
- Consola del proyecto `mnemosine-516014`: Drive API y Picker API habilitadas,
  audiencia externa en pruebas y las dos cuentas piloto presentes. Se conservó
  la tercera cuenta de prueba que ya existía.
- La lista de alcances estaba vacía. Se declaró únicamente `drive.file` y Google
  confirmó que se guardaron los cambios. No se concedió acceso a archivos de
  ninguna cuenta durante esta revisión.
- JSON OAuth de Descargas: proyecto, tipo web, presencia de credenciales, origen
  `http://127.0.0.1:5173` y retorno
  `http://127.0.0.1:5173/api/integrations/google_drive/callback` comprobados.
  No se intercambió ningún código por tokens.
- Con autorización explícita del usuario se creó `Mnemosine Picker desarrollo`.
  Tras recargar la consola se comprobaron las restricciones: Google Picker API,
  `http://127.0.0.1:5173/*` y `https://docs.google.com/*`.
- Al terminar esa revisión quedaban pendientes I2/I3 y la aceptación real A/B.
  La implementación posterior de I2 se documenta a continuación; la preparación
  de Google por sí sola no acredita estos recorridos.

## Conexiones Google implementadas — 27/11/2026

- **5/5** pruebas unitarias en `tests/unit/test_google_drive.py`: cifrado ligado
  al propietario, alteración de ciphertext, rotación de claves, límites HTTP,
  errores sanitizados, revocación idempotente y metadatos malformados.
- **71/71** comprobaciones de `python -m scripts.verify_google_drive`: MySQL real
  temporal, Google simulado y tres usuarios A/B/ADMIN. Comprueban state/PKCE,
  expiración, uso único, sesión concreta, cierre de sesión durante OAuth, alcance
  exacto, identidad al reconectar, privacidad sin bypass de ADMIN, renovación
  serializada, revocación fallida/reintento, selección idempotente incluso al
  límite, rechazo de IDs no accesibles y restauración sin reactivar credenciales.
  La base y archivos de la prueba se eliminan al terminar.
- **45/45** comprobaciones de `scripts.verify_integrations` correctas después
  de introducir 0016: migraciones anteriores, catálogo, referencias, aislamiento,
  almacenamiento local y adaptador de solo lectura.
- **14/14** pruebas de interfaz en `scripts.e2e`, incluida la nueva prueba de
  Drive: carga del selector solo al elegir, token temporal fuera del almacenamiento
  del navegador, IDs revalidados por el servidor, cancelación de desconexión,
  solicitud de reconexión y desconexión. Google/Picker simulados; inicio de sesión
  contra MySQL temporal. Capturas de Drive en escritorio y móvil revisadas.
- `npm run build` correcto. Estas suites no conectan cuentas reales de Google,
  no validan bytes remotos y no prueban reproducción ni transferencia de Drive.
- Configuración local instalada en `backend/.secrets/`, excluida de Git, con
  cliente OAuth del proyecto, clave restringida de Picker y clave independiente
  de cifrado. `GOOGLE_DRIVE_ENABLED=true`; origen `http://127.0.0.1:5173`.
- Antes de aplicar 0016 se detuvo el servidor y se creó el respaldo
  `backups/google-before-0016/20261127-155547`: **25 tablas**, dump de **59.998
  bytes**, **12 archivos de audio / 90.228.542 bytes**. Prefijo SHA-256 del dump:
  `68fd607fb69da2c7`. Se conservó el respaldo; no se hizo una restauración sobre
  la biblioteca real.
- Migración 0016 aplicada a `mnemosine`. Se compararon con el manifiesto los
  conteos de todas las tablas anteriores; coinciden, salvo el incremento esperado
  de una migración registrada. Las nuevas conexiones estaban vacías.
- API 0.6.0 reiniciada en `127.0.0.1:8000`, Vite disponible en `127.0.0.1:5173`.
  Endpoint protegido devuelve 401 sin sesión. Callback con valores ficticios
  devuelve 303 al destino fijo, sin caché; se comprobó que el log de Uvicorn
  contiene la ruta pero no el código ni el estado ficticios.
- **Pendiente manual:** entrar en Mnemosine, autorizar Google A, elegir un audio
  de prueba y repetir con B desde otra cuenta de Mnemosine. Hasta observar ambos
  recorridos, I2 no tiene aceptación real completa. I3/I4 siguen pendientes.

## Etiquetas y portadas en la subida — 27/11/2026

- Corregida la carga que solo guardaba el formulario: las nuevas subidas importan
  etiquetas y portada incrustadas. Los valores manuales tienen prioridad y los
  campos vacíos usan el audio. Título/artista dejan de ser obligatorios.
- `scripts.verify_media`: **54/54** comprobaciones con FLAC, MP3, M4A, OGG y WAV
  sintéticos generados con FFmpeg. Subida real sin formulario, varios artistas,
  álbum, artista del álbum, género, pista, disco y año, portada JPEG legible,
  audio original íntegro y SHA-256 idéntico. También comprueba correcciones
  manuales, ausencia de etiquetas, portada dañada, rechazo de audio falso y
  compensación de una transacción fallida sin archivos ni filas residuales.
- Portadas protegidas: A/B/ADMIN, anónimo, share solo de descarga, revocación,
  publicación y vuelta a privado, desactivación de cuenta, biblioteca propia,
  compartidas, descubrimiento y listas. No se otorga acceso extra a ADMIN.
- **23/23** pruebas unitarias, incluidas **10** nuevas de metadatos: ID3 en WAV
  real, MP4, Vorbis/FLAC/OGG, carátula frontal, límites, Unicode, números,
  imágenes inválidas y eliminación de EXIF. `scripts.verify_journey`: **30/30**.
- `scripts.e2e`: **15/15** pruebas en Chromium. La prueba nueva sube un WAV
  etiquetado contra la API y MySQL temporales, verifica el resultado, detalle,
  biblioteca, cuadrícula y reproductor con imágenes cargadas, también a 320 px.
  La suite de diseño conserva las comprobaciones entre 320 y 2560 px. Capturas
  revisadas en escritorio y móvil. E2E ahora aísla también el almacenamiento,
  genera su audio de prueba y detiene el árbol de procesos en Windows; rechaza
  puertos de prueba ocupados para evitar usar servidores antiguos.
- `npm run build`, `pip check` y `git diff --check`: correctos. Migración 0017
  aplicada en la base local; comprobación de tablas correcta. API reiniciada y
  comprobada: portada disponible como ruta protegida y solo el archivo requerido
  en el formulario de subida.
- No se reprocesaron canciones anteriores ni se consultaron catálogos externos.
  La importación de audio desde Drive continúa su plan separado; esta prueba
  verifica la carga de archivos locales en el servidor.

Reproducir desde `backend`: `python -m unittest discover -s ../tests/unit -v`,
`python -m scripts.verify_media`, `python -m scripts.verify_journey` y
`python -m scripts.e2e`. `verify_media` requiere FFmpeg en PATH o la variable
`MEDIA_TEST_FFMPEG`; es una herramienta de pruebas, no una dependencia de la app.

## Preparación de publicación — 27/11/2026

- `npm run build` y las **23 pruebas unitarias anteriores** correctas.
- Añadidas **3 pruebas de entrega web**: navegación directa de Vue, caché de
  assets, 404 para API desconocida/archivos privados y rechazo de métodos no
  admitidos. Pasan con los permisos de ejecución necesarios en este equipo.
- Imagen `mnemosine:publicacion` construida correctamente en Linux con Node 24,
  Python 3.14 y las dependencias fijadas. Contexto Docker limitado al código:
  no incluye `.env`, claves, respaldos ni biblioteca local.
- `scripts.verify_release` correcto con MySQL 8.4 y volumen desechables: las 17
  migraciones, API y Vue en el mismo puerto, proceso UID 10001, cookies Secure,
  inicio de sesión, subida WAV sintética, descarga idéntica, rangos y conservación
  de archivo/sesión tras reiniciar. Se corrigió la prueba para consultar el puerto
  aleatorio nuevo de Docker Desktop después del reinicio. Los recursos temporales
  se retiraron; los datos locales no se modificaron.
- Comprobación de archivos publicables: sin patrones de claves Google, secretos
  OAuth, tokens GitHub ni claves privadas. Esta comprobación no sustituye una
  revisión completa del historial anterior.
- El usuario eligió Railway en su prueba gratuita, sin contratar un plan. El
  despliegue remoto y el envío a GitHub aún requieren acceso a esas cuentas.
  Preparación y límites descritos en `PUBLICACION_RAILWAY.md`.
