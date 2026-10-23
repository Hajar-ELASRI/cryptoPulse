"""Exercise range recovery against a local server that deliberately drops a response."""

import importlib.util
import io
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from scripts.historical_loader import download_archive


@unittest.skipUnless(importlib.util.find_spec("requests"), "requests needed for HTTP recovery checks")
class HistoryDownloadTests(unittest.TestCase):
    def exercise(self, *, ignore_range=False):
        import requests

        payload = io.BytesIO()
        with ZipFile(payload, "w") as archive:
            archive.writestr("trades.csv", b"x" * (2 * 1024 * 1024))
        data = payload.getvalue()
        seen = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_GET(self):
                byte_range = self.headers.get("Range")
                seen.append(byte_range)
                if not ignore_range and len(seen) == 1:
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data[:1024 * 1024 + 128])
                    self.close_connection = True
                    return
                start = int(byte_range.removeprefix("bytes=").removesuffix("-")) if byte_range and not ignore_range else 0
                self.send_response(206 if start else 200)
                self.send_header("Content-Length", str(len(data) - start))
                if start:
                    self.send_header("Content-Range", f"bytes {start}-{len(data)-1}/{len(data)}")
                self.end_headers()
                self.wfile.write(data[start:])

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with TemporaryDirectory() as temporary, requests.Session() as session:
                directory = Path(temporary)
                if ignore_range:
                    (directory / "TESTBTC-trades-2025-01.zip.part").write_bytes(data[:100])
                with patch("scripts.historical_loader.BASE_URL", f"http://127.0.0.1:{server.server_port}"), patch("scripts.historical_loader.time.sleep"):
                    result = download_archive(session, "TESTBTC", "2025-01", directory)
                self.assertEqual(result.read_bytes(), data)
                self.assertFalse((directory / (result.name + ".part")).exists())
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
        return seen

    def test_interrupted_response_resumes_at_committed_byte(self):
        self.assertEqual(self.exercise(), [None, "bytes=1048576-"])

    def test_full_response_to_range_replaces_partial_file(self):
        self.assertEqual(self.exercise(ignore_range=True), ["bytes=100-"])
