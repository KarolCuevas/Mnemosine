# Decisiones de arranque (Fase 0) — Mnemosine

Fecha: 16 de noviembre de 2026. Estado general: **propuestas adoptadas por
defecto del plan; pendientes de confirmación del equipo**. Al confirmarlas,
cambia el estado de cada fila y actualiza `PLAN_DESARROLLO.md` §3.

## 1. Decisiones

| # | Tema | Decisión propuesta | Momento límite |
|---|---|---|---|
| D1 | Nombre visible en la aplicación | **Mnemosine**; el SRS conserva «Mneme» como referencia documental | Diseño de interfaz |
| D2 | Registro | **Por invitación** generada por el administrador o alta habilitada por él; sin alta pública abierta en el MVP | Autenticación (H2) |
| D3 | Formatos y límites de carga | **MP3, M4A (AAC), FLAC, OGG Vorbis, WAV**; **50 MB** por archivo; **5 GB** de cuota por cuenta; validación real del archivo (no solo extensión); compatibilidad comprobada en navegadores objetivo; los no reproducibles se documentan sin transcodificar | Cargas (H3) |
| D4 | Sesión | Cookie **HttpOnly + SameSite=Lax**, token **CSRF** en mutaciones, expiración deslizante **7 días**, revocación inmediata al desactivar la cuenta; tokens opacos hasheados en `USER_SESSION` | Autenticación (H2) |
| D5 | Hash de contraseñas | **argon2-cffi**; fijar en `requirements.lock.txt` al implementar | H2 |
| D6 | Auditoría de permisos | Tabla **PERMISSION_AUDIT** además de `FILE_OPERATION` (que solo enumera UPLOAD/DOWNLOAD/SCAN). RNF-14: cambios de permisos trazables | Modelo de datos (H1) |
| D7 | Escaneos | **Propietario explícito antes de importar**; nunca inferido de `SOURCE.owner_user_id` (puede ser NULL). Regla fijada ahora; implementación en H5 | Escaneo (H5) |
| D8 | Declaración de autorización | Al publicar o permitir descarga: registro de **quién declara, cuándo y alcance** (`TRACK_SHARE.declaration` + `PERMISSION_AUDIT`); documenta la declaración, no verifica licencia | Compartición (H4) |
| D9 | Sesiones de usuario | `USER_SESSION` con `revoked_at`; desactivación de cuenta revoca todas sus sesiones en caliente | H2 |
| D10 | Nombres en UI vs SRS | Identificadores SQL en inglés (TRACK, TRACK_LOCATION…); UI y docs en español | H1 |
| D11 | e2e | **Playwright** (Chromium primero; Firefox/WebKit según presupuesto) | H3 |
| D12 | Estado de sesión frontend | **Pinia** (store `auth`); añadir a dependencias en H2 | H2 |
| D13 | Metadatos en carga | Formulario manual en v1 (título, artista, álbum, pista); extracción con mutagen como mejora opcional posterior | H3 |
| D14 | Entorno de desarrollo | **Docker Desktop** + `compose.yaml` (MySQL 8.4, puerto 3307); API 8000; Vite 5173 | Fase 0/1 |

## 2. Matriz de acceso (A = propietario, B = autenticado, Admin = rol ADMIN)

Copia privada (visibilidad PRIVATE):

| Operación | A | B | Admin |
|---|---|---|---|
| Ver/buscar sus propios metadatos | ✅ | — | ❌* |
| Descubrir/consultar metadatos de A | — | ❌ | ❌* |
| Reproducir | ✅ | ❌ | ❌ |
| Descargar | ✅ | ❌ | ❌ |
| Publicar / hacer pública | ✅ | — | ❌ |

Copia PUBLIC (publicada por A):

| Operación | A | B | Admin |
|---|---|---|---|
| Ver/buscar metadatos publicados | ✅ | ✅ | ✅ |
| Reproducir | ✅ | ✅ | ✅ |
| Descargar | ✅ | ❌ hasta autorización de descarga | ❌ |
| Administrar contenido / despublicar forzado | ✅ | — | Solo vía moderación H5, sin acceso al bytes |

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
