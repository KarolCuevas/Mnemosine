# Mnemosine — Manual breve

Aplicación web multiusuario para cargar música autorizada, organizar una
biblioteca privada, compartir copias, buscar canciones y reproducir/descargar
solo archivos permitidos. Fase 0–5 completadas (ver `docs/VERIFICACION.md`);
este es el recorrido de uso tras el despliegue local.

## 1. Arranque en local

```powershell
docker compose up -d db                 # MySQL 8.4 en 127.0.0.1:3307
cd backend
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m scripts.migrate
.\.venv\Scripts\python.exe -m scripts.create_admin
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

En otra terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Abre <http://127.0.0.1:5173> y comprueba `http://127.0.0.1:8000/api/health`.

Compueba MySQL: `python -m scripts.check_db` (debe decir 20 tablas).

## 2. Cuentas

- No hay alta pública. El registro es **por invitación**.
- La primera cuenta ADMIN se crea con `python -m scripts.create_admin`.
- Invitaciones: desde el panel de administración (POST /api/admin/invitations
  vía PowerShell con tu sesión, o API directamente):

```powershell
$s = New-Object Microsoft.PowerShell.Commands.WebRequestSession
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/auth/login' -Method Post -ContentType 'application/json' -WebSession $s -Body (@{identity='null';password='TU_CLAVE'} | ConvertTo-Json)
$csrf = ($s.Cookies.GetCookies('http://127.0.0.1:8000') | Where-Object Name -eq 'mnemosine_csrf').Value
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/admin/invitations' -Method Post -ContentType 'application/json' -WebSession $s -Headers @{'X-CSRF-Token'=$csrf} -Body '{"expires_in_days":7}'
```

- Roles: `USER` (biblioteca privada) y `ADMIN` (panel: cuentas, fuentes,
  escaneos, operaciones, auditoría, moderación). El rol **no** concede acceso
  al contenido: un ADMIN ve y oye lo que le permiten sus permisos de copia.

## 3. Recorrido de uso

1. **Cargar**: «Cargar» → elige archivo (MP3/M4A/FLAC/OGG/WAV, ≤ 50 MB; cuota
   5 GB) → título/artista → «Guardar como privada». La copia queda visible
   para ti únicamente.
2. **Biblioteca**: búsqueda por título/artista/álbum, paginación, reproducir y
   descargar lo permitido. El reproductor inferior persiste entre pantallas.
3. **Detalle**: SHA-256, disponibilidad y copias propias. Desde ahí: reproducir,
   descargar, **permisos** (publicar, descarga pública, compartir) y añadir a
   listas.
4. **Compartir**: «Permisos» → declara autorización → comparte con un usuario
   indicando si podrá reproducir y/o descargar. Puedes **revocar** y cortar el
   acceso en caliente.
5. **Publicar**: declaración → «Publicar». Cualquier usuario autenticado verá
   y podrá reproducir la copia. La **descarga pública** requiere una segunda
   autorización explícita.
6. **Listas**: «Listas» → crear, renombrar, ordenar, eliminar (solo las copias;
   las canciones nunca se borran al eliminar una lista).
7. **Descubrir**: copia públicas de otras cuentas; nada es accesible sin
   sesión.

## 4. Administración (rol ADMIN)

Panel «Administración»:

- **Cuentas**: listar, activar/desactivar (revoca sesiones en caliente), rol.
- **Fuentes y escaneos**: registrar carpeta (relativa a la raíz de audio),
  **propietario de la importación** (obligatorio), escanear, ver el informe
  por archivo (ADDED/SKIPPED/MISSING/FAILED). Reescanear no duplica ni cambia
  dueños/permisos.
- **Operaciones**: últimas subidas, descargas y escaneos (sin secretos).
- **Auditoría**: cambios de permisos y roles trazados.

## 5. Respaldo y restauración

```powershell
cd backend
.\.venv\Scripts\python.exe -m scripts.backup          # crea backups/<ts>/ con sql + audio + manifiesto
.\.venv\Scripts\python.exe -m scripts.restore <respaldo>   # RESTAURA en 'mnemosine_restore' y la compara
```

Valida sobre una base de verificación: la restauración real exige pasar
`--db-name mnemosine --yes` (destructiva). Recomendado: respaldo diario y
prueba de restauración mensual.

## 6. Si algo falla

| Síntoma | Qué comprobar |
|---|---|
| Página en blanco | El backend está caído o Tailwind roto. Arranca uvicorn y `npm run dev` de nuevo. |
| «Token CSRF no válido» | Recarga; si sigue, tu sesión caducó → vuelve a iniciar sesión. |
| 401 en toda la app | Sesión expirada/desactivada. Entra de nuevo. |
| `MISSING` en detalle | El archivo falta en disco o la fuente desconectada. Restaura el archivo y reescanea. |
| Docker no arranca | El motor WSL de Docker Desktop requiere y está presente; revisa `docker info`. |
| `--reload` no detecta cambios | OneDrive: arranca uvicorn **sin** `--reload`. |

## 7. Limitaciones del MVP (por diseño)

- PUBLIC accesible solo para cuentas autenticadas; sin acceso anónimo.
- Pertenecer a una lista no otorga derechos sobre el audio.
- Borrar una copia/lista nunca borra el archivo ni otras referencias.
- El rol ADMIN no concede ni retira permisos de contenido.
- No hay conversión/transcodificación ni extracción de audio externo (RF-22+).
