-- Datos de demostración sintéticos (catálogo y fuentes). UNA VEZ, sobre una
-- base migrada y vacía: python -m scripts.migrate && mysql ... < seeds/0001_demo.sql
-- Re-ejecutarlo provoca errores de clave duplicada sin corromper datos.
-- Sin usuarios, contraseñas ni audio: las copias se crean desde la app (H3).
-- Sin material con copyright: nombres inventados.

INSERT INTO DEVICE (device_id, name, kind) VALUES
  (1001, 'Servidor local', 'SERVER');

INSERT INTO SOURCE (source_id, device_id, owner_user_id, name, base_relative_path, status) VALUES
  (1001, 1001, NULL, 'Biblioteca demo', 'demo', 'ACTIVE');

INSERT INTO ARTIST (artist_id, name, sort_name) VALUES
  (1001, 'Kältmare', 'Kältmare'),
  (1002, 'Aya Duarte', 'Duarte, Aya');

INSERT INTO ALBUM (album_id, title, sort_title, release_year) VALUES
  (1001, 'Sol', 'Sol', 2024),
  (1002, 'Marea baja', 'Marea baja', 2025);

INSERT INTO TRACK (track_id, title, sort_title, duration_seconds, disc_number, track_number, album_id) VALUES
  (1001, 'Aurora', 'Aurora', 198, 1, 1, 1001),
  (1002, 'Luz de horizonte', 'Luz de horizonte', 224, 1, 2, 1001),
  (1003, 'Neon Tides', 'Neon Tides', 201, 1, 1, 1002),
  (1004, 'Caminos de sal', 'Caminos de sal', 243, 1, 2, 1002);

INSERT INTO TRACK_ARTIST (track_id, artist_id, position, role) VALUES
  (1001, 1001, 1, 'MAIN'),
  (1002, 1001, 1, 'MAIN'),
  (1003, 1002, 1, 'MAIN'),
  (1004, 1002, 1, 'MAIN');

INSERT INTO ALBUM_ARTIST (album_id, artist_id) VALUES
  (1001, 1001),
  (1002, 1002);
