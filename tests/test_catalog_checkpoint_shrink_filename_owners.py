import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from brasil_eleitoral.ckan.catalog import discover_catalog


class CatalogShrinkFilenameOwnershipTests(unittest.TestCase):
    def test_catalog_shrink_releases_names_from_the_previous_snapshot(self):
        class Client:
            base_url = "https://dadosabertos.tse.jus.br"

            def __init__(self):
                self.calls = []

            def search_page(self, *, start, rows):
                self.calls.append((start, rows))
                if start == 1:
                    return {"count": 0, "results": []}
                return {
                    "count": 1,
                    "results": [{"name": "OLD-DATASET", "resources": []}],
                }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            previous = b'{"name":"old-dataset"}\n'
            (root / "old-dataset.json").write_bytes(previous)
            (root / ".ckan_checkpoint.json").write_text(
                json.dumps({
                    "source_url": Client.base_url,
                    "next_start": 1,
                    "total": 1,
                    "seen": {
                        "old-dataset": hashlib.sha256(previous).hexdigest()
                    },
                }),
                encoding="utf-8",
            )

            client = Client()
            manifest = discover_catalog(client, root, page_size=1)

            self.assertEqual(client.calls, [(1, 1), (0, 1)])
            self.assertEqual(manifest["dataset_count"], 1)
            self.assertTrue(manifest["complete"])
            self.assertEqual(
                json.loads((root / "OLD-DATASET.json").read_text(encoding="utf-8"))["name"],
                "OLD-DATASET",
            )


if __name__ == "__main__":
    unittest.main()
