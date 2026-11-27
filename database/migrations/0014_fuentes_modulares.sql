-- Extensión aditiva: no reescribe rutas ni modifica migraciones anteriores.
ALTER TABLE SOURCE
  ADD COLUMN adapter_code VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL DEFAULT 'LOCAL',
  ADD COLUMN config_version INT UNSIGNED NOT NULL DEFAULT 1,
  ADD COLUMN adapter_config JSON NULL,
  ADD CONSTRAINT chk_source_config_version CHECK (config_version >= 1);

-- Base de trabajos para las fases I2-I4. No hay trabajador remoto habilitado aún.
CREATE TABLE TRANSFER_JOB (
  transfer_job_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  actor_user_id BIGINT UNSIGNED NOT NULL,
  source_location_id BIGINT UNSIGNED NULL,
  destination_source_id BIGINT UNSIGNED NOT NULL,
  operation VARCHAR(32) NOT NULL,
  idempotency_key VARCHAR(128) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
  expected_bytes BIGINT UNSIGNED NOT NULL DEFAULT 0,
  transferred_bytes BIGINT UNSIGNED NOT NULL DEFAULT 0,
  reserved_bytes BIGINT UNSIGNED NOT NULL DEFAULT 0,
  attempts INT UNSIGNED NOT NULL DEFAULT 0,
  next_attempt_at DATETIME(6) NULL,
  lease_token CHAR(36) NULL,
  lease_expires_at DATETIME(6) NULL,
  expected_version VARCHAR(255) NULL,
  recovery_data JSON NULL,
  result_location_id BIGINT UNSIGNED NULL,
  last_error_code VARCHAR(64) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (transfer_job_id),
  UNIQUE KEY uq_transfer_idempotency (actor_user_id, idempotency_key),
  KEY ix_transfer_pending (status, next_attempt_at, lease_expires_at),
  CONSTRAINT fk_transfer_actor FOREIGN KEY (actor_user_id) REFERENCES USER_ACCOUNT (user_id) ON DELETE RESTRICT,
  CONSTRAINT fk_transfer_source FOREIGN KEY (source_location_id) REFERENCES TRACK_LOCATION (location_id) ON DELETE RESTRICT,
  CONSTRAINT fk_transfer_destination FOREIGN KEY (destination_source_id) REFERENCES SOURCE (source_id) ON DELETE RESTRICT,
  CONSTRAINT fk_transfer_result FOREIGN KEY (result_location_id) REFERENCES TRACK_LOCATION (location_id) ON DELETE RESTRICT,
  CONSTRAINT chk_transfer_status CHECK (status IN ('PENDING','RUNNING','VERIFYING','COMPLETED','RETRY_WAIT','AUTH_REQUIRED','FAILED','CANCELLED'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
