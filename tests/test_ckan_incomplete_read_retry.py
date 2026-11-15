import unittest
from http.client import IncompleteRead
from unittest.mock import patch

from brasil_eleitoral.ckan.client import CKANClient


class _ValidResponse:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self, size=-1):
        return b'{"success":true,"result":{"ok":true}}'


class CKANIncompleteReadRetryTests(unittest.TestCase):
    @patch("brasil_eleitoral.ckan.client.urlopen")
    def test_incomplete_json_response_retries_from_a_fresh_request(self, urlopen):
        urlopen.side_effect = [
            IncompleteRead(b'{"success":', 10),
            _ValidResponse(),
        ]
        client = CKANClient("https://example.test", retries=1, backoff=0)

        with patch("brasil_eleitoral.ckan.client.time.sleep") as sleep:
            self.assertEqual(client.action("package_search"), {"ok": True})

        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once()


if __name__ == "__main__":
    unittest.main()
