import tempfile
import unittest
from pathlib import Path

from brasil_eleitoral.ckan.catalog import _dataset_filename, discover_catalog


class PortableDatasetFilenameTests(unittest.TestCase):
    def test_windows_device_names_receive_non_reserved_filenames(self):
        names = ("CON", "nul", "COM1", "LPT³", "CON.archive")
        paths = [_dataset_filename(name) for name in names]

        self.assertEqual(len(paths), len(set(paths)))
        for path in paths:
            self.assertTrue(path.startswith("_dataset_"))
            self.assertTrue(path.endswith(".json"))
            self.assertNotIn("/", path)
            self.assertNotIn("\\", path)

    def test_trailing_dot_names_do_not_alias_normal_windows_paths(self):
        self.assertEqual(_dataset_filename("regular-dataset"), "regular-dataset.json")
        self.assertTrue(_dataset_filename("dataset.").startswith("_dataset_"))

    def test_reserved_dataset_name_is_written_and_manifest_uses_same_safe_path(self):
        class Client:
            base_url = "https://example.test"

            def search_page(self, *, start, rows):
                return {"count": 1, "results": [{"name": "NUL", "resources": []}]}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = discover_catalog(Client(), root, page_size=10)
            expected = _dataset_filename("NUL")

            self.assertTrue((root / expected).is_file())
            self.assertEqual(manifest["datasets"][0]["path"], expected)


if __name__ == "__main__":
    unittest.main()
