"""Audio sintético para pruebas; ninguna grabación ni portada del usuario."""

import base64
import io
import subprocess
import wave
from pathlib import Path

import mutagen
from mutagen.flac import Picture
from mutagen.id3 import APIC, TALB, TCON, TDRC, TIT2, TPE1, TPE2, TPOS, TRCK
from mutagen.mp4 import MP4Cover
from PIL import Image

TITLE = "Aurora etiquetada"
ARTISTS = ["Álvaro de prueba", "Invitada"]
ALBUM = "Horizontes sintéticos"


def cover_png(color=(28, 160, 84)) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (240, 240), color).save(output, format="PNG")
    return output.getvalue()


def make_wav(path: Path) -> None:
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b"\x00\x00" * 8000 * 5)


def add_tags(path: Path, cover: bytes | None = None) -> None:
    cover = cover_png() if cover is None else cover
    audio = mutagen.File(str(path))
    if audio.tags is None:
        audio.add_tags()
    if path.suffix in (".wav", ".mp3"):
        for frame in [TIT2(encoding=3, text=[TITLE]), TPE1(encoding=3, text=ARTISTS),
                      TALB(encoding=3, text=[ALBUM]), TPE2(encoding=3, text=["Ensamble de prueba"]),
                      TCON(encoding=3, text=["Ambient"]), TRCK(encoding=3, text=["3/12"]),
                      TPOS(encoding=3, text=["2/2"]), TDRC(encoding=3, text=["2021-07-15"])]:
            audio.tags.add(frame)
        audio.tags.add(APIC(encoding=3, mime="image/png", type=3, desc="Frente", data=cover))
    elif path.suffix == ".m4a":
        audio.update({"\xa9nam": [TITLE], "\xa9ART": ARTISTS, "\xa9alb": [ALBUM],
                      "aART": ["Ensamble de prueba"], "\xa9gen": ["Ambient"],
                      "\xa9day": ["2021-07-15"], "trkn": [(3, 12)], "disk": [(2, 2)],
                      "covr": [MP4Cover(cover, imageformat=MP4Cover.FORMAT_PNG)]})
    else:
        audio.update({"title": [TITLE], "artist": ARTISTS, "album": [ALBUM],
                      "albumartist": ["Ensamble de prueba"], "genre": ["Ambient"],
                      "date": ["2021-07-15"], "tracknumber": ["3/12"], "discnumber": ["2/2"]})
        picture = Picture()
        picture.type, picture.mime, picture.width, picture.height, picture.depth = 3, "image/png", 240, 240, 24
        picture.data = cover
        if path.suffix == ".flac":
            audio.clear_pictures()
            audio.add_picture(picture)
        else:
            audio["metadata_block_picture"] = [base64.b64encode(picture.write()).decode("ascii")]
    audio.save()


def make_tagged_wav(path: Path) -> None:
    make_wav(path)
    add_tags(path)


def make_all_formats(directory: Path, ffmpeg: str) -> dict[str, Path]:
    source = directory / "sin-etiquetas.wav"
    make_wav(source)
    paths = {}
    for extension, codec in (("flac", "flac"), ("mp3", "libmp3lame"), ("m4a", "aac"), ("ogg", "libvorbis"), ("wav", "pcm_s16le")):
        target = directory / f"nombre-distinto.{extension}"
        subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(source), "-c:a", codec, str(target)], check=True, capture_output=True)
        add_tags(target)
        paths[extension] = target
    return paths
