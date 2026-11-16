-- Fuente central de almacenamiento: las copias subidas por los usuarios se
-- asocian siempre a esta fuente (biblioteca central del servidor).
-- IDs fijos y deterministas; idempotente vía checksum de scripts.migrate.
-- El audio sigue fuera de MySQL: aquí solo hay metadatos de la fuente.

INSERT INTO DEVICE (device_id, name, kind) VALUES
  (9001, 'Almacenamiento central', 'SERVER');

INSERT INTO SOURCE (source_id, device_id, owner_user_id, name, base_relative_path, status) VALUES
  (9001, 9001, NULL, 'Biblioteca central', 'audio', 'ACTIVE');
