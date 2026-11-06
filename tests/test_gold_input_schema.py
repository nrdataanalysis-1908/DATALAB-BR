import tempfile
import unittest
from pathlib import Path

from brasil_eleitoral.transformation.medallion import MedallionError, gold_aggregate_results


class GoldInputSchemaTests(unittest.TestCase):
    def test_rejects_duplicate_input_headers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "silver.csv"
            source.write_text("state,state,votes\nMG,SP,10\n", encoding="utf-8")
            with self.assertRaisesRegex(MedallionError, "duplicate"):
                gold_aggregate_results(source, root / "gold.csv", dimensions=("state",))

    def test_rejects_empty_input_header_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "silver.csv"
            source.write_text("state,,votes\nMG,unknown,10\n", encoding="utf-8")
            with self.assertRaisesRegex(MedallionError, "header"):
                gold_aggregate_results(source, root / "gold.csv", dimensions=("state",))

    def test_rejects_rows_with_more_values_than_the_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "silver.csv"
            source.write_text("state,votes\nMG,10,unexpected\n", encoding="utf-8")
            with self.assertRaisesRegex(MedallionError, "Row 2"):
                gold_aggregate_results(source, root / "gold.csv", dimensions=("state",))


if __name__ == "__main__":
    unittest.main()
