-- Copias de audio con dueño, ruta, hash, disponibilidad y visibilidad.
-- sha256 NO es único globalmente: dos copias de los mismos bytes conservan
-- dueños y permisos independientes (regla del plan §2).
-- relative_path: relativa a la raíz de la fuente, normalizada ('/', sin '..').
-- El servidor rechaza rutas de más de 512 caracteres en carga y escaneo;
-- no se trunca en silencio. 512 * 4 B (utf8mb4) + source_id cabe en el límite
-- de índice InnoDB (3072 B) para UNIQUE(source_id, relative_path).

CREATE TABLE TRACK_LOCATION (
  location_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  track_id BIGINT UNSIGNED NOT NULL,
  owner_user_id BIGINT UNSIGNED NOT NULL,
  source_id BIGINT UNSIGNED NOT NULL,
  relative_path VARCHAR(512) NOT NULL,
  sha256 CHAR(64) NOT NULL,
  size_bytes BIGINT UNSIGNED NOT NULL,
  mime_type VARCHAR(100) NOT NULL,
  visibility ENUM('PRIVATE','PUBLIC') NOT NULL DEFAULT 'PRIVATE',
  availability ENUM('AVAILABLE','MISSING','ERROR') NOT NULL DEFAULT 'AVAILABLE',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (location_id),
  UNIQUE KEY uq_location_source_path (source_id, relative_path),
  KEY ix_location_owner_visibility (owner_user_id, visibility),
  KEY ix_location_track (track_id),
  KEY ix_location_sha256 (sha256),
  CONSTRAINT fk_loc_track FOREIGN KEY (track_id) REFERENCES TRACK (track_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_loc_owner FOREIGN KEY (owner_user_id) REFERENCES USER_ACCOUNT (user_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_loc_source FOREIGN KEY (source_id) REFERENCES SOURCE (source_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT chk_location_path_len CHECK (CHAR_LENGTH(relative_path) BETWEEN 1 AND 512),
  CONSTRAINT chk_location_sha256_len CHECK (CHAR_LENGTH(sha256) = 64)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
