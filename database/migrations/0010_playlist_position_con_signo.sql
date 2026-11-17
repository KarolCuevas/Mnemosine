-- PLAYLIST_TRACK.position pasa a INT con signo: el reordenamiento usa posiciones
-- temporales negativas para no violar UNIQUE(playlist_id, position) en la misma
-- transacción (docs/DER.md, docs/MODELO_DATOS.md). Las posiciones visibles
-- siguen siendo siempre >= 1 (CHECK chk_playlist_track_position se ajusta).

ALTER TABLE PLAYLIST_TRACK
  DROP CHECK chk_playlist_track_position,
  MODIFY position INT NOT NULL,
  ADD CONSTRAINT chk_playlist_track_position CHECK (position >= 1 OR position <= -1);
