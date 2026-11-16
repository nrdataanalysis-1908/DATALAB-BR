import tempfile
import unittest
from pathlib import Path

from brasil_eleitoral.transformation.medallion import MedallionError, silver_normalize_csv


class SilverCsvOptionTests(unittest.TestCase):
    def test_rejects_invalid_delimiters_before_creating_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "raw.csv"
            source.write_text("state,votes\nMG,10\n", encoding="utf-8")
            for delimiter in ("", "::", "\r", "\n", "\x00", None):
                with self.subTest(delimiter=delimiter):
                    destination = root / "silver.csv"
                    with self.assertRaisesRegex(MedallionError, "delimiter"):
                        silver_normalize_csv(source, destination, delimiter=delimiter)
                    self.assertFalse(destination.exists())

    def test_rejects_empty_encoding_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "raw.csv"
            source.write_text("state,votes\nMG,10\n", encoding="utf-8")
            with self.assertRaisesRegex(MedallionError, "encoding"):
                silver_normalize_csv(source, root / "silver.csv", encoding=" ")


if __name__ == "__main__":
    unittest.main()
