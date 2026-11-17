-- Informe detallado por archivo de cada trabajo de escaneo (B12).
-- Solo metadatos: nombre de ruta relativa a la raíz de audio (con prefijo de
-- la fuente), resultado (ADDED/SKIPPED/MISSING/FAILED), track y duración/artista/
-- álbum cuando existan. Sin bytes ni contenido.

CREATE TABLE SCAN_JOB_FILE (
  scan_job_file_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  scan_job_id BIGINT UNSIGNED NOT NULL,
  relative_path VARCHAR(512) NOT NULL,
  outcome ENUM('ADDED','SKIPPED','MISSING','FAILED') NOT NULL,
  track_id BIGINT UNSIGNED NULL,
  title VARCHAR(512) NULL,
  artist VARCHAR(255) NULL,
  album VARCHAR(512) NULL,
  duration_seconds INT UNSIGNED NULL,
  detail VARCHAR(255) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (scan_job_file_id),
  KEY ix_sjf_job_outcome (scan_job_id, outcome),
  KEY ix_sjf_track (track_id),
  CONSTRAINT fk_sjf_job FOREIGN KEY (scan_job_id) REFERENCES SCAN_JOB (scan_job_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_sjf_track FOREIGN KEY (track_id) REFERENCES TRACK (track_id)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
