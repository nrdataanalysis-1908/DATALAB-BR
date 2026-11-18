import unittest
from unittest.mock import MagicMock, patch

from brasil_eleitoral.ckan.client import CKANClient, CKANError


class StrictCkanJsonTests(unittest.TestCase):
    @patch("brasil_eleitoral.ckan.client.urlopen")
    def test_action_rejects_duplicate_keys_at_every_nesting_level(self, mocked_urlopen):
        payloads = (
            b'{"success": true, "success": false, "result": {}}',
            b'{"success": true, "result": {"resource": {"id": "first", "id": "second"}}}',
        )
        for payload in payloads:
            with self.subTest(payload=payload):
                response = MagicMock()
                response.__enter__.return_value.read.return_value = payload
                mocked_urlopen.return_value = response
                client = CKANClient("https://example.test", retries=0, backoff=0)

                with self.assertRaises(CKANError):
                    client.action("package_search")

        self.assertEqual(mocked_urlopen.call_count, 2)

    @patch("brasil_eleitoral.ckan.client.urlopen")
    def test_action_rejects_non_standard_nan_and_infinity_tokens(self, mocked_urlopen):
        for token in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(token=token):
                response = MagicMock()
                response.__enter__.return_value.read.return_value = (
                    ('{"success": true, "result": {"value": ' + token + '}}').encode("utf-8")
                )
                mocked_urlopen.return_value = response
                client = CKANClient("https://example.test", retries=0, backoff=0)

                with self.assertRaises(CKANError):
                    client.action("package_search")


if __name__ == "__main__":
    unittest.main()
