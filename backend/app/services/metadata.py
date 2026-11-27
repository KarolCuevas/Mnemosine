"""Etiquetas y portada incrustadas. Nunca modifica el audio ni consulta servicios externos."""

import base64
import binascii
import io
import re
import unicodedata
import warnings
from dataclasses import dataclass, field
from pathlib import Path

import mutagen
from mutagen.flac import Picture
from mutagen.id3 import ID3
from mutagen.mp4 import MP4Tags
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_COVER_BYTES = 8 * 1024 * 1024
MAX_COVER_PIXELS = 16_000_000
MAX_SAVED_COVER_BYTES = 512 * 1024


@dataclass
class EmbeddedMetadata:
    title: str | None = None
    artists: list[str] = field(default_factory=list)
    album: str | None = None
    album_artist: str | None = None
    genre: str | None = None
    track_number: int | None = None
    disc_number: int | None = None
    release_year: int | None = None
    cover: bytes | None = None
    warnings: list[str] = field(default_factory=list)


def clean_text(value: object, limit: int) -> str | None:
    if value is None:
        return None
    value = unicodedata.normalize("NFC", str(value))
    value = re.sub(r"[\x00-\x1f\x7f]", " ", value)
    return " ".join(value.split())[:limit].strip() or None


def _texts(value: object, limit: int = 255) -> list[str]:
    values = getattr(value, "text", value)
    if not isinstance(values, (tuple, list)):
        values = [values]
    return list(dict.fromkeys(text for item in values[:16] if (text := clean_text(item, limit))))


def _first(value: object, limit: int = 512) -> str | None:
    values = _texts(value, limit)
    return values[0] if values else None


def _number(value: object, maximum: int) -> int | None:
    # ID3/Vorbis: "3/12"; MP4: [(3, 12)]. Ignore invalid tags, never reject good audio.
    if isinstance(value, list):
        value = value[0] if value else None
    if isinstance(value, tuple):
        value = value[0] if value else None
    text = _first(value)
    match = re.fullmatch(r"\s*(\d+)(?:\s*/\s*\d+)?\s*", text or "")
    if not match:
        return None
    number = int(match[1])
    return number if 1 <= number <= maximum else None


def _year(value: object) -> int | None:
    match = re.match(r"^(\d{4})(?:$|[-/T ])", _first(value) or "")
    return int(match[1]) if match and 1000 <= int(match[1]) <= 9999 else None


def read_tag_values(tags) -> EmbeddedMetadata:
    """Normaliza ID3 (MP3/WAV), iTunes (M4A) y Vorbis comments (FLAC/OGG)."""
    if not tags:
        return EmbeddedMetadata()
    if isinstance(tags, ID3):
        keys = ("TIT2", "TPE1", "TALB", "TPE2", "TCON", "TRCK", "TPOS", "TDRC")
        date = tags.get("TDRC") or tags.get("TYER")
        genre = getattr(tags.get("TCON"), "genres", None)
    elif isinstance(tags, MP4Tags):
        keys = ("\xa9nam", "\xa9ART", "\xa9alb", "aART", "\xa9gen", "trkn", "disk", "\xa9day")
        date, genre = tags.get(keys[-1]), tags.get(keys[4])
    else:
        keys = ("title", "artist", "album", "albumartist", "genre", "tracknumber", "discnumber", "date")
        date = tags.get("date") or tags.get("year")
        genre = tags.get("genre")
    return EmbeddedMetadata(
        title=_first(tags.get(keys[0])),
        artists=_texts(tags.get(keys[1])),
        album=_first(tags.get(keys[2])),
        album_artist=clean_text(", ".join(_texts(tags.get(keys[3]))), 255),
        genre=clean_text(", ".join(_texts(genre)), 255),
        track_number=_number(tags.get(keys[5]), 1000),
        disc_number=_number(tags.get(keys[6]), 100),
        release_year=_year(date),
    )


def _cover_candidates(audio):
    candidates = []
    tags = audio.tags
    if hasattr(audio, "pictures"):
        candidates.extend((int(picture.type), picture.data) for picture in audio.pictures[:16])
    if isinstance(tags, ID3):
        candidates.extend((int(picture.type), picture.data) for picture in tags.getall("APIC")[:16])
    elif isinstance(tags, MP4Tags):
        candidates.extend((3, bytes(picture)) for picture in tags.get("covr", [])[:16])
    elif tags:
        for encoded in tags.get("metadata_block_picture", [])[:16]:
            try:
                if len(encoded) > MAX_COVER_BYTES * 4 // 3 + 4096:
                    candidates.append((3, b""))
                    continue
                picture = Picture(base64.b64decode(encoded, validate=True))
                candidates.append((int(picture.type), picture.data))
            except (binascii.Error, ValueError, TypeError, mutagen.MutagenError):
                candidates.append((3, b""))
        # Older Vorbis writers used COVERART instead of METADATA_BLOCK_PICTURE.
        for encoded in tags.get("coverart", [])[:16]:
            try:
                data = base64.b64decode(encoded, validate=True) if len(encoded) <= MAX_COVER_BYTES * 4 // 3 + 4 else b""
                candidates.append((0, data))
            except (binascii.Error, ValueError, TypeError):
                candidates.append((0, b""))
    # Prefer front cover, then unspecified artwork, then back cover/other pictures.
    return sorted(candidates, key=lambda item: 0 if item[0] == 3 else 1 if item[0] == 0 else 2)


def normalize_cover(data: bytes) -> bytes | None:
    if not data or len(data) > MAX_COVER_BYTES:
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data), formats=["JPEG", "PNG", "WEBP"]) as original:
                if original.width * original.height > MAX_COVER_PIXELS:
                    return None
                original.load()  # Reject truncated images before storing anything.
                oriented = ImageOps.exif_transpose(original)
                oriented.thumbnail((800, 800), Image.Resampling.LANCZOS)
                rgba = oriented.convert("RGBA")
                image = Image.new("RGB", rgba.size, "white")
                image.paste(rgba, mask=rgba.getchannel("A"))
                output = io.BytesIO()
                image.save(output, format="JPEG", quality=85, optimize=True)
                if output.tell() > MAX_SAVED_COVER_BYTES:
                    image.thumbnail((512, 512), Image.Resampling.LANCZOS)
                    output = io.BytesIO()
                    image.save(output, format="JPEG", quality=75, optimize=True)
                return output.getvalue() if output.tell() <= MAX_SAVED_COVER_BYTES else None
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        return None


def read_embedded_metadata(path: Path) -> EmbeddedMetadata:
    try:
        audio = mutagen.File(str(path))
    except (mutagen.MutagenError, OSError, ValueError):
        return EmbeddedMetadata(warnings=["No se pudieron leer las etiquetas del archivo."])
    if audio is None:
        return EmbeddedMetadata()
    metadata = read_tag_values(audio.tags)
    candidates = _cover_candidates(audio)
    for _, data in candidates:
        if cover := normalize_cover(data):
            metadata.cover = cover
            break
    if candidates and metadata.cover is None:
        metadata.warnings.append("La portada incrustada no se pudo usar: está dañada, su formato no es compatible o supera el tamaño admitido.")
    return metadata


def save_metadata(cursor, track_id: int, metadata: EmbeddedMetadata) -> None:
    # Small derived artwork stays in the same transaction as the track. No source-specific paths.
    cursor.execute(
        "INSERT INTO TRACK_METADATA (track_id, album_artist, genre, release_year, cover_jpeg) VALUES (%s,%s,%s,%s,%s)",
        (track_id, metadata.album_artist, metadata.genre, metadata.release_year, metadata.cover),
    )


def attach_cover_urls(items: list[dict]) -> None:
    """One small query per page; never load image bytes into a library response."""
    from app.repositories import db
    ids = list({item["track_id"] for item in items})
    if not ids:
        return
    with db.read_only() as cursor:
        placeholders = ",".join(["%s"] * len(ids))
        cursor.execute(f"SELECT track_id FROM TRACK_METADATA WHERE track_id IN ({placeholders}) AND cover_jpeg IS NOT NULL", tuple(ids))
        covered = {row["track_id"] for row in cursor.fetchall()}
    for item in items:
        item["cover_url"] = f"/api/tracks/{item['track_id']}/cover" if item["track_id"] in covered else None
