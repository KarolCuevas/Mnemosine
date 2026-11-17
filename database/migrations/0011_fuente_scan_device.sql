-- Dispositivo lógico para las fuentes importadas por escaneo. Las copias
-- subidas por usuarios siguen referenciando la fuente central (9001); las
-- fuentes registradas por el administrador referencian este dispositivo.

INSERT INTO DEVICE (device_id, name, kind) VALUES
  (9002, 'Servidor de fuentes', 'SERVER');
