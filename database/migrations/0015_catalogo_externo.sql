-- Índice público de campos autorizados. No contiene búsquedas ni actividad de usuarios.
CREATE TABLE CATALOG_RECORD (
  catalog_record_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  provider VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  entity_type VARCHAR(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  provider_id VARCHAR(128) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  title VARCHAR(512) NOT NULL,
  title_search VARCHAR(1024) NOT NULL,
  artist_search TEXT NOT NULL,
  metadata JSON NOT NULL,
  fetched_at DATETIME(6) NOT NULL,
  lookup_at DATETIME(6) NULL,
  PRIMARY KEY (catalog_record_id),
  UNIQUE KEY uq_catalog_identity (provider, entity_type, provider_id),
  KEY ix_catalog_title (title_search(191))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE EXTERNAL_TRACK (
  external_track_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  owner_user_id BIGINT UNSIGNED NOT NULL,
  catalog_record_id BIGINT UNSIGNED NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (external_track_id),
  UNIQUE KEY uq_external_owner_record (owner_user_id, catalog_record_id),
  CONSTRAINT fk_external_owner FOREIGN KEY (owner_user_id) REFERENCES USER_ACCOUNT (user_id) ON DELETE CASCADE,
  CONSTRAINT fk_external_record FOREIGN KEY (catalog_record_id) REFERENCES CATALOG_RECORD (catalog_record_id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Caché de búsqueda: clave HMAC, IDs ordenados y total; nunca texto de búsqueda ni respuestas completas.
CREATE TABLE CATALOG_QUERY_CACHE (
  cache_key CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  record_ids JSON NOT NULL,
  total BIGINT UNSIGNED NOT NULL,
  expires_at DATETIME(6) NOT NULL,
  PRIMARY KEY (cache_key),
  KEY ix_catalog_cache_expiry (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Una política compartida por todas las sesiones/procesos conectados a este MySQL.
CREATE TABLE PROVIDER_TRAFFIC (
  provider VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  next_allowed_at DATETIME(6) NOT NULL,
  PRIMARY KEY (provider)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
