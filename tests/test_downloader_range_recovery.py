import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError
from unittest.mock import patch

from brasil_eleitoral.ingestion.downloader import download_resource
from test_downloader import FakeResponse


class DownloaderRangeRecoveryTests(unittest.TestCase):
    @patch("brasil_eleitoral.ingestion.downloader.urlopen")
    def test_http_416_discards_stale_partial_and_restarts_full_transfer(self, urlopen):
        url = "https://example.test/resource"
        error = HTTPError(url, 416, "Range not satisfiable", None, None)
        urlopen.side_effect = [
            error,
            FakeResponse(b"complete", headers={"Content-Length": "8", "ETag": '"v2"'}),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "resource.bin"
            partial = destination.with_name(destination.name + ".part")
            partial.write_bytes(b"stale-partial-data")
            partial.with_name(partial.name + ".json").write_text(
                json.dumps({"url": url, "etag": '"v1"'}), encoding="utf-8"
            )

            result = download_resource(url, destination, retries=1, backoff=0)

            self.assertEqual(destination.read_bytes(), b"complete")
            self.assertEqual(result["status"], "verified")
            self.assertEqual(urlopen.call_count, 2)
            self.assertIsNotNone(urlopen.call_args_list[0].args[0].get_header("Range"))
            self.assertIsNone(urlopen.call_args_list[1].args[0].get_header("Range"))


if __name__ == "__main__":
    unittest.main()
