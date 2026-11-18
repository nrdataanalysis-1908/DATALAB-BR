import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from brasil_eleitoral.ingestion.downloader import download_resource


class DownloadUrlWhitespaceTests(unittest.TestCase):
    @patch("brasil_eleitoral.ingestion.downloader.urlopen")
    def test_rejects_internal_whitespace_before_network_request(self, urlopen):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "resource.bin"
            with self.assertRaisesRegex(ValueError, "trimmed HTTP"):
                download_resource(
                    "https://example.test/path with space", destination
                )
        urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
