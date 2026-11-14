import unittest

from brasil_eleitoral.ckan.client import CKANClient


class CKANClientLimitsTests(unittest.TestCase):
    def test_rejects_unbounded_timeout_retry_and_backoff_settings(self):
        for options in ({"timeout": 601}, {"retries": 11}, {"backoff": 301}):
            with self.subTest(options=options):
                with self.assertRaises(ValueError):
                    CKANClient("https://example.test", **options)

    def test_rejects_control_characters_in_user_agent(self):
        for user_agent in ("DataLab\nInjected: value", "DataLab\rInjected: value", "DataLab\x7f"):
            with self.subTest(user_agent=user_agent):
                with self.assertRaisesRegex(ValueError, "control characters"):
                    CKANClient("https://example.test", user_agent=user_agent)

    def test_accepts_maximum_documented_retry_configuration(self):
        client = CKANClient(
            "https://example.test", timeout=600, retries=10, backoff=300,
            user_agent="DATALAB-BR/1.0",
        )
        self.assertEqual(client.retries, 10)


if __name__ == "__main__":
    unittest.main()
