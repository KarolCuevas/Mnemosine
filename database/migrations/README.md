# Migraciones SQL pendientes

MySQL se inicia con una base vacía. No se crean todavía las tablas del negocio.
Primero cierra las decisiones de `docs/MODELO_DATOS.md`.

Convención: `0001_identidad.sql`, `0002_catalogo.sql`, etc. Una migración aplicada
no se edita: escribe otra que transforme el esquema. Usa InnoDB y utf8mb4.
Registra versión, fecha y checksum en una tabla `schema_migrations` cuando
implementes el ejecutor. No ejecutes todas las migraciones cada vez que inicia la API.

El ejecutor deberá detenerse ante fallos, evitar ejecuciones simultáneas y detectar
cambios en migraciones ya aplicadas. MySQL puede hacer commit implícito en DDL:
no prometas rollback transaccional de CREATE/ALTER TABLE. Prueba recuperación y
respalda antes de migraciones destructivas.

En desarrollo puedes aplicar cada archivo revisado con un cliente MySQL conectado
a la base local. No se incluye un ejecutor automático en este esqueleto.
