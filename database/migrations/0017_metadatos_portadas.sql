-- Datos derivados del archivo. La portada siempre es JPEG normalizado <=512 KiB.
-- Su entrega exige sesión y permiso de vista sobre una copia, igual que el catálogo.
CREATE TABLE TRACK_METADATA (
  track_id BIGINT UNSIGNED NOT NULL,
  album_artist VARCHAR(255) NULL,
  genre VARCHAR(255) NULL,
  release_year SMALLINT UNSIGNED NULL,
  cover_jpeg MEDIUMBLOB NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (track_id),
  CONSTRAINT fk_metadata_track FOREIGN KEY (track_id) REFERENCES TRACK(track_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT chk_metadata_year CHECK (release_year IS NULL OR release_year BETWEEN 1000 AND 9999),
  CONSTRAINT chk_metadata_cover_size CHECK (cover_jpeg IS NULL OR OCTET_LENGTH(cover_jpeg) <= 524288)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- El formulario ya admite pistas hasta 1000; TINYINT solo alcanzaba 255.
ALTER TABLE TRACK MODIFY COLUMN track_number SMALLINT UNSIGNED NULL;
