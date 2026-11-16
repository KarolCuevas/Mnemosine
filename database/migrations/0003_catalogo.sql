-- Catálogo: artistas, álbumes y canciones. Los metadatos son compartidos;
-- la propiedad y los permisos viven en TRACK_LOCATION (0004_copias.sql).

CREATE TABLE ARTIST (
  artist_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  name VARCHAR(255) NOT NULL,
  sort_name VARCHAR(255) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (artist_id),
  KEY ix_artist_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE ALBUM (
  album_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  title VARCHAR(512) NOT NULL,
  sort_title VARCHAR(512) NULL,
  release_year SMALLINT UNSIGNED NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (album_id),
  KEY ix_album_title (title)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE TRACK (
  track_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  title VARCHAR(512) NOT NULL,
  sort_title VARCHAR(512) NULL,
  duration_seconds INT UNSIGNED NOT NULL DEFAULT 0,
  disc_number TINYINT UNSIGNED NULL,
  track_number TINYINT UNSIGNED NULL,
  album_id BIGINT UNSIGNED NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (track_id),
  KEY ix_track_title (title),
  KEY ix_track_album (album_id),
  CONSTRAINT fk_track_album FOREIGN KEY (album_id) REFERENCES ALBUM (album_id)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE TRACK_ARTIST (
  track_id BIGINT UNSIGNED NOT NULL,
  artist_id BIGINT UNSIGNED NOT NULL,
  position TINYINT UNSIGNED NOT NULL DEFAULT 1,
  role ENUM('MAIN','FEATURING') NOT NULL DEFAULT 'MAIN',
  PRIMARY KEY (track_id, artist_id, role),
  KEY ix_track_artist_artist (artist_id),
  CONSTRAINT chk_ta_position CHECK (position >= 1),
  CONSTRAINT fk_ta_track FOREIGN KEY (track_id) REFERENCES TRACK (track_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_ta_artist FOREIGN KEY (artist_id) REFERENCES ARTIST (artist_id)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE ALBUM_ARTIST (
  album_id BIGINT UNSIGNED NOT NULL,
  artist_id BIGINT UNSIGNED NOT NULL,
  PRIMARY KEY (album_id, artist_id),
  KEY ix_album_artist_artist (artist_id),
  CONSTRAINT fk_aa_album FOREIGN KEY (album_id) REFERENCES ALBUM (album_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_aa_artist FOREIGN KEY (artist_id) REFERENCES ARTIST (artist_id)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
