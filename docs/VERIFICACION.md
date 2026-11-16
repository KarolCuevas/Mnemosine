# Verificación de la base y de la Fase 1

Fecha: 16 de noviembre de 2026.

- Docker reparado por el usuario (WSL no estaba instalado/recreado; la
  distribución `docker-desktop` quedó operativa tras su intervención).
- `docker compose up -d db`: MySQL 8.4.13 crea el volumen nuevo y pasa a
  `healthy` (127.0.0.1:3307).
- Ejecutor `scripts.migrate`: primera ejecución detectada/corregida — `GET_LOCK`
  y `RELEASE_LOCK` devolvían filas sin consumir ("Unread result found"). Corregido
  con `fetchall()`. Tras el arreglo:
  - `--dry-run` lista las 7 migraciones pendientes.
  - Aplicación real: `0001`–`0007` aplicadas correctamente.
  - Segunda ejecución: 0 pendientes, 7 ya aplicadas (idempotencia OK);
    checksums validados.
- `scripts.check_db`: conexión OK; 18 tablas presentes
  (17 de negocio/identidad + `schema_migrations`).
- `scripts.verify_schema`: 10/10 comprobaciones correctas contra MySQL real
  (uniques, FK RESTRICT, CHECKs, ENUMs, hash sin unicidad global). La
  transacción se revierte; sin datos residuales.
- `scripts.migrate`/`split_statements` y SHA-256 de los SQL validados sin DB.
- Adaptador de almacenamiento local comprobado con pruebas ad hoc: normalización
  y rechazo de rutas maliciosas, ciclo save→commit→stream con offset/length,
  no-sobrescritura, límite de tamaño y recuperación de temporales
  (`STORAGE_TESTS_OK`).
- `compileall` correcto en `scripts/` y `app/storage/`.
- Seeds: `database/seeds/0001_demo.sql` aplicado; DEVICE=1, SOURCE=1,
  ARTIST=2, ALBUM=2, TRACK=4.
- FastAPI: importación, health y OpenAPI comprobadas con anterioridad.
- Frontend: `npm ci` y `npm run build` completados con anterioridad. Sin
  revisión visual en navegador.
- Cuentas, sesiones, carga y reproducción: todavía no implementadas (H2/H3).

Pendiente de la Fase 1 que no requiere más trabajo antes de H2; se cierra
demostrando la instalación reproducible de cero al integrar los cambios:

1. `docker compose down` (sin `-v`) → `up -d db` sobre volumen vacío →
   migrate → check_db → verify_schema en otra máquina o tras clonar limpio.
2. Respaldo/restauración: H6.
