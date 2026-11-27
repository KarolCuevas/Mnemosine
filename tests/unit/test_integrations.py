import json
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

import httpx

from app.integrations.catalog.contract import CatalogError
from app.integrations.catalog.providers.musicbrainz import MusicBrainzAdapter, literal, normalize, retry_seconds
from app.services.external_catalog import make_cursor, cursor_offset
from app.storage.contract import DestinationExistsError, ObjectState, FileTooLargeError
from app.storage.local import LocalStorageAdapter

RECORDING_ID = "11111111-1111-4111-8111-111111111111"


class CatalogUnitTests(unittest.TestCase):
    def test_normalize_whitelist_and_multiple_releases(self):
        raw = {"id": RECORDING_ID, "title": "Mismo nombre", "score": 100, "tags": [{"name": "privado"}],
               "annotation": "no persistir", "rating": {"value": 4}, "releases": [
                   {"id": "22222222-2222-4222-8222-222222222222", "title": "Edición A"},
                   {"id": "33333333-3333-4333-8333-333333333333", "title": "Edición B"}]}
        record = normalize(raw).model_dump()
        self.assertEqual(len(record["releases"]), 2)
        self.assertEqual(record["artists"], [])
        self.assertIsNone(record["duration_ms"])
        self.assertNotIn("score", record)
        self.assertNotIn("tags", record)
        self.assertNotIn("annotation", record)
        self.assertNotIn("album", record)

    def test_literal_cannot_inject_lucene(self):
        value = literal('x" OR artist:* (live) + test\\')
        self.assertIn('\\"', value)
        self.assertIn('artist\\:\\*', value)
        self.assertTrue(value.startswith('"') and value.endswith('"'))

    def test_cursor_bound_to_query_and_signed(self):
        cursor = make_cursor(20, "query-a")
        self.assertEqual(cursor_offset(cursor, "query-a"), 20)
        for invalid, key in [(cursor, "query-b"), (cursor + "x", "query-a"), ("bad", "query-a")]:
            with self.assertRaises(CatalogError):
                cursor_offset(invalid, key)

    def test_provider_errors_are_sanitized_and_bounded(self):
        original_client = httpx.Client
        for status, expected in [(401, 502), (403, 502), (404, 404), (429, 429), (500, 502), (503, 429)]:
            transport = httpx.MockTransport(lambda request: httpx.Response(status, text="secret-provider-message", headers={"Retry-After": "12"}))
            with patch.object(MusicBrainzAdapter, "enabled", True), patch("app.integrations.catalog.providers.musicbrainz.provider_slot", return_value=nullcontext()), patch("app.integrations.catalog.providers.musicbrainz.httpx.Client", side_effect=lambda **kw: original_client(transport=transport, **kw)):
                with self.assertRaises(CatalogError) as error:
                    MusicBrainzAdapter().get_reference(RECORDING_ID)
                self.assertEqual(error.exception.status, expected)
                self.assertNotIn("secret-provider", str(error.exception))
                if status in (429, 503):
                    self.assertEqual(error.exception.retry_after, 12)

    def test_bad_provider_json(self):
        with patch.object(MusicBrainzAdapter, "_request", return_value={"recordings": [{}], "count": 1}):
            with self.assertRaises(CatalogError) as error:
                MusicBrainzAdapter().search("a", "", offset=0, limit=20)
            self.assertEqual(error.exception.status, 502)

    def test_retry_after_limits(self):
        self.assertEqual(retry_seconds("120"), 120)
        self.assertEqual(retry_seconds("nonsense"), 30)
        self.assertEqual(retry_seconds("9999999"), 86400)


class StorageUnitTests(unittest.TestCase):
    def test_source_paths_are_not_prefixed_twice(self):
        with tempfile.TemporaryDirectory() as root:
            staging = LocalStorageAdapter(root)
            source = LocalStorageAdapter(root, source_prefix="audio/subfolder")
            staged = staging.save_stream([b"0123456789"], max_bytes=20)
            source.commit(staged, "audio/subfolder/song.wav")
            self.assertEqual(b"".join(source.read_range("audio/subfolder/song.wav", 2, 3)), b"234")
            self.assertEqual(source.stat("audio/subfolder/song.wav").state, ObjectState.FOUND)
            self.assertEqual(source.stat("audio/other/song.wav").state, ObjectState.NOT_ACCESSIBLE)
            self.assertEqual(len(source.list_objects().items), 1)
            second = staging.save_stream([b"other"], max_bytes=20)
            with self.assertRaises(DestinationExistsError):
                source.commit(second, "audio/subfolder/song.wav")
            staging.discard(second)
            self.assertEqual(b"".join(source.read_range("audio/subfolder/song.wav")), b"0123456789")

    def test_stream_limit_cleans_only_own_temp(self):
        with tempfile.TemporaryDirectory() as root:
            storage = LocalStorageAdapter(root)
            active = storage.save_stream([b"active"], max_bytes=100)
            with self.assertRaises(FileTooLargeError):
                storage.save_stream([b"too-large"], max_bytes=1)
            self.assertTrue(Path(active.token).exists())
            self.assertEqual(len(list(storage.tmp_dir.iterdir())), 1)


if __name__ == "__main__":
    unittest.main()
