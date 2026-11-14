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


class _ValidResponse:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self, size=-1):
        return b'{"success":true,"result":{"ok":true}}'


class CKANRetryAfterTests(unittest.TestCase):
    def test_numeric_retry_after_is_honored_and_error_stream_is_closed(self):
        import io

        body = io.BytesIO(b"rate limited")
        error = HTTPError(
            "https://example.test/api",
            429,
            "rate limited",
            {"Retry-After": "7"},
            body,
        )
        with patch(
            "brasil_eleitoral.ckan.client.urlopen",
            side_effect=[error, _ValidResponse()],
        ):
            with patch("brasil_eleitoral.ckan.client.time.sleep") as sleep:
                client = CKANClient("https://example.test", retries=1, backoff=0.1)
                self.assertEqual(client.action("package_search"), {"ok": True})

        sleep.assert_called_once_with(7.0)
        self.assertTrue(body.closed)


    def test_http_date_retry_after_uses_server_deadline(self):
        import io

        error = HTTPError(
            "https://example.test/api",
            503,
            "temporarily unavailable",
            {"Retry-After": "Thu, 01 Jan 1970 00:00:10 GMT"},
            io.BytesIO(b"busy"),
        )
        with patch(
            "brasil_eleitoral.ckan.client.urlopen",
            side_effect=[error, _ValidResponse()],
        ):
            with patch("brasil_eleitoral.ckan.client.time.time", return_value=2):
                with patch("brasil_eleitoral.ckan.client.time.sleep") as sleep:
                    client = CKANClient("https://example.test", retries=1, backoff=0)
                    self.assertEqual(client.action("package_search"), {"ok": True})

        sleep.assert_called_once_with(8.0)


    def test_invalid_retry_after_falls_back_to_exponential_backoff(self):
        import io

        error = HTTPError(
            "https://example.test/api",
            429,
            "rate limited",
            {"Retry-After": "not-a-date"},
            io.BytesIO(b"rate limited"),
        )
        with patch(
            "brasil_eleitoral.ckan.client.urlopen",
            side_effect=[error, _ValidResponse()],
        ):
            with patch("brasil_eleitoral.ckan.client.random.uniform", return_value=0):
                with patch("brasil_eleitoral.ckan.client.time.sleep") as sleep:
                    client = CKANClient("https://example.test", retries=1, backoff=2)
                    self.assertEqual(client.action("package_search"), {"ok": True})

        sleep.assert_called_once_with(2.0)


    def test_retry_after_is_capped_by_global_backoff_limit(self):
        import io

        error = HTTPError(
            "https://example.test/api",
            429,
            "rate limited",
            {"Retry-After": "9999"},
            io.BytesIO(b"rate limited"),
        )
        with patch(
            "brasil_eleitoral.ckan.client.urlopen",
            side_effect=[error, _ValidResponse()],
        ):
            with patch("brasil_eleitoral.ckan.client.time.sleep") as sleep:
                client = CKANClient("https://example.test", retries=1, backoff=0)
                self.assertEqual(client.action("package_search"), {"ok": True})

        sleep.assert_called_once_with(300.0)


if __name__ == "__main__":
    unittest.main()

    def test_past_http_date_retry_after_is_clamped_to_zero(self):
        import io

        error = HTTPError(
            "https://example.test/api",
            429,
            "rate limited",
            {"Retry-After": "Wed, 31 Dec 1969 23:59:50 GMT"},
            io.BytesIO(b"rate limited"),
        )
        with patch(
            "brasil_eleitoral.ckan.client.urlopen",
            side_effect=[error, _ValidResponse()],
        ):
            with patch("brasil_eleitoral.ckan.client.time.time", return_value=0):
                with patch("brasil_eleitoral.ckan.client.time.sleep") as sleep:
                    client = CKANClient("https://example.test", retries=1, backoff=1)
                    self.assertEqual(client.action("package_search"), {"ok": True})

        sleep.assert_called_once_with(0.0)

