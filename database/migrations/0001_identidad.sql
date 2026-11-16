-- Identidad: cuentas, sesiones revocables e invitaciones.
-- Convención: una migración aplicada no se edita; los cambios van en archivos nuevos.

CREATE TABLE USER_ACCOUNT (
  user_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  username VARCHAR(64) NOT NULL,
  email VARCHAR(255) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  display_name VARCHAR(255) NULL,
  role ENUM('USER','ADMIN') NOT NULL DEFAULT 'USER',
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id),
  UNIQUE KEY uq_user_username (username),
  UNIQUE KEY uq_user_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE USER_SESSION (
  session_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id BIGINT UNSIGNED NOT NULL,
  token_hash CHAR(64) NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires_at DATETIME NOT NULL,
  last_used_at DATETIME NULL,
  revoked_at DATETIME NULL,
  PRIMARY KEY (session_id),
  UNIQUE KEY uq_session_token_hash (token_hash),
  KEY ix_session_user (user_id),
  KEY ix_session_expires (expires_at),
  CONSTRAINT fk_session_user FOREIGN KEY (user_id) REFERENCES USER_ACCOUNT (user_id)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE INVITATION (
  invitation_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  code_hash CHAR(64) NOT NULL,
  created_by BIGINT UNSIGNED NOT NULL,
  used_by BIGINT UNSIGNED NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires_at DATETIME NOT NULL,
  used_at DATETIME NULL,
  PRIMARY KEY (invitation_id),
  UNIQUE KEY uq_invitation_code_hash (code_hash),
  KEY ix_invitation_created_by (created_by),
  CONSTRAINT fk_invitation_created_by FOREIGN KEY (created_by) REFERENCES USER_ACCOUNT (user_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_invitation_used_by FOREIGN KEY (used_by) REFERENCES USER_ACCOUNT (user_id)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
