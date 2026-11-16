import tempfile
import unittest
from pathlib import Path

import brasil_eleitoral.transformation.medallion as medallion
from brasil_eleitoral.transformation.medallion import MedallionError, silver_normalize_csv


class SilverValidationOrderTests(unittest.TestCase):
    def test_invalid_delimiter_fails_before_source_hashing(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "raw.csv"
            source.write_text("state,votes\nMG,10\n", encoding="utf-8")
            original = medallion.sha256_file
            medallion.sha256_file = lambda path: (_ for _ in ()).throw(AssertionError("hash should not run"))
            try:
                with self.assertRaisesRegex(MedallionError, "delimiter"):
                    silver_normalize_csv(source, Path(tmp) / "silver.csv", delimiter="::")
            finally:
                medallion.sha256_file = original


if __name__ == "__main__":
    unittest.main()
