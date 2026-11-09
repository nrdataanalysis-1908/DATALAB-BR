import unittest
from urllib.error import HTTPError
from unittest.mock import patch

from brasil_eleitoral.ckan.client import CKANClient, CKANError


class CKANRetryBackoffTests(unittest.TestCase):
    def test_exponential_delay_never_exceeds_global_cap(self):
        error = HTTPError("https://example.test/api", 429, "rate limited", None, None)
        with patch("brasil_eleitoral.ckan.client.urlopen", side_effect=error):
            with patch("brasil_eleitoral.ckan.client.random.uniform", return_value=0):
                with patch("brasil_eleitoral.ckan.client.time.sleep") as sleep:
                    client = CKANClient(
                        "https://example.test", timeout=1, retries=10, backoff=300
                    )
                    with self.assertRaises(CKANError):
                        client.action("package_search")
        self.assertEqual(sleep.call_count, 10)
        self.assertTrue(all(call.args[0] <= 300 for call in sleep.call_args_list))


if __name__ == "__main__":
    unittest.main()
