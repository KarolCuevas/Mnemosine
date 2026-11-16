"""Construcción de respuestas de entrega de audio (Range / Content-Range)."""

import re
import urllib.parse
from dataclasses import dataclass
from pathlib import Path


def attachment_filename(title: str, relative_path: str) -> tuple[str, str]:
    """(nombre ASCII seguro, cabecera Content-Disposition attachment)."""
    ext = Path(relative_path).suffix.lower()
    cleaned = "".join(ch for ch in title if ch.isalnum() or ch in (" ", "-", "_", ".", "'", "&", ",")).strip()
    cleaned = " ".join(cleaned.split())[:120] or "cancion"
    filename = f"{cleaned}{ext}"
    ascii_name = filename.encode("ascii", "ignore").decode().strip() or "cancion"
    encoded = urllib.parse.quote(filename)
    return filename, f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{encoded}"


class RangeNotSatisfiable(Exception):
    pass


@dataclass(frozen=True)
class ByteRange:
    start: int
    end: int  # inclusivo


_RANGE_RE = re.compile(r"^bytes=(\d*)-(\d*)$")


def parse_range(header: str, size: int) -> ByteRange:
    if "," in header:
        raise RangeNotSatisfiable("múltiples rangos no admitidos")
    match = _RANGE_RE.match(header.strip())
    if not match:
        raise RangeNotSatisfiable("cabecera Range no válida")
    start_s, end_s = match.groups()
    if not start_s and not end_s:
        raise RangeNotSatisfiable("cabecera Range vacía")

    if not start_s:  # bytes=-SUFFIX
        suffix = int(end_s)
        if suffix <= 0:
            raise RangeNotSatisfiable("sufijo debe ser positivo")
        start = max(size - suffix, 0)
        end = size - 1
    else:
        start = int(start_s)
        end = int(end_s) if end_s else size - 1
        if start >= size:
            raise RangeNotSatisfiable("inicio fuera de rango")
        if end < start:
            raise RangeNotSatisfiable("fin antes del inicio")
        end = min(end, size - 1)
    if size == 0 or start > end:
        raise RangeNotSatisfiable("archivo vacío o rango no válido")
    return ByteRange(start=start, end=end)


def content_range(start: int, end: int, size: int) -> str:
    return f"bytes {start}-{end}/{size}"
