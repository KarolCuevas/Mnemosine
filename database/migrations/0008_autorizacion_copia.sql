-- Autorización de publicación y descarga pública asociada a la copia.
-- Ajuste D8 (docs/DECISIONES.md): la declaración se liga a TRACK_LOCATION,
-- no solo a destinatarios (TRACK_SHARE). Kinds: PUBLICATION | DOWNLOAD.
-- Regla de negocio (capa de servicios, H4): poner PUBLIC exige declaración
-- PUBLICATION; permitir descarga pública exige public_download_allowed = 1
-- y declaración DOWNLOAD. PERMISSION_AUDIT guarda copia del texto como traza.
-- Nota: MySQL hace commit implícito en DDL (igual que el resto de migraciones).

ALTER TABLE TRACK_LOCATION
  ADD COLUMN public_download_allowed TINYINT(1) NOT NULL DEFAULT 0 AFTER availability;

CREATE TABLE AUTHORIZATION_DECLARATION (
  declaration_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  location_id BIGINT UNSIGNED NOT NULL,
  kind ENUM('PUBLICATION','DOWNLOAD') NOT NULL,
  declaration VARCHAR(500) NOT NULL,
  declared_by BIGINT UNSIGNED NOT NULL,
  declared_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (declaration_id),
  KEY ix_authdecl_location_kind (location_id, kind),
  CONSTRAINT fk_authdecl_location FOREIGN KEY (location_id) REFERENCES TRACK_LOCATION (location_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_authdecl_declared_by FOREIGN KEY (declared_by) REFERENCES USER_ACCOUNT (user_id)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
