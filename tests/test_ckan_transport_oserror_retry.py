import unittest
from unittest.mock import patch

from brasil_eleitoral.ckan.client import CKANClient, CKANError


class _ValidResponse:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self, size=-1):
        return b'{"success":true,"result":{"ok":true}}'


class CKANTransportOSErrorRetryTests(unittest.TestCase):
    @patch("brasil_eleitoral.ckan.client.urlopen")
    def test_connection_reset_is_retried(self, urlopen):
        urlopen.side_effect = [ConnectionResetError("socket reset"), _ValidResponse()]
        client = CKANClient("https://example.test", retries=1, backoff=0)

        with patch("brasil_eleitoral.ckan.client.time.sleep") as sleep:
            self.assertEqual(client.action("package_search"), {"ok": True})

        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once()

    @patch("brasil_eleitoral.ckan.client.urlopen")
    def test_exhausted_connection_reset_is_wrapped_as_ckan_error(self, urlopen):
        urlopen.side_effect = ConnectionResetError("socket reset")
        client = CKANClient("https://example.test", retries=1, backoff=0)

        with patch("brasil_eleitoral.ckan.client.time.sleep"):
            with self.assertRaisesRegex(CKANError, "failed after 2 attempts"):
                client.action("package_search")

        self.assertEqual(urlopen.call_count, 2)


if __name__ == "__main__":
    unittest.main()
