import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from brasil_eleitoral.ingestion.downloader import DownloadError, download_resource
from test_downloader import FakeResponse


class ExistingDestinationPreservationTests(unittest.TestCase):
    @patch("brasil_eleitoral.ingestion.downloader.urlopen")
    def test_checksum_mismatch_preserves_previous_destination(self, urlopen):
        urlopen.return_value = FakeResponse(
            b"bad", headers={"Content-Length": "3", "ETag": '"v1"'}
        )
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "resource.bin"
            destination.write_bytes(b"previous verified content")

            with self.assertRaisesRegex(DownloadError, "Checksum mismatch"):
                download_resource(
                    "https://example.test/resource",
                    destination,
                    expected_checksum="0" * 64,
                    retries=0,
                )

            self.assertEqual(destination.read_bytes(), b"previous verified content")

    @patch("brasil_eleitoral.ingestion.downloader.urlopen")
    def test_content_length_mismatch_preserves_previous_destination(self, urlopen):
        urlopen.return_value = FakeResponse(
            b"short", headers={"Content-Length": "99", "ETag": '"v1"'}
        )
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "resource.bin"
            destination.write_bytes(b"previous verified content")

            with self.assertRaisesRegex(DownloadError, "Truncated response"):
                download_resource(
                    "https://example.test/resource", destination, retries=0
                )

            self.assertEqual(destination.read_bytes(), b"previous verified content")


if __name__ == "__main__":
    unittest.main()
