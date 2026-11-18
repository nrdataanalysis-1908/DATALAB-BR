import json
import tempfile
import unittest
from pathlib import Path

from brasil_eleitoral.ckan.catalog import discover_catalog


class CaseInsensitiveCatalogFilenameTests(unittest.TestCase):
    def test_casefold_collisions_do_not_overwrite_an_existing_dataset(self):
        class CollidingClient:
            base_url = "https://dadosabertos.tse.jus.br"

            def search_page(self, *, start, rows):
                records = [
                    {"name": "dataset", "title": "First dataset", "resources": []},
                    {"name": "DATASET", "title": "Second dataset", "resources": []},
                ]
                return {"count": len(records), "results": records[start:start + rows]}

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = discover_catalog(CollidingClient(), root, page_size=10)

            self.assertEqual(manifest["dataset_count"], 1)
            self.assertFalse(manifest["complete"])
            stored = json.loads((root / "dataset.json").read_text(encoding="utf-8"))
            self.assertEqual(stored["title"], "First dataset")
            self.assertFalse((root / "DATASET.json").exists())


if __name__ == "__main__":
    unittest.main()
