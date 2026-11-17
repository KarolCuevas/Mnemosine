# Decisiones de arranque (Fase 0) — Mnemosine

Fecha: 16 de noviembre de 2026. Estado general: **revisadas y aprobadas el
16/11/2026 con los ajustes D4, D8, D13 y la matriz de acceso indicados abajo**.
El resto se mantiene según la propuesta inicial (registro por invitación, límites
de carga y cuota, sesión, etc.).

## 1. Decisiones

| # | Tema | Decisión propuesta | Momento límite |
|---|---|---|---|
| D1 | Nombre visible en la aplicación | **Mnemosine**; el SRS conserva «Mneme» como referencia documental | Diseño de interfaz |
| D2 | Registro | **Por invitación** generada por el administrador o alta habilitada por él; sin alta pública abierta en el MVP | Autenticación (H2) |
| D3 | Formatos y límites de carga | **MP3, M4A (AAC), FLAC, OGG Vorbis, WAV**; **50 MB** por archivo; **5 GB** de cuota por cuenta; validación real del archivo (no solo extensión); compatibilidad comprobada en navegadores objetivo; los no reproducibles se documentan sin transcodificar | Cargas (H3) |
| D4 | Sesión | Cookie **HttpOnly + SameSite=Lax + Secure cuando hay HTTPS** (variable `SESSION_COOKIE_SECURE`, obligatoria tras HTTPS), token **CSRF** (doble envío con HMAC) en mutaciones, **expiración deslizante de 7 días Y límite absoluto de sesión de 30 días** (configurables); tokens opacos hasheados en `USER_SESSION`; `created_at` ancla el límite absoluto | Autenticación (H2) |
| D5 | Hash de contraseñas | **argon2-cffi**; fijar en `requirements.lock.txt` al implementar | H2 |
| D6 | Auditoría de permisos | Tabla **PERMISSION_AUDIT** además de `FILE_OPERATION` (que solo enumera UPLOAD/DOWNLOAD/SCAN). RNF-14: cambios de permisos trazables | Modelo de datos (H1) |
| D7 | Escaneos | **Propietario explícito antes de importar** (obligatorio por escaneo); nunca inferido de `SOURCE.owner_user_id` (puede ser NULL). **IMPLEMENTADO en H5 (2026-11-17)** | Escaneo (H5) ✓ |
| D8 | Declaración de autorización | La declaración va **asociada a la copia publicada** (tabla `AUTHORIZATION_DECLARATION`, ligada a `TRACK_LOCATION`), no solo en `TRACK_SHARE` (que cubre destinatarios individuales y no la publicación pública). Kinds: `PUBLICATION`, `DOWNLOAD`. Copia coherente también en `PERMISSION_AUDIT.declaration` para la traza. **IMPLEMENTADO en H4 (2026-11-16)** | Compartición (H4) ✓ |
| D9 | Sesiones de usuario | `USER_SESSION` con `revoked_at`; desactivación de cuenta revoca todas sus sesiones en caliente | H2 |
| D10 | Nombres en UI vs SRS | Identificadores SQL en inglés (TRACK, TRACK_LOCATION…); UI y docs en español | H1 |
| D11 | e2e | **Playwright** (Chromium primero; Firefox/WebKit según presupuesto) | H3 |
| D12 | Estado de sesión frontend | **Pinia** (store `auth`); añadir a dependencias en H2 | H2 |
| D13 | Metadatos en carga | El formulario manual sirve para título, artista, álbum y pista. Se **distingue de la lectura técnica del audio**: para validar formato real y obtener duración se usará **mutagen** (en H3); la extensión y el MIME declarado nunca bastan por sí solos | H3 |
| D14 | Entorno de desarrollo | **Docker Desktop** + `compose.yaml` (MySQL 8.4, puerto 3307); API 8000; Vite 5173 | Fase 0/1 |

## 2. Matriz de acceso (A = propietario, B = autenticado, Admin = rol ADMIN)

Regla transversal revisada: **el rol ADMIN no concede ni retira permisos sobre
contenido**. Un administrador es además un usuario: si es propietario A o
destinatario autorizado B, conserva exactamente esos permisos como cualquiera;
la descarga pública autorizada le aplica igual que a B. El rol solo habilita
losendpoints de gestión de la plataforma (invitaciones, cuentas, operaciones).

Copia privada (visibilidad PRIVATE):

| Operación | A | B | Admin |
|---|---|---|---|
| Ver/buscar sus propios metadatos | ✅ | — | ❌* |
| Descubrir/consultar metadatos de A | — | ❌ | ❌* |
| Reproducir | ✅ | ❌ | ❌ |
| Descargar | ✅ | ❌ | ❌ |
| Publicar / hacer pública | ✅ | — | ❌ |

Copia PUBLIC (publicada por A; publicación asociada a declaración `PUBLICATION` en la copia):

| Operación | A | B | Admin |
|---|---|---|---|
| Ver/buscar metadatos publicados | ✅ | ✅ | ✅ |
| Reproducir | ✅ | ✅ | ✅ |
| Descargar | ✅ | ✅ si A autorizó descarga pública (`public_download_allowed` + declaración `DOWNLOAD`); si no, solo con share | igual que B (como usuario) |
| Administrar contenido / despublicar forzado | ✅ | — | Solo vía moderación H5, sin acceso al bytes por su rol |

Copia compartida con B (TRACK_SHARE):

| Operación | A | B | Admin |
|---|---|---|---|
| Ver/buscar la copia en el contexto del compartir | ✅ | ✅ | ❌ |
| Reproducir | ✅ | ✅ (si concedió streaming) | ❌ |
| Descargar | ✅ | ✅ (si concedió descarga) | ❌ |
| Revocar share / unpublish propio | ✅ | — | ❌ |

Notas:

- `*` El rol ADMIN permite **gestionar la plataforma** (usuarios, fuentes,
  operaciones), nunca obtener bytes privados ni eludir permisos de copia.
  Y no excluye los permisos que tenga como propietario o destinatario: un
  admin propietario A conserva ✅ en todo; un admin destinatario autorizado
  conserva ✅ según su share, incluida la descarga pública autorizada.
- Conocer ID/ruta/hash **no** concede acceso: todos los endpoints vuelven a
  autorizar la ubicación resuelta.
- Revocar un permiso individual **no** retira la publicación PUBLIC; para
  cortar acceso hay que retirar la publicación (D8/D11 del plan maestro §3).
- Las listas nunca otorgan derechos sobre el audio (RF-07).
- Un recurso inexistente o no autorizado responde el mismo 404 para no
  revelar la existencia de archivos privados.

## 3. Pendientes que NO bloquean el arranque

- Esquema de INVITATION definitivo (D2) — se cierra al detallar H2.
- Umbral exacto de cuota y revisión tras pruebas de carga (D3).
- Catálogo de errores uniformes y paginación del API (H3/§8 del SRS).
