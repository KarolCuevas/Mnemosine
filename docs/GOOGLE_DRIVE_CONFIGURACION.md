# Preparar Google Drive personal

Estado al 27/11/2026: implementados OAuth por usuario, cifrado de credenciales,
reconexión/desconexión, Picker y selección privada de archivos con comprobación
de acceso desde el servidor. La pantalla está en **Mi Google Drive** (`/conexiones`).
La autorización real de las dos cuentas piloto sigue pendiente de aceptación.

Esta fase comprueba los datos y permisos de los archivos elegidos. La validación
de sus bytes, incorporación a la biblioteca, reproducción, descarga y copias
Drive ↔ servidor corresponden a I3/I4 y todavía no están disponibles.

## Configuración comprobada el 27/11/2026

Proyecto piloto: `mnemosine-516014`. Número de proyecto: `115531235897`.

| Requisito | Resultado comprobado |
|---|---|
| Google Drive API y Google Picker API | Ambas habilitadas en el proyecto |
| Audiencia | Usuarios externos; estado de publicación «Prueba» |
| Cuentas piloto A/B | Ambas cuentas indicadas por el usuario figuran como usuarios de prueba; también existe una tercera cuenta previa |
| Alcances declarados | La lista estaba vacía. Se agregó y guardó únicamente `https://www.googleapis.com/auth/drive.file`; sin permisos sensibles ni restringidos |
| Cliente OAuth | `Mnemosine Intern`, de tipo aplicación web; JSON localizado en Descargas y correspondiente a este proyecto |
| Origen y retorno | El JSON contiene exactamente el origen y la URI de retorno indicados abajo |
| Clave de Picker | Se creó `Mnemosine Picker desarrollo`, con autorización del usuario, y se verificaron sus restricciones tras recargar la consola |

Restricciones guardadas para la clave de Picker:

- API: solo **Google Picker API**.
- Sitios web: `http://127.0.0.1:5173/*` y `https://docs.google.com/*`.
- Sin vinculación a una cuenta de servicio.

El dominio `docs.google.com` es necesario porque aloja el selector en un iframe,
según la [guía oficial de Picker web](https://developers.google.com/workspace/drive/picker/guides/web-picker).
El cliente OAuth y la clave de Picker están incorporados a `backend/.secrets/`
en este equipo. Ese directorio y `backend/.env` están excluidos de Git; los
valores no se incluyen en esta documentación ni en el código.

Estas comprobaciones validan la preparación del proyecto. Las pruebas automáticas
del intercambio OAuth, aislamiento y selector usan Google simulado. No sustituyen
el consentimiento y la selección reales que debe realizar cada persona.

## Proyecto de pruebas

1. En [Google Cloud Console](https://console.cloud.google.com/), crea o selecciona
   un proyecto de Mnemosine. Guarda su **número de proyecto** y su ID.
2. En la biblioteca de APIs habilita **Google Drive API** y **Google Picker API**.
3. En Google Auth Platform configura el nombre Mnemosine, correo de soporte y
   contacto del desarrollador. Selecciona audiencia externa de pruebas e incorpora
   dos cuentas piloto distintas (A y B).
4. Declara únicamente `https://www.googleapis.com/auth/drive.file` para los archivos
   creados por la app o seleccionados explícitamente con Picker. No solicites acceso
   completo a Drive. Elegir una carpeta no garantiza acceso a sus archivos existentes.
   [Alcances oficiales](https://developers.google.com/workspace/drive/api/guides/api-specific-auth).

## Cliente OAuth y selector

1. Crea un cliente OAuth 2.0 de tipo **Aplicación web**.
2. Para desarrollo, usa el mismo host en toda la sesión: `http://127.0.0.1:5173`
   como origen de JavaScript. No alternes con `localhost` durante la autorización.
3. Registra esta URI exacta de retorno:
   `http://127.0.0.1:5173/api/integrations/google_drive/callback`.
   Vite reenviará `/api` al backend y así se conserva la cookie de sesión del mismo
   host. La ruta ya está implementada. En producción será la misma ruta bajo el
   dominio HTTPS definitivo, registrado por separado y sin comodines.
4. Conserva el client ID y client secret en configuración protegida del servidor.
   No los subas a Git ni los pegues en el chat. El secreto no lleva prefijo `VITE_`.
5. Crea la clave para Google Picker, restringida a Google Picker API. En
   restricciones de sitios web permite `http://127.0.0.1:5173/*` para desarrollo
   y `https://docs.google.com/*` para el iframe de Picker. Agrega el origen HTTPS
   de producción cuando se defina; no habilites todos los sitios.
   El selector necesitará esa clave, el número del proyecto y un access token
   temporal del usuario. No guardes ese token en localStorage. El refresh token
   permanecerá cifrado en el backend.

Referencias: [OAuth web](https://developers.google.com/identity/protocols/oauth2/web-server),
[Google Picker web](https://developers.google.com/workspace/drive/picker/guides/web-picker),
[restricciones de claves](https://docs.cloud.google.com/api-keys/docs/add-restrictions-api-keys).

## Instalar la configuración local

En este equipo ya se instaló la configuración y se aplicó la migración 0016,
después de respaldar la base y el audio. Para otra instalación, desde `backend`:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m scripts.backup
.\.venv\Scripts\python.exe -m scripts.migrate
.\.venv\Scripts\python.exe -m scripts.prepare_google "C:/ruta/cliente-oauth.json" --project-id mnemosine-516014 --project-number 115531235897 --picker-key-file "C:/ruta/clave-picker.txt"
```

El último archivo debe contener únicamente la clave restringida de Picker.
El script copia las credenciales, genera una clave de cifrado independiente si
no existe y configura rutas absolutas en `backend/.env`. No muestra los valores,
no sustituye un cliente distinto ni regenera una clave de cifrado existente.
Sin archivo de Picker deja la función desactivada. Reinicia FastAPI después.

| Variable | Contenido |
|---|---|
| `GOOGLE_DRIVE_ENABLED` | `true` cuando las tres piezas están disponibles |
| `GOOGLE_PROJECT_ID` | `mnemosine-516014` |
| `GOOGLE_PROJECT_NUMBER` | `115531235897`; no confundir con el ID |
| `GOOGLE_APP_ORIGIN` | `http://127.0.0.1:5173` en desarrollo |
| `GOOGLE_OAUTH_CLIENT_FILE` | Ruta absoluta a `google-oauth.json` |
| `GOOGLE_TOKEN_KEYS_FILE` | Ruta absoluta a `google-token-keys.json` |
| `GOOGLE_PICKER_KEY_FILE` | Ruta absoluta a `google-picker.txt` |

El secreto OAuth y la clave de cifrado permanecen en el servidor. Picker recibe
la clave restringida y un token de acceso corto de la cuenta conectada, solo al
pulsar **Elegir un audio de Drive**. El refresh token nunca se envía al navegador;
no se guardan tokens en localStorage ni sessionStorage.

## Conectar las dos cuentas piloto

Los usuarios de prueba de Google y los usuarios de Mnemosine son registros
distintos: agregar un correo en Google no crea una cuenta en Mnemosine.

1. A inicia sesión en su cuenta de Mnemosine desde `http://127.0.0.1:5173`.
2. Abre **Mi Google Drive → Conectar Google Drive** y elige su cuenta piloto de
   Google. Comprueba que el permiso se refiere a los archivos usados con la app.
3. Al volver, debe aparecer **Conectada** y el correo elegido. Pulsa **Elegir un
   audio de Drive** y selecciona un archivo de prueba propio de **Mi unidad**.
4. La selección privada debe mostrar el nombre confirmado por Google. **Comprobar
   acceso** repite la consulta; **Quitar selección** conserva el original.
5. B repite el recorrido con otra cuenta de Mnemosine y su propio Google. Usar
   perfiles distintos del navegador evita mezclar sesiones. Si B aún no tiene
   cuenta de Mnemosine, ADMIN debe crearle una invitación desde Administración.
6. Verifica que A, B y un ADMIN separado no vean selecciones ajenas. Cancelar
   el consentimiento conserva una conexión anterior. Desconectar retira la
   selección y revoca el permiso sin borrar archivos en Drive; después permite
   reconectar. Para cambiar de cuenta Google hay que desconectar primero.

No se enumeran todos los archivos con Drive API. Picker es la elección explícita;
el servidor vuelve a consultar cada ID con el token del propietario. Solo se
admiten candidatos a audio propios, descargables y autorizados, hasta cinco por
solicitud y 500 selecciones por conexión. Carpetas, accesos directos, documentos
de Workspace y unidades compartidas quedan fuera.

En proyectos externos en estado **Prueba**, los refresh tokens para este permiso
pueden vencer a los siete días: la interfaz pedirá reconectar. La publicación y
las revisiones de Google se planifican aparte. [Caducidad de refresh tokens](https://developers.google.com/identity/protocols/oauth2#expiration).

## Custodia, rotación y restauración

El archivo `google-token-keys.json` contiene un identificador `current` y un mapa
`keys` de claves Fernet versionadas. Es independiente de `SECRET_KEY` y de MySQL.
Protege sus permisos de lectura para el servicio y el administrador; en despliegue
guárdalo fuera del repositorio y de carpetas sincronizadas. Todos los procesos
de la misma instalación deben usar las mismas claves y base de datos.

Para rotar, conserva una copia protegida de las claves por separado del respaldo
SQL. Genera una nueva clave con `cryptography.fernet.Fernet.generate_key()`,
añádela con un identificador nuevo y cambia `current` mediante sustitución atómica
del archivo. Conserva las claves anteriores: las conexiones existentes aún las
necesitan hasta renovarse o reconectarse. No retires una versión mientras haya
credenciales o autorizaciones pendientes cifradas con ella. Si una clave se pierde,
recupérala del respaldo protegido; generar otra no descifra los tokens anteriores.

`scripts.restore` comprueba primero los conteos del respaldo y después elimina
credenciales y estados OAuth restaurados, exige reconexión y cancela trabajos
pendientes. No reactiva permisos antiguos ni revoca la instalación original de
Google. El respaldo habitual incluye SQL y audio local; no contiene las claves
de `.secrets/` ni los archivos remotos de Drive. Los logs de proxies tampoco
deben guardar la consulta de la ruta OAuth; véase [DESPLIEGUE.md](DESPLIEGUE.md).

## Verificación

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s ../tests/unit -p test_google_drive.py -v
.\.venv\Scripts\python.exe -m scripts.verify_google_drive
.\.venv\Scripts\python.exe -m scripts.e2e
```

Resultado: 5 pruebas unitarias de Google, 71 comprobaciones con MySQL temporal
y 14 recorridos de interfaz correctos (incluyen las funciones anteriores).
Google y su selector se simulan en estas suites; la prueba real A/B sigue
pendiente. Descargar/reproducir audio remoto se verificará al implementar I3.
