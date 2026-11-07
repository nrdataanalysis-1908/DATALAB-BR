import tempfile
import unittest
import zipfile
from pathlib import Path

from brasil_eleitoral.ingestion.extractor import ExtractionError, extract_zip


class ZipPathConflictTests(unittest.TestCase):
    def _archive(self, root, entries):
        path = root / "conflicts.zip"
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, content in entries:
                archive.writestr(name, content)
        return path

    def test_rejects_file_used_as_parent_of_another_member(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = self._archive(root, [
                ("dataset.csv", "data"),
                ("dataset.csv/row.csv", "nested"),
            ])
            destination = root / "out"
            with self.assertRaises(ExtractionError):
                extract_zip(archive, destination)
            self.assertFalse(destination.exists())

    def test_rejects_nested_file_used_as_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = self._archive(root, [
                ("folder/file.csv", "data"),
                ("folder/file.csv/child.csv", "nested"),
            ])
            with self.assertRaises(ExtractionError):
                extract_zip(archive, root / "out")

    def test_accepts_explicit_directory_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = self._archive(root, [
                ("folder/", ""),
                ("folder/file.csv", "data"),
            ])
            result = extract_zip(archive, root / "out")
            self.assertEqual(result["file_count"], 1)
            self.assertEqual((root / "out/folder/file.csv").read_text(), "data")


if __name__ == "__main__":
    unittest.main()
