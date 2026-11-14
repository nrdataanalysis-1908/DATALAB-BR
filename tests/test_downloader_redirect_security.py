import tempfile
import unittest
from email.message import Message
from pathlib import Path
from unittest.mock import patch

from brasil_eleitoral.ingestion.downloader import DownloadError, download_resource


class _RedirectedResponse:
    def __init__(self, final_url, body=b"payload"):
        self.final_url = final_url
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

    def geturl(self):
        return self.final_url

    def read(self, size=-1):
        if size < 0:
            size = len(self.body) - self.position
        chunk = self.body[self.position:self.position + size]
        self.position += len(chunk)
        return chunk


class DownloaderRedirectSecurityTests(unittest.TestCase):
    @patch("brasil_eleitoral.ingestion.downloader.urlopen")
    def test_https_download_rejects_redirect_to_plain_http(self, urlopen):
        urlopen.return_value = _RedirectedResponse(
            "http://cdn.example.test/resource"
        )

        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "resource.bin"
            with self.assertRaisesRegex(DownloadError, "HTTPS.*redirect"):
                download_resource(
                    "https://example.test/resource",
                    destination,
                )

            self.assertFalse(destination.exists())
            self.assertEqual(urlopen.call_count, 1)

    @patch("brasil_eleitoral.ingestion.downloader.urlopen")
    def test_https_download_allows_redirect_to_another_https_host(self, urlopen):
        urlopen.return_value = _RedirectedResponse(
            "https://cdn.example.test/resource"
        )

        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "resource.bin"
            result = download_resource(
                "https://example.test/resource",
                destination,
            )

            self.assertEqual(destination.read_bytes(), b"payload")
            self.assertEqual(result["status"], "verified")


if __name__ == "__main__":
    unittest.main()
