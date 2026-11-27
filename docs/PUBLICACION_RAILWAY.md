# Publicación de Mnemosine en Railway

Preparación del 27/11/2026. El usuario eligió empezar con la prueba gratuita,
sin contratar un plan. Esta guía se conserva en `codex/documentacion-ia`;
`main` conserva el código de publicación y el README original del repositorio.

## Servicios y datos

Se requieren dos servicios en el mismo proyecto:

1. **MySQL 8.4**, sin acceso público, con su volumen persistente.
2. **Mnemosine**, construido desde el `Dockerfile` de la raíz, rama `main`.
   Añadir un volumen persistente montado exactamente en `/data` y generar el
   dominio HTTPS de Railway. Mantener una sola réplica mientras se use este volumen.

La imagen compila Vue y ejecuta FastAPI bajo el mismo dominio. El arranque espera
a MySQL, aplica migraciones y comprueba que el volumen sea escribible. En Railway
se niega a arrancar sin volumen para evitar guardar audios en un disco efímero.
Prepara el propietario del volumen y ejecuta el servidor con UID/GID 10001.
Los archivos de audio solo se sirven mediante rutas que comprueban permisos.

No se incluyen la base local, sus usuarios, audios, `.env`, claves Google,
respaldos ni historial Git en la imagen. La instalación remota comienza vacía;
trasladar los datos locales requiere un procedimiento separado y autorizado.

## Variables del servicio Mnemosine

Usar referencias a las variables del servicio MySQL, no copiar secretos al código:

| Variable | Valor |
|---|---|
| `DB_HOST` | Dirección privada del servicio MySQL |
| `DB_PORT` | `3306` |
| `DB_NAME` | Base creada por MySQL |
| `DB_USER` | Usuario de aplicación con permisos sobre esa base |
| `DB_PASSWORD` | Referencia al secreto correspondiente de MySQL |
| `SECRET_KEY` | Valor aleatorio nuevo de al menos 32 caracteres |
| `STORAGE_ROOT` | `/data` |
| `SESSION_COOKIE_SECURE` | `true` |
| `MAX_UPLOAD_BYTES` | `52428800` (50 MiB) |
| `MAX_USER_QUOTA_BYTES` | `104857600` inicialmente (100 MiB por cuenta en el piloto) |
| `MUSICBRAINZ_ENABLED` | `true` si el entorno permite consultas externas |
| `MUSICBRAINZ_CONTACT` | `czmprojects@gmail.com` |
| `GOOGLE_DRIVE_ENABLED` | `false` hasta completar el consentimiento real y registrar el dominio nuevo |

El límite por usuario no sustituye el límite del volumen compartido. Ajustar las
cuotas al espacio contratado antes de invitar más usuarios. No publicar el puerto
de MySQL para que la aplicación conecte: la red privada es suficiente.

`railway.json` selecciona Docker y `/api/ready` como comprobación de arranque.
Esta ruta comprueba conexión SQL y presencia del almacenamiento; `/api/health`
solo confirma que el proceso responde. Los cambios en `main` deben publicarse
solo después de comprobar el respaldo y las migraciones pendientes.

## Primera cuenta y aceptación

Crear la primera cuenta con `python -m scripts.create_admin` dentro del servicio
(por ejemplo, mediante `railway ssh`). El script solicita la contraseña de forma
interactiva; no pasarla en argumentos, no guardarla en Git ni enviarla por chat.
Después ADMIN puede generar invitaciones para otras cuentas.

En el enlace HTTPS comprobar acceso, carga de un audio propio de prueba,
reproducción, descarga y conservación después de reiniciar. Las cookies deben
ser Secure. Los audios y portadas privados deben rechazar solicitudes anónimas.
La aceptación real de Google Drive continúa pendiente; al reactivarlo hay que
registrar el nuevo origen y callback en Google y restringir la clave de Picker.

## Prueba local de la imagen

Desde la raíz: `docker build -t mnemosine:publicacion .`.
Desde `backend`: `python -m scripts.verify_release`.

La prueba usa una red Docker, MySQL y un volumen nuevos con nombres únicos.
Crea una cuenta y un WAV sintéticos, comprueba subida, descarga exacta, rangos,
cookies Secure, archivos privados, usuario del proceso y reinicio. Retira solo
sus contenedores, volumen y red. No usa `mnemosine` ni `storage/` locales.

## Coste y conservación

La prueba nueva ofrece US$5 de crédito durante un máximo de 30 días. Al agotarse
el crédito o el plazo, los servicios pueden detenerse. No equivale a alojamiento
permanente gratis. Antes de que termine, exportar los datos o elegir un plan y
sus límites; comprobar en la cuenta la política vigente de conservación.
Fuente: [planes gratuitos y prueba](https://docs.railway.com/pricing/free-plan).

Los respaldos de Railway y las exportaciones de la base y el volumen deben
configurarse antes de depender de la instalación para datos únicos. Los scripts
`backup`/`restore` actuales usan Docker Compose local: no respaldan automáticamente
esta instalación remota. Conservar SQL y audio como un conjunto consistente;
las claves de cifrado, cuando se active Google, se custodian por separado.

Referencias: [Dockerfiles](https://docs.railway.com/builds/dockerfiles),
[MySQL](https://docs.railway.com/databases/mysql),
[volúmenes](https://docs.railway.com/volumes),
[configuración como código](https://docs.railway.com/config-as-code/reference).
