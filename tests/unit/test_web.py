import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.web import FrontendFiles


class ProductionFrontendTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        (root / "index.html").write_text("<html>Mnemosine</html>", encoding="utf-8")
        (root / "assets").mkdir()
        (root / "assets" / "app-12345678.js").write_text("/* built */")
        self.app = FastAPI()

        @self.app.get("/api/health")
        def health():
            return {"status": "ok"}

        self.app.mount("/", FrontendFiles(directory=root, html=True))
        self.web = TestClient(self.app)

    def tearDown(self):
        self.web.close()
        self.directory.cleanup()

    def test_refreshing_vue_route_serves_app_without_caching_html(self):
        response = self.web.get("/conexiones", headers={"Accept": "text/html"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("Mnemosine", response.text)
        self.assertEqual(response.headers["cache-control"], "no-cache")
        self.assertEqual(self.web.get("/descubrir/nombre.apellido", headers={"Accept": "text/html"}).status_code, 200)
        self.assertEqual(self.web.get("/api/health").json(), {"status": "ok"})

    def test_api_and_private_or_missing_files_never_become_html(self):
        for path in ("/api/missing", "/api", "/.env", "/.git/config", "/assets/missing.js", "/assets/missing", "/%2e%2e/secret"):
            with self.subTest(path=path):
                self.assertEqual(self.web.get(path, headers={"Accept": "text/html"}).status_code, 404)
        self.assertEqual(self.web.post("/conexiones").status_code, 405)

    def test_built_asset_is_cached_and_missing_asset_is_404(self):
        result = self.web.get("/assets/app-12345678.js")
        self.assertEqual(result.status_code, 200)
        self.assertIn("immutable", result.headers["cache-control"])
        self.assertEqual(result.headers["x-content-type-options"], "nosniff")
