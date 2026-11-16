import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from brasil_eleitoral.ingestion.downloader import DownloadError, download_resource
from test_downloader import FakeResponse


class MissingContentRangeTests(unittest.TestCase):
    @patch("brasil_eleitoral.ingestion.downloader.urlopen")
    def test_resumed_partial_response_requires_content_range(self, urlopen):
        url = "https://example.test/resource"
        urlopen.return_value = FakeResponse(
            b"suffix", status=206,
            headers={"Content-Length": "6", "ETag": '"v1"'},
        )
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "resource.bin"
            partial = destination.with_name(destination.name + ".part")
            state = partial.with_name(partial.name + ".json")
            partial.write_bytes(b"prefix")
            state.write_text(
                json.dumps({"url": url, "etag": '"v1"'}), encoding="utf-8"
            )

            with self.assertRaisesRegex(DownloadError, "Invalid Content-Range"):
                download_resource(url, destination, retries=0)

            self.assertFalse(destination.exists())
            self.assertEqual(partial.read_bytes(), b"prefix")


if __name__ == "__main__":
    unittest.main()
