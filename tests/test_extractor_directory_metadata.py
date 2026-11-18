import stat
import tempfile
import unittest
import zipfile
from pathlib import Path

from brasil_eleitoral.ingestion.extractor import ExtractionError, extract_zip


class ZipDirectoryMetadataTests(unittest.TestCase):
    def _archive(self, root, name, mode, payload):
        archive_path = root / "metadata.zip"
        info = zipfile.ZipInfo(name)
        info.create_system = 3
        info.external_attr = (mode | 0o755) << 16
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr(info, payload)
        return archive_path

    def test_rejects_directory_member_with_payload(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = self._archive(root, "folder/", stat.S_IFDIR, b"ignored payload")
            destination = root / "out"

            with self.assertRaisesRegex(ExtractionError, "directory.*data"):
                extract_zip(archive, destination)

            self.assertFalse(destination.exists())

    def test_rejects_file_path_marked_as_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = self._archive(root, "file.txt", stat.S_IFDIR, b"")
            destination = root / "out"

            with self.assertRaisesRegex(ExtractionError, "metadata does not match"):
                extract_zip(archive, destination)

            self.assertFalse(destination.exists())

    def test_rejects_directory_path_marked_as_regular_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = self._archive(root, "folder/", stat.S_IFREG, b"")
            destination = root / "out"

            with self.assertRaisesRegex(ExtractionError, "metadata does not match"):
                extract_zip(archive, destination)

            self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
