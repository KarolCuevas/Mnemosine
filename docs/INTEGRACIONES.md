# Integraciones — estado de implementación

Fecha: 25 de noviembre de 2026. Configuración Google revisada el 27 de noviembre
de 2026. Referencia: `PLAN_INTEGRACIONES.md`.

## Estado real

| Fase | Estado en esta entrega |
|---|---|
| I0 | Decisiones registradas: Drive personal, MusicBrainz principal, contacto `czmprojects@gmail.com`. Proyecto piloto Google preparado: APIs, cuentas de prueba, alcance `drive.file`, cliente OAuth y clave de Picker restringida comprobados; véase `GOOGLE_DRIVE_CONFIGURACION.md` |
| I1 | Registro de fuentes/capacidades, resolvedor por fuente, estados de consulta, compatibilidad local, cargas por bloques, cuota serializada y base TRANSFER_JOB implementados |
| I2 | Implementado: conexiones privadas, tokens cifrados, OAuth con state/PKCE, reconexión/desconexión, Picker y selección comprobada por ID. Pendiente aceptación real con A/B |
| I3 | Pendiente: adaptador Drive, IDs/versiones remotos, vinculación, trabajador, leases, cuotas reservadas y carga reanudable |
| I4 | Pendiente: copias Drive ↔ servidor, cancelación, reconciliación e idempotencia remota |
| I5 | Implementado: búsqueda MusicBrainz, índice local de núcleo CC0, lookup/caché, tráfico compartido y referencias privadas |
| I6 | Pantallas de referencias y conexiones, pruebas automáticas y restauración sin reactivar permisos; aceptación integrada con Drive pendiente |

No se presenta la base `TRANSFER_JOB` como un trabajador funcional. La evolución
remota de SOURCE/TRACK_LOCATION se completará junto al contrato de I2/I3, con
claves foráneas que unan propietario y conexión. Las fases completas I1/I6 no se
dan por cerradas mientras falten reservas, recuperación y pruebas remotas.

## Uso

1. Inicia MySQL, aplica `python -m scripts.migrate` desde el entorno del backend
   y arranca FastAPI y Vite. Respalda una instalación con datos antes de migrar.
2. Configura en `backend/.env` (no en Git):

   ```dotenv
   MUSICBRAINZ_ENABLED=true
   MUSICBRAINZ_CONTACT=czmprojects@gmail.com
   CATALOG_CACHE_SECONDS=3600
   CATALOG_RECORD_TTL_DAYS=30
   ```

3. Reinicia FastAPI tras cambiar configuración. El `.env.example` mantiene la
   consulta externa desactivada por defecto para otras instalaciones.
4. Abre **Mi biblioteca → Referencias musicales** (`/referencias`). La vista
   comienza en el índice local. Para consultar Internet selecciona **MusicBrainz**,
   escribe título/artista y pulsa **Buscar**. No hay peticiones al escribir cada letra.
5. **Guardar referencia** verifica el MBID mediante lookup o caché vigente y añade
   el registro a **Mi colección privada**. Guardar dos veces no crea duplicados.
6. **Actualizar datos** consulta el proveedor explícitamente. **Quitar de mi colección**
   elimina solo tu asociación: conserva el índice público y todos los archivos.

Las referencias no tienen controles de audio. No se asigna un álbum único a una
grabación: se muestran las ediciones conocidas con sus IDs independientes. Las
ediciones devueltas por el proveedor pueden ser un subconjunto, no un inventario completo.

## Contratos y datos

- `GET /api/integrations/providers`: capacidades y disponibilidad configurada.
- `GET /api/catalog/recordings?title=&artist=&page=`: búsqueda local sin proveedor.
- `GET /api/external/musicbrainz/search?title=&artist=&cursor=`: consulta explícita;
  el cursor firmado se liga a los filtros. Máximo 25 resultados por solicitud.
- `GET /api/external/musicbrainz/recordings/{mbid}?refresh=true`: detalle o actualización.
- `POST /api/external/references`: solo `provider` y `provider_id`; sesión + CSRF.
- `GET /api/external/references`: colección del usuario, paginada y sin caché HTTP compartida.
- `DELETE /api/external/references/{id}`: solo su propietario, con CSRF; ADMIN no tiene bypass.
- `GET /api/storage/sources`: fuente central y fuentes propias, con capacidades.
- `GET /api/storage/sources/{id}/objects`: inventario autorizado. LOCAL lista solo
  copias registradas del usuario, sin exponer rutas físicas ni archivos ajenos.
- `POST /api/tracks/upload`: conserva respuesta 201 y acepta `source_id` opcional;
  el destino predeterminado sigue siendo 9001. Una fuente de solo lectura rechaza
  la carga antes de consumir el iterador de bytes en el servicio.

Migración 0014 agrega código/configuración versionada a SOURCE sin reescribir rutas
y reserva TRANSFER_JOB. Migración 0015 crea CATALOG_RECORD, EXTERNAL_TRACK,
CATALOG_QUERY_CACHE y PROVIDER_TRAFFIC. No se alteran 0001–0013 ni sus checksums.

Se almacenan título, crédito de artistas/IDs, duración, ISRC, desambiguación y
ediciones básicas/IDs; no se guardan respuestas completas, portadas, puntuaciones,
etiquetas ni anotaciones. Cada grabación se identifica por proveedor/tipo/MBID.
La colección privada usa el índice público, pero no publica quién la guardó.

### Conexiones Drive

La migración 0016 añade `INTEGRATION_CONNECTION`, `OAUTH_AUTHORIZATION` y
`DRIVE_SELECTION`, con relación entre conexión y propietario. No modifica
TRACK_LOCATION ni crea audio a partir de metadatos. Desde **Mi Google Drive**
(`/conexiones`) cada usuario conecta su cuenta y elige archivos con Picker.
Configuración y recorrido: [GOOGLE_DRIVE_CONFIGURACION.md](GOOGLE_DRIVE_CONFIGURACION.md).

Rutas bajo `/api/integrations/google_drive`:

- `GET /status`: configuración disponible y estado de la conexión propia, sin tokens.
- `POST /authorize` y `GET /callback`: inicio con CSRF y retorno fijo ligado a la
  sesión, estado de un solo uso con diez minutos de vigencia y PKCE S256.
- `POST /connections/{id}/picker`: token corto propio, clave restringida y número
  de proyecto. Verifica la identidad con Google antes de entregar el token.
- `POST /connections/{id}/files`: recibe solo IDs; Google confirma permisos,
  propietario, nombre, tipo, tamaño y versión. Aún no valida los bytes del audio.
- `GET /connections/{id}/files`: selección privada paginada (25 elementos).
- `DELETE /connections/{id}/files/{selection_id}`: quita la selección local.
- `POST /connections/{id}/disconnect`: bloquea inmediatamente, revoca y limpia
  la selección. Si Google falla conserva un estado pendiente para reintentar.

Las operaciones que modifican datos exigen CSRF; no hay bypass para ADMIN.
Los tokens se cifran con claves versionadas independientes del secreto de sesión.
Un bloqueo MySQL por usuario serializa OAuth, renovación, selección y desconexión
entre procesos, sin mantener transacciones SQL durante las peticiones a Google.
Los errores no incluyen respuestas del proveedor ni credenciales. Las respuestas
no se cachean y el callback elimina su consulta antes del registro de Uvicorn.
El proxy de producción necesita una regla equivalente para sus propios logs.

Fuentes técnicas: [API y búsqueda](https://musicbrainz.org/doc/MusicBrainz_API/Search),
[campos del núcleo](https://musicbrainz.org/doc/MusicBrainz_Database),
[identificación de la aplicación](https://musicbrainz.org/doc/MusicBrainz_API).

## Tráfico, caché y fallos

Todas las consultas externas pasan por un bloqueo asesor MySQL y un reloj en
PROVIDER_TRAFFIC. La conexión está en autocommit: no hay una transacción abierta
durante HTTP. Hay al menos 1,1 s de separación tras una respuesta, tiempos de espera
de red, límite de respuesta y respeto de Retry-After. Si está ocupado se devuelve
429 con tiempo de reintento; el usuario puede volver a buscar. No hay reintentos
automáticos ilimitados ni un contador independiente por proceso.

Todos los procesos de una misma IP pública deben compartir este MySQL/registro de
tráfico. Si despliegas varias instalaciones con bases independientes bajo la misma
IP, necesitas coordinar también ese tráfico antes de habilitarlas simultáneamente.

La caché guarda una clave HMAC de la consulta, IDs ordenados y total, sin texto de
búsqueda ni usuario. Caduca en una hora; las entradas vencidas se purgan por lotes
al insertar. Los lookups caducan en 30 días y se refrescan al usarse. Los campos CC0
del índice se conservan; no hay barridos ni copia masiva del catálogo. Un fallo
externo no impide consultar ese índice, las referencias guardadas o el audio local.

## Límites operativos antes de Drive

- La carga lee el archivo desde UploadFile por bloques de 64 KiB; el parser de
  multipart aún recibe/spool el cuerpo antes del servicio. En despliegue hay que
  limitar el cuerpo y las cargas concurrentes en el proxy para proteger disco temporal.
- Las cargas ya no limpian temporales globales. Cada una retira solo su temporal,
  incluso tras un fallo de validación. Limpieza de temporales interrumpidos: solo
  en mantenimiento con API/trabajadores detenidos hasta implementar leases.
- La cuota local serializa escrituras de cargas y escaneos sobre la cuenta y cuenta
  reservas de trabajos. Reservar cuota ANTES de una transferencia remota larga
  todavía es parte de I3; no hay transferencias remotas expuestas.
- La publicación local usa creación exclusiva con hard link en el mismo volumen;
  requiere soporte de enlaces duros (NTFS en este equipo). Nunca sobrescribe otro
  archivo. Si SQL falla al confirmar, se verifica el registro antes de compensar;
  si no se puede resolver la incertidumbre, se conserva para reconciliación manual.
- El respaldo contiene MySQL y audio local, no archivos de Drive ni las claves
  de cifrado. La restauración descarta tokens/estados OAuth y cancela trabajos
  pendientes después de verificar los conteos; requiere autorizar Google otra vez.

## Verificar

Desde `backend` con su entorno virtual:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s ../tests/unit -p test_*.py -v
.\.venv\Scripts\python.exe -m scripts.verify_integrations
.\.venv\Scripts\python.exe -m scripts.verify_google_drive
.\.venv\Scripts\python.exe -m scripts.check_musicbrainz
.\.venv\Scripts\python.exe -m scripts.e2e
```

`verify_integrations` crea una base única, migra desde el esquema 0013 con una copia
previa y conserva sus valores, prueba dos usuarios/admin y un adaptador ficticio
de solo lectura. Al finalizar borra únicamente su base y sus temporales. La API
externa se simula en esas pruebas para reproducir fallos y no depender de Internet.
`check_musicbrainz` es la prueba real: consulta hasta cinco registros y los indexa,
sin guardar referencias en ninguna cuenta ni descargar audio.

Resultados del 25/11/2026: 8 pruebas unitarias, 45 comprobaciones nuevas con MySQL,
regresiones H2–H5 y dos pruebas Playwright correctas. Búsqueda y lookup reales de
MusicBrainz verificados. Véase [VERIFICACION.md](VERIFICACION.md) para evidencia,
respaldo y limitaciones de estas pruebas.

Resultados de I2 del 27/11/2026: **5/5** pruebas unitarias de Google, **71/71**
comprobaciones OAuth/aislamiento/restauración con MySQL real y Google simulado,
**45/45** de regresión de integraciones y **14/14** de interfaz. Compilación correcta.
El piloto real con dos consentimientos Google y la aceptación de I3/I4 siguen
pendientes; estos resultados no acreditan almacenamiento ni reproducción remotos.
