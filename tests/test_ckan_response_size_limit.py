import unittest
from unittest.mock import patch

import brasil_eleitoral.ckan.client as ckan_client
from brasil_eleitoral.ckan.client import CKANClient, CKANError


class CKANResponseSizeLimitTests(unittest.TestCase):
    def test_oversized_response_is_rejected_before_json_parsing(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

            def read(self, size):
                return b"x" * size

        with patch.object(ckan_client, "_MAX_RESPONSE_BYTES", 8):
            with patch.object(ckan_client, "urlopen", return_value=Response()) as urlopen:
                client = CKANClient("https://example.test", retries=0)
                with self.assertRaisesRegex(CKANError, "safety limit"):
                    client.action("package_search")
                urlopen.assert_called_once()


if __name__ == "__main__":
    unittest.main()
