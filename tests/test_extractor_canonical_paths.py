import tempfile
import unittest
import zipfile
from pathlib import Path

from brasil_eleitoral.ingestion.extractor import ExtractionError, extract_zip


class CanonicalZipPathTests(unittest.TestCase):
    def _archive(self, root, member):
        path = root / "noncanonical.zip"
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(member, "payload")
        return path

    def test_rejects_dot_and_empty_path_segments(self):
        members = ("./root.txt", "nested/./file.txt", "nested//file.txt", "nested///file.txt")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for index, member in enumerate(members):
                with self.subTest(member=member):
                    archive = self._archive(root, member)
                    destination = root / f"out-{index}"
                    with self.assertRaises(ExtractionError):
                        extract_zip(archive, destination)
                    self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
