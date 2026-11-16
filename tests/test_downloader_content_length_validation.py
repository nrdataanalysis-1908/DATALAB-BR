import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from brasil_eleitoral.ingestion.downloader import DownloadError, download_resource
from test_downloader import FakeResponse


class ContentLengthValidationTests(unittest.TestCase):
    @patch("brasil_eleitoral.ingestion.downloader.urlopen")
    def test_full_response_rejects_non_numeric_content_length(self, urlopen):
        urlopen.return_value = FakeResponse(
            b"payload", headers={"Content-Length": "unknown"}
        )
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "resource.bin"
            with self.assertRaisesRegex(DownloadError, "Content-Length"):
                download_resource(
                    "https://example.test/resource", destination, retries=0
                )
            self.assertFalse(destination.exists())

    @patch("brasil_eleitoral.ingestion.downloader.urlopen")
    def test_resumed_response_rejects_empty_content_length_header(self, urlopen):
        url = "https://example.test/resource"
        urlopen.return_value = FakeResponse(
            b"suffix",
            status=206,
            headers={
                "Content-Range": "bytes 6-11/12",
                "Content-Length": "",
                "ETag": '"v1"',
            },
        )
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "resource.bin"
            partial = destination.with_name(destination.name + ".part")
            state = partial.with_name(partial.name + ".json")
            partial.write_bytes(b"prefix")
            state.write_text(
                json.dumps({"url": url, "etag": '"v1"'}), encoding="utf-8"
            )

            with self.assertRaisesRegex(DownloadError, "Content-Length"):
                download_resource(url, destination, retries=0)

            self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
