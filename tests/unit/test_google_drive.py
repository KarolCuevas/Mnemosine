import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import httpx
from cryptography.fernet import Fernet

from app.integrations.google_drive import client, crypto
from app.integrations.google_drive.config import DriveError


class GoogleSecurityTests(unittest.TestCase):
    def test_ciphertext_is_bound_to_owner_and_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "keys.json"
            path.write_text(json.dumps({"current": "v1", "keys": {"v1": Fernet.generate_key().decode()}}))
            with patch.object(crypto, "get_settings", return_value=SimpleNamespace(google_token_keys_file=str(path))):
                value = crypto.encrypt({"refresh_token": "test-refresh"}, "google:1")
                self.assertNotIn("test-refresh", value)
                self.assertEqual(crypto.decrypt(value, "google:1")["refresh_token"], "test-refresh")
                for ciphertext, purpose in ((value, "google:2"), (value[:-8] + "tampered", "google:1")):
                    with self.assertRaises(DriveError):
                        crypto.decrypt(ciphertext, purpose)
                old_key = json.loads(path.read_text())["keys"]["v1"]
                path.write_text(json.dumps({"current": "v2", "keys": {"v1": old_key, "v2": Fernet.generate_key().decode()}}))
                self.assertEqual(crypto.decrypt(value, "google:1")["refresh_token"], "test-refresh")
                self.assertTrue(crypto.encrypt("new", "google:1").startswith("v2:"))

    def test_http_boundaries_and_error_redaction(self):
        real_client = httpx.Client
        scenarios = [
            (httpx.Response(401, json={"error": "invalid_token", "detail": "PRIVATE_SECRET"}), "reauth_required"),
            (httpx.Response(429, json={"error": "PRIVATE_SECRET"}), "rate_limited"),
            (httpx.Response(503, text="PRIVATE_SECRET"), "unavailable"),
            (httpx.Response(200, json=[]), "unavailable"),
            (httpx.Response(200, content=b" " * (1024 * 1024 + 1)), "unavailable"),
            (httpx.Response(302, headers={"Location": "https://untrusted.invalid"}), "unavailable"),
        ]
        for response, code in scenarios:
            with self.subTest(code=code), patch.object(client.httpx, "Client", side_effect=lambda **kw: real_client(transport=httpx.MockTransport(lambda request: response), **kw)):
                with self.assertRaises(DriveError) as raised:
                    client.request("GET", client.API + "about", token="PRIVATE_SECRET")
                self.assertEqual(raised.exception.code, code)
                self.assertNotIn("PRIVATE_SECRET", str(raised.exception))

    def test_already_revoked_token_can_disconnect(self):
        real_client = httpx.Client
        transport = httpx.MockTransport(lambda req: httpx.Response(400, json={"error": "invalid_token"}))
        with patch.object(client.httpx, "Client", side_effect=lambda **kw: real_client(transport=transport, **kw)):
            self.assertTrue(client.revoke("already-revoked"))

    def test_metadata_rejects_unavailable_files(self):
        good = {"id": "file_a", "name": "Audio.wav", "mimeType": "audio/wav", "size": "100", "version": "1",
                "ownedByMe": True, "isAppAuthorized": True, "capabilities": {"canDownload": True}}
        bad = [{"driveId": "shared"}, {"trashed": True}, {"ownedByMe": False}, {"isAppAuthorized": False},
               {"capabilities": {"canDownload": False}}, {"mimeType": "application/vnd.google-apps.shortcut"},
               {"mimeType": "application/vnd.google-apps.folder"}, {"mimeType": None}, {"capabilities": None},
               {"ownedByMe": "false"}, {"size": "9000000000"}, {"size": "0"}]
        with patch.object(client, "get_settings", return_value=SimpleNamespace(max_upload_bytes=1024)):
            for changes in bad:
                with patch.object(client, "request", return_value={**good, **changes}), self.assertRaises(DriveError):
                    client.file_metadata("token", "file_a")
            with patch.object(client, "request", return_value=good):
                self.assertFalse(client.file_metadata("token", "file_a")["audio_validated"])
                with self.assertRaises(DriveError):
                    client.file_metadata("token", "../about")

    def test_malformed_identity_is_rejected(self):
        for user in (None, [], "wrong", {}, {"permissionId": ""}):
            with patch.object(client, "request", return_value={"user": user}), self.assertRaises(DriveError):
                client.identity("token")


if __name__ == "__main__":
    unittest.main()
