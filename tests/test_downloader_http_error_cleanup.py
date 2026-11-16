import io
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from brasil_eleitoral.ingestion.downloader import DownloadError, download_resource


class _Response:
    def __init__(self, body):
        self.body = body
        self.status = 200
        self.headers = Message({"Content-Length": str(len(body))})
        self.position = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def getcode(self):
        return self.status

    def read(self, size=-1):
        if size < 0:
            size = len(self.body) - self.position
        chunk = self.body[self.position:self.position + size]
        self.position += len(chunk)
        return chunk


class DownloaderHTTPErrorCleanupTests(unittest.TestCase):
    @patch("brasil_eleitoral.ingestion.downloader.time.sleep")
    @patch("brasil_eleitoral.ingestion.downloader.urlopen")
    def test_transient_http_error_body_is_closed_before_retry(self, urlopen, sleep):
        body = io.BytesIO(b"temporarily unavailable")
        error = HTTPError(
            "https://example.test/resource",
            503,
            "temporarily unavailable",
            {},
            body,
        )
        urlopen.side_effect = [error, _Response(b"complete")]

        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "resource.bin"
            result = download_resource(
                "https://example.test/resource",
                destination,
                retries=1,
                backoff=0,
            )

            self.assertEqual(destination.read_bytes(), b"complete")
            self.assertEqual(result["status"], "verified")
            self.assertTrue(body.closed)
            self.assertEqual(urlopen.call_count, 2)
            sleep.assert_called_once_with(0)

    @patch("brasil_eleitoral.ingestion.downloader.time.sleep")
    @patch("brasil_eleitoral.ingestion.downloader.urlopen")
    def test_non_retryable_http_error_body_is_closed_without_retry(self, urlopen, sleep):
        body = io.BytesIO(b"not found")
        error = HTTPError(
            "https://example.test/resource",
            404,
            "not found",
            {},
            body,
        )
        urlopen.side_effect = error

        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "resource.bin"
            with self.assertRaises(DownloadError):
                download_resource(
                    "https://example.test/resource",
                    destination,
                    retries=2,
                    backoff=0,
                )

            self.assertTrue(body.closed)
            self.assertFalse(destination.exists())
            self.assertEqual(urlopen.call_count, 1)
            sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
