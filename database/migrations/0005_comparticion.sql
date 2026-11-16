-- Compartición y auditoría de permisos (extensión propuesta del modelo).
-- TRACK_SHARE: una fila por (copia, destinatario). Re-conceder tras revocar
-- actualiza la fila (revoked_at NULL y nuevos flags). 'declaration' registra
-- la declaración de autorización; no verifica licencia por sí misma.
-- Quitar un permiso individual no retira una publicación PUBLIC existente.

CREATE TABLE TRACK_SHARE (
  share_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  location_id BIGINT UNSIGNED NOT NULL,
  recipient_user_id BIGINT UNSIGNED NOT NULL,
  can_stream TINYINT(1) NOT NULL DEFAULT 1,
  can_download TINYINT(1) NOT NULL DEFAULT 0,
  granted_by BIGINT UNSIGNED NOT NULL,
  declaration VARCHAR(500) NULL,
  granted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  revoked_at DATETIME NULL,
  revoked_by BIGINT UNSIGNED NULL,
  PRIMARY KEY (share_id),
  UNIQUE KEY uq_share_location_recipient (location_id, recipient_user_id),
  KEY ix_share_recipient (recipient_user_id),
  CONSTRAINT fk_share_location FOREIGN KEY (location_id) REFERENCES TRACK_LOCATION (location_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_share_recipient FOREIGN KEY (recipient_user_id) REFERENCES USER_ACCOUNT (user_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_share_granted_by FOREIGN KEY (granted_by) REFERENCES USER_ACCOUNT (user_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_share_revoked_by FOREIGN KEY (revoked_by) REFERENCES USER_ACCOUNT (user_id)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE PERMISSION_AUDIT (
  audit_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  actor_user_id BIGINT UNSIGNED NULL,
  action ENUM('PUBLISH','UNPUBLISH','SHARE_GRANT','SHARE_REVOKE','DOWNLOAD_GRANT','DOWNLOAD_REVOKE','VISIBILITY_CHANGE','ROLE_CHANGE','ACCOUNT_DEACTIVATE','ACCOUNT_ACTIVATE') NOT NULL,
  location_id BIGINT UNSIGNED NULL,
  target_user_id BIGINT UNSIGNED NULL,
  declaration VARCHAR(500) NULL,
  details VARCHAR(500) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (audit_id),
  KEY ix_audit_location (location_id),
  KEY ix_audit_actor (actor_user_id),
  KEY ix_audit_target (target_user_id),
  KEY ix_audit_created (created_at),
  CONSTRAINT fk_audit_actor FOREIGN KEY (actor_user_id) REFERENCES USER_ACCOUNT (user_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_audit_location FOREIGN KEY (location_id) REFERENCES TRACK_LOCATION (location_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_audit_target FOREIGN KEY (target_user_id) REFERENCES USER_ACCOUNT (user_id)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
