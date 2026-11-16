import unittest
from unittest.mock import MagicMock, patch

from brasil_eleitoral.ckan.client import CKANClient, CKANError


class StrictCkanJsonTests(unittest.TestCase):
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
