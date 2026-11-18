import tempfile
import unittest
import zipfile
from pathlib import Path

from brasil_eleitoral.ingestion.extractor import ExtractionError, extract_zip


class ZipUnicodeFormatControlTests(unittest.TestCase):
    def test_rejects_bidi_and_zero_width_format_controls_in_member_names(self):
        member_names = (
            "report\u202eexe.txt",
            "zero\u200bwidth.csv",
        )
        for member_name in member_names:
            with self.subTest(member_name=repr(member_name)):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    archive_path = root / "format-controls.zip"
                    with zipfile.ZipFile(archive_path, "w") as archive:
                        archive.writestr(member_name, "untrusted")
                    destination = root / "out"

                    with self.assertRaisesRegex(
                        ExtractionError, "Windows-incompatible character"
                    ):
                        extract_zip(archive_path, destination)

                    self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
