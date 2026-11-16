-- Registro de operaciones de archivo (subidas, descargas, escaneos).
-- Sin contraseñas, tokens, rutas físicas ni datos sensibles en 'detail'.

CREATE TABLE FILE_OPERATION (
  operation_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  type ENUM('UPLOAD','DOWNLOAD','SCAN') NOT NULL,
  actor_user_id BIGINT UNSIGNED NULL,
  location_id BIGINT UNSIGNED NULL,
  result ENUM('SUCCESS','FAILURE') NOT NULL,
  bytes_transferred BIGINT UNSIGNED NULL,
  detail VARCHAR(500) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (operation_id),
  KEY ix_operation_type_created (type, created_at),
  KEY ix_operation_actor (actor_user_id),
  KEY ix_operation_location (location_id),
  CONSTRAINT fk_operation_actor FOREIGN KEY (actor_user_id) REFERENCES USER_ACCOUNT (user_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_operation_location FOREIGN KEY (location_id) REFERENCES TRACK_LOCATION (location_id)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
