-- Listas privadas ordenadas. Pertenecer a una lista NUNCA otorga derechos
-- sobre el audio; la autorización se resuelve siempre vía TRACK_LOCATION.
-- PLAYLIST_TRACK: la misma canción aparece una sola vez por lista (SRS) y la
-- posición es única por lista. Reordenar en transacción con posiciones
-- temporales o renumeración para no violar uq_playlist_track_position.

CREATE TABLE PLAYLIST (
  playlist_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  owner_user_id BIGINT UNSIGNED NOT NULL,
  name VARCHAR(255) NOT NULL,
  description VARCHAR(1000) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (playlist_id),
  KEY ix_playlist_owner (owner_user_id),
  CONSTRAINT fk_playlist_owner FOREIGN KEY (owner_user_id) REFERENCES USER_ACCOUNT (user_id)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE PLAYLIST_TRACK (
  playlist_id BIGINT UNSIGNED NOT NULL,
  track_id BIGINT UNSIGNED NOT NULL,
  position INT UNSIGNED NOT NULL,
  PRIMARY KEY (playlist_id, track_id),
  UNIQUE KEY uq_playlist_track_position (playlist_id, position),
  KEY ix_playlist_track_track (track_id),
  CONSTRAINT fk_plt_playlist FOREIGN KEY (playlist_id) REFERENCES PLAYLIST (playlist_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_plt_track FOREIGN KEY (track_id) REFERENCES TRACK (track_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT chk_playlist_track_position CHECK (position >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
