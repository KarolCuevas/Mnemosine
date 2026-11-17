"""Lectura técnica del audio, compartida entre carga y escaneo (D13).

La lectura técnica (contenedor/códec/duración/tipo) se distingue de los
metadatos de catálogo (formulario manual en la carga; etiquetas cuando
existan en el escaneo).
"""

from pathlib import Path

import filetype
import mutagen

ALLOWED_EXTENSIONS = {".mp3", ".m4a", ".flac", ".ogg", ".wav"}

# Tipo real devuelto por filetype → extensiones compatibles.
_MIME_BY_EXT = {
    ".mp3": {"audio/mpeg", "audio/mp3"},
    ".m4a": {"audio/mp4", "audio/x-m4a", "audio/m4a", "audio/aac"},
    ".flac": {"audio/flac", "audio/x-flac"},
    ".ogg": {"audio/ogg", "audio/x-ogg", "application/ogg"},
    ".wav": {"audio/x-wav", "audio/wav", "audio/wave", "audio/vnd.wave"},
}


class AudioProbeError(Exception):
    """El archivo no es un audio válido o su nombre no cuadra con el contenido."""


def allowed_extension(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def probe_audio_file(path: Path, filename_hint: str | None = None) -> tuple[str, int, str]:
    """Devuelve (ext, duración_segundos, mime). Lanza AudioProbeError en fallo."""
    ext = Path(filename_hint or path.name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise AudioProbeError(f"formato no admitido: {ext or '(sin extensión)'}")

    kind = filetype.guess(str(path))
    guessed_mime = kind.mime if kind else None
    if guessed_mime and guessed_mime not in _MIME_BY_EXT[ext]:
        raise AudioProbeError(f"el contenido no coincide con la extensión {ext} (detectado: {guessed_mime})")

    audio = mutagen.File(str(path))
    if audio is None or not getattr(audio, "info", None) or not getattr(audio.info, "length", 0):
        raise AudioProbeError("no se reconoce como un audio válido (contenedor/códec no legible)")
    duration = int(audio.info.length)
    if duration <= 0:
        raise AudioProbeError("la duración del audio no es válida")

    mime = guessed_mime or next(iter(_MIME_BY_EXT[ext]))
    return ext, duration, mime


def read_easy_tags(path: Path) -> dict[str, str]:
    """Etiquetas sencillas (título, artista, álbum, pista). Diccionario plano en minúsculas."""
    tags: dict[str, str] = {}
    try:
        audio = mutagen.File(str(path), easy=True)
    except Exception:
        return tags
    if audio is None:
        return tags
    for key in ("title", "artist", "album", "tracknumber", "discnumber", "date"):
        values = audio.get(key)
        if values:
            first = values if isinstance(values, str) else values[0]
            if first:
                tags[key] = str(first).strip()
    return tags
