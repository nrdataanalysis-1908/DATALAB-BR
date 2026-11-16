import tempfile
import unittest
from email.message import Message
from pathlib import Path
from unittest.mock import patch

from brasil_eleitoral.ingestion.downloader import DownloadError, download_resource


class _RedirectedResponse:
    def __init__(self, final_url):
        self.final_url = final_url
        self.status = 200
        self.headers = Message({"Content-Length": "7"})
        self.body = b"payload"
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


class RedirectFinalUrlSecurityTests(unittest.TestCase):
    @patch("brasil_eleitoral.ingestion.downloader.urlopen")
    def test_redirected_url_with_embedded_credentials_is_rejected(self, urlopen):
        urlopen.return_value = _RedirectedResponse(
            "https://user:secret@cdn.example.test/resource"
        )
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "resource.bin"
            with self.assertRaisesRegex(DownloadError, "without credentials"):
                download_resource("https://example.test/resource", destination)
            self.assertFalse(destination.exists())

    @patch("brasil_eleitoral.ingestion.downloader.urlopen")
    def test_redirected_non_http_scheme_is_rejected(self, urlopen):
        urlopen.return_value = _RedirectedResponse("file:///tmp/private-resource")
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "resource.bin"
            with self.assertRaisesRegex(DownloadError, "absolute HTTP"):
                download_resource("https://example.test/resource", destination)
            self.assertFalse(destination.exists())

    @patch("brasil_eleitoral.ingestion.downloader.urlopen")
    def test_redirected_url_with_invalid_port_is_rejected(self, urlopen):
        urlopen.return_value = _RedirectedResponse(
            "https://cdn.example.test:invalid/resource"
        )
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "resource.bin"
            with self.assertRaisesRegex(DownloadError, "invalid authority or port"):
                download_resource("https://example.test/resource", destination)
            self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
