-- Conexiones privadas: solo metadatos de selección; todavía no son TRACK_LOCATION.
CREATE TABLE INTEGRATION_CONNECTION (
  connection_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  owner_user_id BIGINT UNSIGNED NOT NULL,
  provider VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  external_subject VARCHAR(255) CHARACTER SET ascii COLLATE ascii_bin NULL,
  account_email VARCHAR(255) NULL,
  account_name VARCHAR(255) NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'DISCONNECTED',
  granted_scopes TEXT NULL,
  credentials_ciphertext MEDIUMTEXT NULL,
  expires_at DATETIME(6) NULL,
  generation BIGINT UNSIGNED NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (connection_id),
  UNIQUE KEY uq_connection_provider (owner_user_id, provider),
  UNIQUE KEY uq_connection_owner (connection_id, owner_user_id),
  CONSTRAINT fk_connection_owner FOREIGN KEY (owner_user_id) REFERENCES USER_ACCOUNT(user_id) ON DELETE CASCADE,
  CONSTRAINT chk_connection_status CHECK (status IN ('ACTIVE','REAUTH_REQUIRED','DISCONNECTED','REVOCATION_PENDING'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE OAUTH_AUTHORIZATION (
  state_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  owner_user_id BIGINT UNSIGNED NOT NULL,
  session_id BIGINT UNSIGNED NOT NULL,
  connection_generation BIGINT UNSIGNED NOT NULL,
  verifier_ciphertext TEXT NOT NULL,
  expires_at DATETIME(6) NOT NULL,
  PRIMARY KEY (state_hash),
  UNIQUE KEY uq_oauth_owner (owner_user_id),
  KEY ix_oauth_expiry (expires_at),
  CONSTRAINT fk_oauth_owner FOREIGN KEY (owner_user_id) REFERENCES USER_ACCOUNT(user_id) ON DELETE CASCADE,
  CONSTRAINT fk_oauth_session FOREIGN KEY (session_id) REFERENCES USER_SESSION(session_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE DRIVE_SELECTION (
  selection_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  connection_id BIGINT UNSIGNED NOT NULL,
  owner_user_id BIGINT UNSIGNED NOT NULL,
  file_id VARCHAR(200) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  file_name VARCHAR(512) NOT NULL,
  mime_type VARCHAR(255) NOT NULL,
  size_bytes BIGINT UNSIGNED NOT NULL,
  remote_version VARCHAR(128) NOT NULL,
  checked_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (selection_id),
  UNIQUE KEY uq_drive_selection (connection_id, file_id),
  CONSTRAINT fk_selection_connection_owner FOREIGN KEY (connection_id, owner_user_id)
    REFERENCES INTEGRATION_CONNECTION(connection_id, owner_user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
