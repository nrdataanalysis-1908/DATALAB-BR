import tempfile
import unittest
import zipfile
from pathlib import Path

from brasil_eleitoral.ingestion.extractor import ExtractionError, extract_zip


class WindowsInvalidPathCharacterTests(unittest.TestCase):
    def _assert_rejected(self, member):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive_path = root / "invalid-name.zip"
            with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(member, "payload")
            destination = root / "out"
            with self.assertRaises(ExtractionError):
                extract_zip(archive_path, destination)
            self.assertFalse(destination.exists())

    def test_rejects_windows_forbidden_filename_characters(self):
        for character in '<>"|?*':
            with self.subTest(character=character):
                self._assert_rejected(f"report{character}.csv")

    def test_rejects_control_characters_in_path_components(self):
        for character in ("\x01", "\x1f", "\x7f"):
            with self.subTest(codepoint=ord(character)):
                self._assert_rejected(f"nested/report{character}.csv")


if __name__ == "__main__":
    unittest.main()