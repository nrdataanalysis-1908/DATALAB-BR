import json
import tempfile
import unittest
from pathlib import Path

from catalog_data import load_catalog


class CatalogLoaderTests(unittest.TestCase):
    def test_loads_manifest_and_dataset_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "sample.json").write_text(json.dumps({
                "name": "sample", "title": "Dataset de teste",
                "organization": "TSE", "resources": [{"format": "CSV"}],
            }), encoding="utf-8")
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps({
                "dataset_count": 1, "complete": True,
                "datasets": [{"path": "sample.json"}],
            }), encoding="utf-8")
            manifest, datasets = load_catalog(manifest_path)
            self.assertEqual(manifest["dataset_count"], 1)
            self.assertEqual(len(datasets), 1)
            self.assertEqual(datasets[0]["name"], "sample")

    def test_missing_manifest_returns_empty_catalog(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest, datasets = load_catalog(Path(temp) / "missing.json")
            self.assertEqual(manifest, {})
            self.assertEqual(datasets, [])

    def test_rejects_parent_traversal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "outside.json").write_text(json.dumps({"name": "outside"}), encoding="utf-8")
            catalog = root / "catalog"
            catalog.mkdir()
            manifest_path = catalog / "manifest.json"
            manifest_path.write_text(json.dumps({
                "datasets": [{"path": "../outside.json"}],
            }), encoding="utf-8")
            _, datasets = load_catalog(manifest_path)
            self.assertEqual(datasets, [])

    def test_rejects_invalid_manifest_shape(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest_path = Path(temp) / "manifest.json"
            manifest_path.write_text(json.dumps({"datasets": {}}), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_catalog(manifest_path)


if __name__ == "__main__":
    unittest.main()
