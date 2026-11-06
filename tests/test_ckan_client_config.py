import unittest

from brasil_eleitoral.ckan.client import CKANClient


class CKANClientConfigurationTests(unittest.TestCase):
    def test_rejects_non_http_base_urls_and_embedded_credentials(self):
        for url in (
            "file:///tmp/catalog",
            "ftp://example.test",
            "https:///missing-host",
            "https://user:secret@example.test",
            "https://example.test:invalid",
        ):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    CKANClient(url)

    def test_rejects_invalid_timeout(self):
        for timeout in (0, -1, True, float("nan"), float("inf"), "30"):
            with self.subTest(timeout=timeout):
                with self.assertRaises(ValueError):
                    CKANClient("https://example.test", timeout=timeout)

    def test_rejects_invalid_retry_count(self):
        for retries in (-1, True, 1.5):
            with self.subTest(retries=retries):
                with self.assertRaises(ValueError):
                    CKANClient("https://example.test", retries=retries)

    def test_rejects_invalid_backoff(self):
        for backoff in (-0.1, True, float("nan"), float("inf")):
            with self.subTest(backoff=backoff):
                with self.assertRaises(ValueError):
                    CKANClient("https://example.test", backoff=backoff)

    def test_rejects_empty_user_agent(self):
        for user_agent in ("", "   ", None):
            with self.subTest(user_agent=user_agent):
                with self.assertRaises(ValueError):
                    CKANClient("https://example.test", user_agent=user_agent)

    def test_accepts_valid_configuration(self):
        client = CKANClient(
            "https://example.test/",
            timeout=10,
            retries=2,
            backoff=0.25,
            user_agent="DATALAB-BR-tests/1.0",
        )
        self.assertEqual(client.base_url, "https://example.test")
        self.assertEqual(client.retries, 2)


if __name__ == "__main__":
    unittest.main()
