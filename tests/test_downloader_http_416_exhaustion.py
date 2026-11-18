import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError
from unittest.mock import patch

from brasil_eleitoral.ingestion.downloader import DownloadError, download_resource


class DownloaderRangeExhaustionTests(unittest.TestCase):
    @patch("brasil_eleitoral.ingestion.downloader.urlopen")
    def test_http_416_clears_stale_partial_even_when_retries_are_exhausted(self, urlopen):
        url = "https://example.test/resource"
        urlopen.side_effect = HTTPError(url, 416, "Range not satisfiable", None, None)

        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "resource.bin"
            partial = destination.with_name(destination.name + ".part")
            state = partial.with_name(partial.name + ".json")
            partial.write_bytes(b"stale")
            state.write_text(json.dumps({"url": url, "etag": '"v1"'}), encoding="utf-8")

            with self.assertRaises(DownloadError):
                download_resource(url, destination, retries=0, backoff=0)

            self.assertFalse(destination.exists())
            self.assertFalse(partial.exists())
            self.assertFalse(state.exists())
            self.assertEqual(urlopen.call_count, 1)


if __name__ == "__main__":
    unittest.main()
