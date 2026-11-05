import hashlib
import json
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from unittest.mock import patch

from brasil_eleitoral.ingestion.downloader import (
    DownloadError, download_resource, download_resources,
)


class FakeResponse:
    def __init__(self, body, status=200, headers=None):
        self.body = body
        self.status = status
        self.headers = Message()
        for key, value in (headers or {}).items():
            self.headers[key] = value
        self.position = 0

    def __enter__(self): return self
    def __exit__(self, *args): return None
    def getcode(self): return self.status
    def read(self, size=-1):
        if size < 0: size = len(self.body) - self.position
        chunk = self.body[self.position:self.position + size]
        self.position += len(chunk)
        return chunk


class DownloaderTests(unittest.TestCase):
    @patch("brasil_eleitoral.ingestion.downloader.urlopen")
    def test_download_and_sha256(self, urlopen):
        payload = b"electoral-data"
        urlopen.return_value = FakeResponse(payload, headers={"Content-Length": str(len(payload)), "ETag": '"v1"'})
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "resource.csv"
            result = download_resource("https://example.test/resource.csv", target)
            self.assertEqual(target.read_bytes(), payload)
            self.assertEqual(result["checksum"], hashlib.sha256(payload).hexdigest())
            self.assertEqual(result["status"], "verified")

    @patch("brasil_eleitoral.ingestion.downloader.urlopen")
    def test_checksum_mismatch_never_publishes_file(self, urlopen):
        urlopen.return_value = FakeResponse(b"bad", headers={"Content-Length": "3", "ETag": '"v1"'})
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "resource.csv"
            with self.assertRaises(DownloadError):
                download_resource("https://example.test/data", target, expected_checksum="0" * 64)
            self.assertFalse(target.exists())
            self.assertTrue(target.with_name(target.name + ".part").exists())

    @patch("brasil_eleitoral.ingestion.downloader.urlopen")
    def test_resume_uses_range_and_appends_on_206(self, urlopen):
        payload = b"abcdefghij"
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "data.bin"
            partial = target.with_name(target.name + ".part")
            partial.write_bytes(payload[:4])
            partial.with_name(partial.name + ".json").write_text(json.dumps({
                "url": "https://example.test/data", "etag": '"v1"'
            }))
            urlopen.return_value = FakeResponse(payload[4:], status=206, headers={
                "Content-Range": "bytes 4-9/10", "Content-Length": "6", "ETag": '"v1"'
            })
            result = download_resource("https://example.test/data", target)
            self.assertEqual(target.read_bytes(), payload)
            self.assertIn("bytes=4-", urlopen.call_args.args[0].get_header("Range"))
            self.assertEqual(result["size_bytes"], 10)

    @patch("brasil_eleitoral.ingestion.downloader.urlopen")
    def test_manifest_records_success_and_missing_url(self, urlopen):
        payload = b"ok"
        urlopen.return_value = FakeResponse(payload, headers={"Content-Length": "2"})
        with tempfile.TemporaryDirectory() as tmp:
            result = download_resources([
                {"id": "r1", "name": "dataset.csv", "url": "https://example.test/d.csv"},
                {"id": "r2", "name": "broken.csv"},
            ], Path(tmp))
            self.assertEqual(result["resource_count"], 1)
            self.assertEqual(result["failure_count"], 1)
            manifest = json.loads((Path(tmp) / "manifest.json").read_text())
            self.assertEqual(manifest["resources"][0]["resource_id"], "r1")
            self.assertEqual(manifest["failures"][0]["resource_id"], "r2")

    def test_rejects_non_http_urls_and_sanitizes_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                download_resource("file:///etc/passwd", Path(tmp) / "x")
            result = download_resources([{"id": "x", "name": "../../evil.csv"}], Path(tmp))
            self.assertEqual(result["failure_count"], 1)


    @patch("brasil_eleitoral.ingestion.downloader.urlopen")
    def test_resume_rejects_inconsistent_content_range(self, urlopen):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "data.bin"
            partial = target.with_name(target.name + ".part")
            partial.write_bytes(b"abcd")
            partial.with_name(partial.name + ".json").write_text(json.dumps({
                "url": "https://example.test/data", "etag": '"v1"'
            }))
            urlopen.return_value = FakeResponse(b"efghij", status=206, headers={
                "Content-Range": "bytes 3-8/9", "Content-Length": "6", "ETag": '"v1"'
            })
            with self.assertRaises(DownloadError):
                download_resource("https://example.test/data", target)

    @patch("brasil_eleitoral.ingestion.downloader.urlopen")
    def test_fresh_download_rejects_unsolicited_partial_response(self, urlopen):
        urlopen.return_value = FakeResponse(b"partial", status=206, headers={
            "Content-Range": "bytes 0-6/20", "Content-Length": "7", "ETag": '"v1"'
        })
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "data.bin"
            with self.assertRaises(DownloadError):
                download_resource("https://example.test/data", target)
            self.assertFalse(target.exists())


    @patch("brasil_eleitoral.ingestion.downloader.urlopen")
    def test_checksum_failure_forces_clean_transfer_on_next_run(self, urlopen):
        urlopen.side_effect = [
            FakeResponse(b"bad", headers={"Content-Length": "3", "ETag": '"v1"'}),
            FakeResponse(b"good", headers={"Content-Length": "4", "ETag": '"v2"'}),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "resource.bin"
            with self.assertRaises(DownloadError):
                download_resource(
                    "https://example.test/data", target, expected_checksum=hashlib.sha256(b"good").hexdigest()
                )
            partial = target.with_name(target.name + ".part")
            state = partial.with_name(partial.name + ".json")
            self.assertTrue(partial.exists())
            self.assertFalse(state.exists())

            result = download_resource(
                "https://example.test/data", target, expected_checksum=hashlib.sha256(b"good").hexdigest()
            )
            self.assertEqual(target.read_bytes(), b"good")
            self.assertEqual(result["status"], "verified")
            self.assertEqual(urlopen.call_count, 2)


    @patch("brasil_eleitoral.ingestion.downloader.urlopen")
    def test_rejects_two_resources_that_sanitize_to_the_same_filename(self, urlopen):
        urlopen.return_value = FakeResponse(b"first", headers={"Content-Length": "5"})
        with tempfile.TemporaryDirectory() as tmp:
            result = download_resources([
                {"id": "r1", "name": "../dataset.csv", "url": "https://example.test/one"},
                {"id": "r2", "name": "dataset.csv", "url": "https://example.test/two"},
            ], Path(tmp))
            self.assertEqual(result["resource_count"], 1)
            self.assertEqual(result["failure_count"], 1)
            self.assertEqual(result["failures"][0]["resource_id"], "r2")
            self.assertEqual(urlopen.call_count, 1)
            self.assertEqual((Path(tmp) / "dataset.csv").read_bytes(), b"first")

    @patch("brasil_eleitoral.ingestion.downloader.urlopen")
    def test_rejects_case_insensitive_filename_collisions(self, urlopen):
        urlopen.return_value = FakeResponse(b"first", headers={"Content-Length": "5"})
        with tempfile.TemporaryDirectory() as tmp:
            result = download_resources([
                {"id": "upper", "name": "Dataset.csv", "url": "https://example.test/one"},
                {"id": "lower", "name": "dataset.csv", "url": "https://example.test/two"},
            ], Path(tmp))
            self.assertEqual(result["resource_count"], 1)
            self.assertEqual(result["failure_count"], 1)
            self.assertIn("collides", result["failures"][0]["error"])
            self.assertEqual(urlopen.call_count, 1)

if __name__ == "__main__":
    unittest.main()
