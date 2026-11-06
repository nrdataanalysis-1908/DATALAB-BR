import tempfile
import unittest
import zipfile
from pathlib import Path

from brasil_eleitoral.ingestion.extractor import extract_zip


class ExtractionLimitTypeTests(unittest.TestCase):
    def _archive(self, root):
        path = root / "sample.zip"
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("data.csv", "id\n1\n")
        return path

    def test_size_and_entry_limits_require_positive_integers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = self._archive(root)
            invalid_options = (
                {"max_entries": True},
                {"max_entries": 1.5},
                {"max_entries": 0},
                {"max_file_size": False},
                {"max_file_size": 1.5},
                {"max_total_size": True},
                {"max_total_size": -1},
            )
            for index, options in enumerate(invalid_options):
                with self.subTest(options=options):
                    with self.assertRaises(ValueError):
                        extract_zip(archive, root / f"out-{index}", **options)

    def test_compression_ratio_rejects_boolean_and_non_numeric_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = self._archive(root)
            for ratio in (True, False, "200"):
                with self.subTest(ratio=ratio):
                    with self.assertRaises(ValueError):
                        extract_zip(archive, root / f"out-{ratio}", max_compression_ratio=ratio)


if __name__ == "__main__":
    unittest.main()
