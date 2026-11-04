import tempfile
import unittest
import zipfile
from pathlib import Path

from brasil_eleitoral.ingestion.extractor import ExtractionError, extract_zip


class SafeZipExtractionTests(unittest.TestCase):
    def _archive(self, root, entries):
        path = root / "sample.zip"
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, content in entries:
                archive.writestr(name, content)
        return path

    def test_extracts_valid_archive_atomically(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = self._archive(root, [("nested/results.csv", "year,votes\n2022,10\n")])
            result = extract_zip(archive, root / "out")
            self.assertEqual(result["file_count"], 1)
            self.assertEqual((root / "out/nested/results.csv").read_text(), "year,votes\n2022,10\n")
            self.assertEqual(result["status"], "verified")

    def test_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = self._archive(root, [("../escape.txt", "bad")])
            with self.assertRaises(ExtractionError):
                extract_zip(archive, root / "out")
            self.assertFalse((root / "escape.txt").exists())
            self.assertFalse((root / "out").exists())

    def test_enforces_entry_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = self._archive(root, [("a.txt", "a"), ("b.txt", "b")])
            with self.assertRaises(ExtractionError):
                extract_zip(archive, root / "out", max_entries=1)

    def test_refuses_existing_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = self._archive(root, [("a.txt", "a")])
            (root / "out").mkdir()
            with self.assertRaises(FileExistsError):
                extract_zip(archive, root / "out")


    def test_rejects_non_finite_compression_ratio_limits(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = self._archive(root, [("a.txt", "a")])
            for ratio in (float("nan"), float("inf"), float("-inf"), 0):
                with self.subTest(ratio=ratio):
                    with self.assertRaises(ValueError):
                        extract_zip(archive, root / f"out-{str(ratio)}",
                                    max_compression_ratio=ratio)


if __name__ == "__main__":
    unittest.main()
