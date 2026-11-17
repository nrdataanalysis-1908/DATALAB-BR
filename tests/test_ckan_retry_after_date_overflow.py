import io
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from brasil_eleitoral.ckan.client import CKANClient


class _ValidResponse:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self, size=-1):
        return b'{"success":true,"result":{"recovered":true}}'


class _UnrepresentableDate:
    tzinfo = None

    def replace(self, **kwargs):
        return self

    def timestamp(self):
        raise OSError("platform timestamp range exceeded")


class RetryAfterDateOverflowTests(unittest.TestCase):
    def test_unrepresentable_http_date_falls_back_to_exponential_backoff(self):
        for error_type in (OSError, OverflowError):
            with self.subTest(error_type=error_type.__name__):
                date_value = _UnrepresentableDate()
                def fail_timestamp():
                    raise error_type("timestamp out of range")
                date_value.timestamp = fail_timestamp
                error = HTTPError(
                    "https://example.test/api",
                    429,
                    "rate limited",
                    {"Retry-After": "Tue, 17 Nov 2026 08:00:00 GMT"},
                    io.BytesIO(b"rate limited"),
                )
                with patch(
                    "brasil_eleitoral.ckan.client.urlopen",
                    side_effect=[error, _ValidResponse()],
                ) as urlopen:
                    with patch(
                        "brasil_eleitoral.ckan.client.parsedate_to_datetime",
                        return_value=date_value,
                    ):
                        with patch("brasil_eleitoral.ckan.client.random.uniform", return_value=0):
                            with patch("brasil_eleitoral.ckan.client.time.sleep") as sleep:
                                client = CKANClient(
                                    "https://example.test", retries=1, backoff=3
                                )
                                self.assertEqual(
                                    client.action("package_search"), {"recovered": True}
                                )
                self.assertEqual(urlopen.call_count, 2)
                sleep.assert_called_once_with(3.0)


if __name__ == "__main__":
    unittest.main()