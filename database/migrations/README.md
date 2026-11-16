# Migraciones SQL

MySQL arranca con una base vacía; el esquema se define con los archivos numerados
en esta carpeta. Una migración aplicada **no se edita**: escribe otra que transforme
el esquema. InnoDB y utf8mb4 (`utf8mb4_0900_ai_ci`).

## Convención de archivos

- `0001_identidad.sql`, `0002_fuentes.sql`, … en orden estricto.
- Comentarios de línea con `--`; una sentencia por `;` al final de línea;
  sin `;` dentro de literales de texto y sin procedimientos almacenados.
- `schema_migrations` registra versión, archivo, checksum SHA-256 y fecha.

## Ejecutar

Desde `backend/` (con `backend/.env` configurado y MySQL en `healthy`):

```powershell
.\.venv\Scripts\python.exe -m scripts.migrate --dry-run   # ver qué se aplicaría
.\.venv\Scripts\python.exe -m scripts.migrate             # aplicar pendientes
.\.venv\Scripts\python.exe -m scripts.check_db            # comprobar conexión + esquema
.\.venv\Scripts\python.exe -m scripts.verify_schema       # probar restricciones (transacción revertida)
```

El ejecutor se detiene ante fallos, evita ejecuciones simultáneas con
`GET_LOCK` y detecta modificaciones en migraciones ya aplicadas (checksum).
MySQL hace commit implícito en DDL: no prometas rollback transaccional de
CREATE/ALTER; respalda antes de migraciones destructivas.
