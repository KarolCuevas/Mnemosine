-- Las copias importadas por escaneo almacenaban rutas sin el prefijo de la
-- fuente, por lo que la entrega las daba por inexistentes y las marcaba MISSING.
-- Tras la corrección del código, reescribimos las rutas existentes para que
-- sean relativas a la raíz de audio (con el prefijo de la fuente), como exige
-- UNIQUE(source_id, relative_path).

UPDATE TRACK_LOCATION l
JOIN SOURCE s ON s.source_id = l.source_id
SET l.relative_path = CONCAT(s.base_relative_path, '/', l.relative_path)
WHERE s.source_id <> 9001
  AND l.relative_path NOT LIKE CONCAT(s.base_relative_path, '/%');
