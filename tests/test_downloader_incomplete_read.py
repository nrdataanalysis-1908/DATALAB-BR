import json
import tempfile
import unittest
from email.message import Message
from http.client import IncompleteRead
from pathlib import Path
from unittest.mock import patch

from brasil_eleitoral.ingestion.downloader import DownloadError, download_resource


class _Response:
    def __init__(self, body, *, status=200, headers=None):
        self.body = body
        self.status = status
        self.headers = Message()
        for key, value in (headers or {}).items():
            self.headers[key] = value
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


class _TruncatedResponse(_Response):
    def __init__(self):
        super().__init__(
            b"abc",
            headers={"Content-Length": "10", "ETag": '"v1"'},
        )
        self.failed = False

    def read(self, size=-1):
        if self.failed:
            raise IncompleteRead(b"def", 4)
        self.failed = True
        return b"abc"


class DownloaderIncompleteReadTests(unittest.TestCase):
    @patch("brasil_eleitoral.ingestion.downloader.time.sleep")
    @patch("brasil_eleitoral.ingestion.downloader.urlopen")
    def test_incomplete_read_preserves_bytes_and_resumes_with_range(self, urlopen, sleep):
        url = "https://example.test/resource"
        urlopen.side_effect = [
            _TruncatedResponse(),
            _Response(
                b"ghij",
                status=206,
                headers={
                    "Content-Range": "bytes 6-9/10",
                    "Content-Length": "4",
                    "ETag": '"v1"',
                },
            ),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "resource.bin"
            result = download_resource(url, destination, retries=1, backoff=0)

            self.assertEqual(destination.read_bytes(), b"abcdefghij")
            self.assertEqual(result["status"], "verified")
            self.assertEqual(urlopen.call_count, 2)
            self.assertEqual(
                urlopen.call_args_list[1].args[0].get_header("Range"),
                "bytes=6-",
            )
            sleep.assert_called_once_with(0)

    @patch("brasil_eleitoral.ingestion.downloader.urlopen")
    def test_exhausted_incomplete_read_keeps_partial_for_diagnosis(self, urlopen):
        urlopen.return_value = _TruncatedResponse()

        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "resource.bin"
            partial = destination.with_name(destination.name + ".part")
            state = partial.with_name(partial.name + ".json")

            with self.assertRaises(DownloadError):
                download_resource(url, destination, retries=0)

            self.assertFalse(destination.exists())
            self.assertEqual(partial.read_bytes(), b"abcdef")
            self.assertEqual(json.loads(state.read_text(encoding="utf-8"))["etag"], '"v1"')


if __name__ == "__main__":
    unittest.main()
