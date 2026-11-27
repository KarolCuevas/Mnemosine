import base64
import io
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from mutagen.flac import Picture
from mutagen.id3 import ID3, APIC, TIT2, TPE1, TCON, TRCK, TPOS, TDRC
from mutagen.mp4 import MP4Tags
from PIL import Image

from app.services.metadata import MAX_COVER_BYTES, clean_text, normalize_cover, read_embedded_metadata, read_tag_values
from scripts.media_test_fixtures import cover_png, make_tagged_wav


class MetadataTests(unittest.TestCase):
    def test_real_wav_id3_and_picture_without_modifying_file(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "different-name.wav"
            make_tagged_wav(path)
            original = path.read_bytes()
            metadata = read_embedded_metadata(path)
            self.assertEqual(metadata.title, "Aurora etiquetada")
            self.assertEqual(metadata.artists, ["Álvaro de prueba", "Invitada"])
            self.assertEqual((metadata.track_number, metadata.disc_number, metadata.release_year), (3, 2, 2021))
            self.assertEqual(metadata.album_artist, "Ensamble de prueba")
            self.assertEqual(metadata.genre, "Ambient")
            self.assertTrue(metadata.cover.startswith(b"\xff\xd8"))
            self.assertEqual(path.read_bytes(), original)

    def test_mp4_tuple_numbers_and_multiple_artists(self):
        tags = MP4Tags()
        tags.update({"\xa9nam": ["M4A"], "\xa9ART": ["Uno", "Dos"], "trkn": [(300, 400)], "disk": [(2, 3)], "\xa9day": ["2022-01-01"]})
        metadata = read_tag_values(tags)
        self.assertEqual((metadata.title, metadata.artists, metadata.track_number, metadata.disc_number, metadata.release_year), ("M4A", ["Uno", "Dos"], 300, 2, 2022))

    def test_id3_number_and_genre_handling(self):
        tags = ID3()
        for frame in [TIT2(text=["ID3"]), TPE1(text=["Artista"]), TCON(text=["(13)"]), TRCK(text=["03/12"]), TPOS(text=["2/2"]), TDRC(text=["1999"])]:
            tags.add(frame)
        metadata = read_tag_values(tags)
        self.assertEqual(metadata.genre, "Pop")
        self.assertEqual((metadata.track_number, metadata.disc_number, metadata.release_year), (3, 2, 1999))

    def test_absent_and_malformed_tags_are_optional(self):
        for tags in [None, {}, {"tracknumber": ["5000/6000"], "discnumber": ["0"], "date": ["no fecha"]}, {"tracknumber": ["tres"], "date": ["0001"]}]:
            metadata = read_tag_values(tags)
            self.assertIsNone(metadata.title)
            self.assertEqual(metadata.artists, [])
            self.assertIsNone(metadata.track_number)
            self.assertIsNone(metadata.disc_number)
            self.assertIsNone(metadata.release_year)

    def test_text_limits_controls_and_unicode(self):
        self.assertEqual(clean_text("  Cafe\u0301\x00\n azul  ", 255), "Café azul")
        metadata = read_tag_values({"title": ["x" * 1000], "artist": ["", "A" * 300], "album": ["Á" * 600]})
        self.assertEqual(len(metadata.title), 512)
        self.assertEqual(len(metadata.artists[0]), 255)
        self.assertEqual(len(metadata.album), 512)

    def test_cover_is_bounded_jpeg_without_exif(self):
        raw = io.BytesIO()
        exif = Image.Exif()
        exif[270] = "private metadata"
        Image.new("RGB", (1600, 1200), "green").save(raw, "JPEG", exif=exif)
        result = normalize_cover(raw.getvalue())
        with Image.open(io.BytesIO(result)) as image:
            self.assertEqual(image.format, "JPEG")
            self.assertEqual(image.size, (800, 600))
            self.assertFalse(image.getexif())
        self.assertNotIn(b"private metadata", result)
        self.assertLessEqual(len(result), 512 * 1024)

    def test_bad_oversized_and_linked_artwork_is_rejected(self):
        for value in [b"<svg></svg>", b"https://example.test/cover.jpg", b"\xff\xd8broken", b"x" * (MAX_COVER_BYTES + 1)]:
            self.assertIsNone(normalize_cover(value))
        def chunk(kind, data):
            return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        huge_png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 5000, 5000, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(b"\x00")) + chunk(b"IEND", b"")
        self.assertIsNone(normalize_cover(huge_png))

    def test_flac_prefers_front_cover(self):
        back, front = Picture(), Picture()
        back.type, back.data = 4, cover_png((200, 20, 20))
        front.type, front.data = 3, cover_png((20, 180, 20))
        with patch("app.services.metadata.mutagen.File", return_value=SimpleNamespace(tags={}, pictures=[back, front])):
            metadata = read_embedded_metadata(Path("unused"))
        with Image.open(io.BytesIO(metadata.cover)) as image:
            self.assertGreater(image.getpixel((0, 0))[1], 150)

    def test_ogg_picture_and_legacy_coverart(self):
        picture = Picture()
        picture.type, picture.data = 3, cover_png()
        for tags in [{"metadata_block_picture": [base64.b64encode(picture.write()).decode()]}, {"coverart": [base64.b64encode(cover_png()).decode()]}]:
            with patch("app.services.metadata.mutagen.File", return_value=SimpleNamespace(tags=tags)):
                self.assertIsNotNone(read_embedded_metadata(Path("unused")).cover)

    def test_bad_cover_warns_without_losing_tags(self):
        tags = ID3()
        tags.add(TIT2(text=["Conservar título"]))
        tags.add(APIC(type=3, mime="image/jpeg", data=b"broken"))
        with patch("app.services.metadata.mutagen.File", return_value=SimpleNamespace(tags=tags)):
            metadata = read_embedded_metadata(Path("unused"))
        self.assertEqual(metadata.title, "Conservar título")
        self.assertIsNone(metadata.cover)
        self.assertEqual(len(metadata.warnings), 1)


if __name__ == "__main__":
    unittest.main()
