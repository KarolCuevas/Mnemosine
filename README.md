# Mnemosine

A Sound Archieve

Aplicación de biblioteca musical con cuentas por invitación, cargas privadas,
reproducción, permisos por copia, listas y administración. Vue 3 + Tailwind,
FastAPI y MySQL 8.4 con SQL explícito, sin ORM.

La primera entrega del [plan de integraciones](docs/PLAN_INTEGRACIONES.md) añade
MusicBrainz, un índice local de metadatos y referencias privadas en `/referencias`.
También permite conectar el Drive de cada usuario y elegir archivos en
`/conexiones`; su audio aún no se incorpora a la biblioteca. Consulta
[el estado de las integraciones](docs/INTEGRACIONES.md) y
[la configuración y prueba de Google](docs/GOOGLE_DRIVE_CONFIGURACION.md).

## 1. Requisitos

| Herramienta | Para qué sirve |
|---|---|
| Python 3.12 o posterior | Ejecutar el backend dentro de un entorno virtual |
| Node.js 24 LTS y npm | Instalar dependencias y ejecutar Vue; mínimo de esta base: 22.12 |
| Docker Desktop con Compose y motor Linux | Ejecutar MySQL sin instalarlo directamente en Windows |
| Git | Versionar código y configuración sin secretos |
| Editor y navegador | Escribir código y probar la aplicación |

SQL es el lenguaje de consultas; **MySQL es el servidor que necesitas**. Docker
lo ejecutará por ti. Workbench o DBeaver son clientes opcionales, no reemplazan
el servidor. Si prefieres MySQL instalado directamente, usa 8.4, crea una base
utf8mb4 y un usuario propio, omite Docker y ajusta `backend/.env`.

En la revisión inicial se detectaron Python 3.14.3, Node 24.14.0, npm, Git y Docker
en este equipo. La presencia del comando Docker no garantiza que su motor esté iniciado.
No necesitas instalar todos otra vez. Comprueba en PowerShell:

```powershell
python --version
node --version
npm --version
git --version
docker compose version
docker info
```

## 2. Preparar MySQL

Desde la raíz del proyecto, abre Docker Desktop y ejecuta:

```powershell
Copy-Item .env.example .env
Copy-Item backend/.env.example backend/.env
```

Edita ambos archivos antes de continuar: cambia las contraseñas de ejemplo y
usa la misma clave en `MYSQL_PASSWORD` y `DB_PASSWORD`. No repitas las copias
si ya configuraste los archivos. `.env` queda excluido de Git.

```powershell
docker compose up -d db
docker compose ps
```

Espera a que figure `healthy`. Si no inicia, consulta `docker compose logs db`.
Conexión desde un cliente SQL: host `127.0.0.1`, puerto `3307`, base `mnemosine`,
usuario `mnemosine_app` y la clave elegida. Este puerto evita el 3306 habitual.
El volumen conserva los datos al detener el contenedor. Las variables iniciales
solo crean cuentas y base cuando el volumen está vacío: editar `.env` después no
cambia automáticamente las credenciales existentes.

Docker crea una base vacía en la primera ejecución. `scripts.migrate` crea y
actualiza las tablas (migraciones 0001–0017); no edites migraciones ya aplicadas.
Antes de actualizar una instalación con datos, detén escrituras y ejecuta
`python -m scripts.backup` desde el entorno virtual del backend.

## 3. Iniciar el backend

En una terminal desde la raíz:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m scripts.migrate
.\.venv\Scripts\python.exe -m scripts.check_db
.\.venv\Scripts\python.exe -m scripts.create_admin
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 ##Levantar API
```

En este equipo `uvicorn --reload` no detecta bien los cambios (OneDrive): arranca
sin `--reload` y reinicia el proceso al editar.

`create_admin` crea la primera cuenta ADMIN (la plataforma es por invitación; la
primera cuenta se crea así). `python -m scripts.verify_schema` y
`python -m scripts.verify_isolation` comprueban restricciones y aislamiento A/B/admin
(esta última usa una base `mnemosine_test` temporal, ya eliminada al terminar).

No hace falta activar el entorno ni cambiar la política de PowerShell.
API: <http://127.0.0.1:8000/api/health>. Documentación: <http://127.0.0.1:8000/docs>.
El endpoint health solo comprueba la API; el script anterior comprueba MySQL.

Se incluye `requirements.lock.txt` generado y comprobado con Python 3.14.3.
Si usas otra versión de Python y alguna dependencia no es compatible, instala
desde `requirements.txt`, comprueba el arranque y actualiza el lock. Después de
cambiar dependencias, registra las versiones validadas para repetirlas:

```powershell
.\.venv\Scripts\python.exe -m pip freeze | Set-Content -Encoding utf8 requirements.lock.txt
```

En otras instalaciones usa `pip install -r requirements.lock.txt` con la misma
versión de Python. El archivo inicial usa rangos, no es un lock reproducible.

## 4. Iniciar el frontend

En otra terminal desde la raíz:

```powershell
cd frontend
npm ci
npm run dev
```

Abre <http://127.0.0.1:5173>. Vite reenvía `/api` al backend en el puerto 8000.
Se incluye `package-lock.json` generado tras instalar las dependencias. Usa
`npm ci` para reproducirlas y `npm install` cuando modifiques dependencias.
Para comprobar la compilación ejecuta `npm run build`.
Si 8000 o 5173 ya están ocupados, detén tu servicio anterior o cambia los puertos
y el destino del proxy en `frontend/vite.config.js`.

## 5. Dónde continuar

La siguiente ampliación está definida en el [plan de catálogos musicales y almacenamiento](docs/PLAN_INTEGRACIONES.md): MusicBrainz como fuente principal para buscar e indexar nombres, Drive conectado por cada usuario, copias entre Drive y servidor, y almacenamiento modular para otros medios. Deezer queda descartado para el índice local bajo sus condiciones estándar actuales; el motivo está documentado en el plan.

```text
frontend/src/       Pantallas, componentes y comunicación con la API
backend/app/        Rutas, servicios, SQL, seguridad y almacenamiento
backend/scripts/    Comprobaciones y futuras tareas administrativas
database/           Migraciones y datos sintéticos
storage/            Audio local y temporales; excluidos de Git
tests/              Pruebas unitarias, de integración y recorridos
docs/               Guías de arquitectura, datos y crecimiento
```

1. Lee [la arquitectura](docs/ARQUITECTURA.md) para saber dónde va cada archivo.
2. Sigue el arranque por hitos (acuerdos → datos → cuentas → demo privada) en [el plan de arranque](docs/PLAN_ARRANQUE.md) y cierra las decisiones propuestas en [decisiones](docs/DECISIONES.md) antes de escribir migraciones.
3. Diseña el DER con [la guía de datos](docs/MODELO_DATOS.md), [el DER inicial](docs/DER.md) y el SRS original.
4. Consulta [el manual](docs/MANUAL.md) para las funciones existentes.
5. Completa la aceptación real de I2 y continúa por I3–I4 según [el estado de las integraciones](docs/INTEGRACIONES.md).
6. Sigue [la guía de crecimiento](docs/ESCALABILIDAD.md) antes de publicar.

Las pruebas existentes y sus resultados se documentan en [verificación](docs/VERIFICACION.md).
La nueva suite se ejecuta desde backend con
`.\.venv\Scripts\python.exe -m scripts.verify_integrations` (usa una base temporal).
OAuth y Picker se verifican con
`.\.venv\Scripts\python.exe -m scripts.verify_google_drive` (MySQL temporal y Google simulado).
Los tests de lógica se ejecutan con
`.\.venv\Scripts\python.exe -m unittest discover -s ../tests/unit -p test_*.py`.
Conviene mantener entornos virtuales, dependencias y audio fuera de sincronización
con OneDrive si aparecen bloqueos o sincronización lenta.

Para detener: Ctrl+C en las terminales y `docker compose stop` desde la raíz.
Evita eliminar volúmenes: contienen la base de datos. Los respaldos se guardan
fuera del repositorio y deben incluir también el audio.

## Referencias oficiales

- [Vite: requisitos e inicio](https://vite.dev/guide/)
- [Tailwind con Vite](https://tailwindcss.com/docs/installation/using-vite)
- [Imagen oficial MySQL y variables de inicialización](https://hub.docker.com/_/mysql)
