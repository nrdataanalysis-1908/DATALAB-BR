import tempfile
import unittest
from pathlib import Path

from brasil_eleitoral.ckan.catalog import _atomic_json


class StrictCatalogJsonTests(unittest.TestCase):
    def test_non_finite_numbers_are_rejected_without_replacing_existing_file(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "manifest.json"
                original = '{"complete": true}\n'
                path.write_text(original, encoding="utf-8")

                with self.assertRaises(ValueError):
                    _atomic_json(path, {"value": value})

                self.assertEqual(path.read_text(encoding="utf-8"), original)
                self.assertEqual(list(Path(tmp).glob("*.tmp")), [])
                self.assertEqual(list(Path(tmp).glob(".manifest.json.*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
