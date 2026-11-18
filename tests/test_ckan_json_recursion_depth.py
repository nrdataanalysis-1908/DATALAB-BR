import unittest
from unittest.mock import patch

from brasil_eleitoral.ckan.client import CKANClient


class _ValidResponse:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self, size=-1):
        return b'{"success":true,"result":{"recovered":true}}'


class CkanJsonRecursionDepthTests(unittest.TestCase):
    def test_json_decoder_recursion_uses_the_configured_retry_policy(self):
        with patch(
            "brasil_eleitoral.ckan.client.urlopen",
            side_effect=[_ValidResponse(), _ValidResponse()],
        ) as urlopen:
            with patch(
                "brasil_eleitoral.ckan.client.json.loads",
                side_effect=[
                    RecursionError("maximum recursion depth exceeded"),
                    {"success": True, "result": {"recovered": True}},
                ],
            ) as json_loads:
                with patch("brasil_eleitoral.ckan.client.random.uniform", return_value=0):
                    with patch("brasil_eleitoral.ckan.client.time.sleep") as sleep:
                        client = CKANClient(
                            "https://example.test",
                            retries=1,
                            backoff=0,
                        )
                        self.assertEqual(
                            client.action("package_search"),
                            {"recovered": True},
                        )

        self.assertEqual(urlopen.call_count, 2)
        self.assertEqual(json_loads.call_count, 2)
        sleep.assert_called_once_with(0)


if __name__ == "__main__":
    unittest.main()
