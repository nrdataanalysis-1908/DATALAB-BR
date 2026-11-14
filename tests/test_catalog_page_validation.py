import tempfile
import unittest
from pathlib import Path

from brasil_eleitoral.ckan.catalog import discover_catalog


class CatalogPageValidationTests(unittest.TestCase):
    class Client:
        base_url = "https://example.test"

        def __init__(self, page):
            self.page = page

        def search_page(self, *, start, rows):
            return self.page

    def test_rejects_malformed_page_envelopes(self):
        invalid_pages = (
            None,
            {"count": True, "results": []},
            {"count": "1", "results": []},
            {"count": -1, "results": []},
            {"count": 1, "results": {}},
            {"count": 1, "results": [{}, {}]},
        )
        with tempfile.TemporaryDirectory() as tmp:
            for page in invalid_pages:
                with self.subTest(page=page):
                    with self.assertRaises(ValueError):
                        discover_catalog(self.Client(page), Path(tmp) / "catalog", page_size=1)


if __name__ == "__main__":
    unittest.main()
