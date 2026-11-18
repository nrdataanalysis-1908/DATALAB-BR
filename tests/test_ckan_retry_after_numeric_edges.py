import io
import unittest
from urllib.error import HTTPError
from unittest.mock import patch

from brasil_eleitoral.ckan.client import CKANClient


class _ValidResponse:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self, size=-1):
        return b'{"success":true,"result":{"ok":true}}'


class CKANRetryAfterNumericEdgeTests(unittest.TestCase):
    def test_non_finite_retry_after_uses_backoff_and_negative_value_clamps_to_zero(self):
        cases = (("NaN", 2.0), ("inf", 2.0), ("-5", 0.0))
        for header_value, expected_delay in cases:
            with self.subTest(retry_after=header_value):
                error = HTTPError(
                    "https://example.test/api",
                    429,
                    "rate limited",
                    {"Retry-After": header_value},
                    io.BytesIO(b"rate limited"),
                )
                with patch(
                    "brasil_eleitoral.ckan.client.urlopen",
                    side_effect=[error, _ValidResponse()],
                ):
                    with patch("brasil_eleitoral.ckan.client.random.uniform", return_value=0):
                        with patch("brasil_eleitoral.ckan.client.time.sleep") as sleep:
                            client = CKANClient(
                                "https://example.test", retries=1, backoff=2
                            )
                            self.assertEqual(
                                client.action("package_search"), {"ok": True}
                            )
                sleep.assert_called_once_with(expected_delay)


if __name__ == "__main__":
    unittest.main()
