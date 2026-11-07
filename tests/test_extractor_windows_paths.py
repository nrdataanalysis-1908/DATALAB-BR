import tempfile
import unittest
import zipfile
from pathlib import Path

from brasil_eleitoral.ingestion.extractor import ExtractionError, extract_zip


class WindowsPortableZipPathTests(unittest.TestCase):
    def _archive(self, root, members):
        path = root / "portable.zip"
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            for name in members:
                archive.writestr(name, "payload")
        return path

    def _assert_rejected(self, members):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = self._archive(root, members)
            destination = root / "out"
            with self.assertRaises(ExtractionError):
                extract_zip(archive, destination)
            self.assertFalse(destination.exists())

    def test_rejects_alternate_data_streams_in_any_path_component(self):
        self._assert_rejected(["folder:stream.txt"])
        self._assert_rejected(["nested/file.csv:payload"])

    def test_rejects_reserved_windows_device_names_even_with_extensions(self):
        for name in ("CON", "CON.csv", "nested/NUL.txt", "COM1.log", "LPT9"):
            with self.subTest(name=name):
                self._assert_rejected([name])

    def test_rejects_components_ending_in_dot_or_space(self):
        self._assert_rejected(["report.csv."])
        self._assert_rejected(["folder /report.csv"])
        self._assert_rejected(["nested/report.csv "])

    def test_rejects_case_insensitive_path_collisions(self):
        self._assert_rejected(["Data.csv", "data.csv"])

    def test_rejects_windows_component_names_over_255_utf16_units(self):
        self._assert_rejected(["a" * 256 + ".csv"])


if __name__ == "__main__":
    unittest.main()
