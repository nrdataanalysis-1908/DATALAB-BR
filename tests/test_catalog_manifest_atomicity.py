import json
import tempfile
import unittest
from pathlib import Path

from brasil_eleitoral.ckan.catalog import discover_catalog


class ManifestAtomicityTests(unittest.TestCase):
    class Client:
        base_url = "https://example.test"

        def __init__(self, pages):
            self.pages = pages
            self.calls = []

        def search_page(self, *, start, rows):
            self.calls.append((start, rows))
            return self.pages[start]

    def test_empty_page_before_reported_total_preserves_previous_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "manifest.json"
            previous = '{"complete": true, "dataset_count": 2}\n'
            manifest_path.write_text(previous, encoding="utf-8")
            client = self.Client({
                0: {"count": 2, "results": [{"name": "first-dataset", "resources": []}]},
                1: {"count": 2, "results": []},
            })

            with self.assertRaisesRegex(ValueError, "empty page before the reported total"):
                discover_catalog(client, root, page_size=1)

            self.assertEqual(manifest_path.read_text(encoding="utf-8"), previous)
            self.assertTrue((root / "first-dataset.json").is_file())
            self.assertEqual(client.calls, [(0, 1), (1, 1)])

    def test_empty_probe_after_completed_checkpoint_is_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = self.Client({
                0: {"count": 1, "results": [{"name": "stable-dataset", "resources": []}]},
            })
            first_manifest = discover_catalog(first, root, page_size=1)
            self.assertTrue(first_manifest["complete"])

            probe = self.Client({
                1: {"count": 1, "results": []},
            })
            second_manifest = discover_catalog(probe, root, page_size=1)

            self.assertTrue(second_manifest["complete"])
            self.assertEqual(second_manifest["dataset_count"], 1)
            self.assertEqual(probe.calls, [(1, 1)])


if __name__ == "__main__":
    unittest.main()
