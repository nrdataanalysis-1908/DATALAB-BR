import tempfile
import unittest
import zipfile
from pathlib import Path

from brasil_eleitoral.ingestion.extractor import ExtractionError, extract_zip


class UnicodePathNormalizationTests(unittest.TestCase):
    def test_rejects_nfc_and_nfd_aliases_before_publishing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive_path = root / "unicode-aliases.zip"
            with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("caf\u00e9.csv", "first")
                archive.writestr("cafe\u0301.csv", "second")
            destination = root / "out"

            with self.assertRaisesRegex(ExtractionError, "Duplicate or case-insensitive"):
                extract_zip(archive_path, destination)

            self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()