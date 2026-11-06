import unittest
from unittest.mock import patch

from brasil_eleitoral.ckan.client import CKANClient, CKANError


class CKANClientRequestValidationTests(unittest.TestCase):
    def setUp(self):
        self.client = CKANClient("https://example.test")

    def test_action_name_cannot_escape_ckan_action_path(self):
        with patch("brasil_eleitoral.ckan.client.urlopen") as urlopen:
            for name in ("", "../package_search", "package/search", "package search", None):
                with self.subTest(name=name):
                    with self.assertRaises(ValueError):
                        self.client.action(name)
            urlopen.assert_not_called()

    def test_search_page_rejects_invalid_offsets_before_network_request(self):
        with patch.object(self.client, "action") as action:
            for start in (-1, True, 1.5, "0"):
                with self.subTest(start=start):
                    with self.assertRaises(ValueError):
                        self.client.search_page(start=start, rows=10)
            action.assert_not_called()

    def test_search_page_rejects_invalid_page_sizes_before_network_request(self):
        with patch.object(self.client, "action") as action:
            for rows in (0, -1, True, 1.5, 1001):
                with self.subTest(rows=rows):
                    with self.assertRaises(ValueError):
                        self.client.search_page(start=0, rows=rows)
            action.assert_not_called()

    def test_search_page_rejects_boolean_or_negative_remote_count(self):
        for count in (True, -1, "10"):
            with self.subTest(count=count):
                with patch.object(self.client, "action", return_value={"count": count, "results": []}):
                    with self.assertRaises(CKANError):
                        self.client.search_page(start=0, rows=10)

    def test_large_integer_timeout_and_backoff_are_rejected_cleanly(self):
        for option in ({"timeout": 10**400}, {"backoff": 10**400}):
            with self.subTest(option=option):
                with self.assertRaises(ValueError):
                    CKANClient("https://example.test", **option)


if __name__ == "__main__":
    unittest.main()
