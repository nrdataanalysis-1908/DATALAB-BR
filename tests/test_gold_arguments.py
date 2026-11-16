import tempfile
import unittest
from pathlib import Path

from brasil_eleitoral.transformation.medallion import MedallionError, gold_aggregate_results


class GoldArgumentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root / "silver.csv"
        self.source.write_text("state,votes\nMG,10\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_rejects_string_instead_of_dimension_iterable(self):
        with self.assertRaisesRegex(MedallionError, "not a string"):
            gold_aggregate_results(self.source, self.root / "gold.csv", dimensions="state")

    def test_rejects_empty_or_whitespace_dimension_names(self):
        for dimensions in (("",), (" state",), (None,)):
            with self.subTest(dimensions=dimensions):
                with self.assertRaisesRegex(MedallionError, "dimension names"):
                    gold_aggregate_results(self.source, self.root / "gold.csv", dimensions=dimensions)

    def test_rejects_empty_metric_name(self):
        with self.assertRaisesRegex(MedallionError, "Metric must be"):
            gold_aggregate_results(self.source, self.root / "gold.csv", dimensions=("state",), metric=" ")


if __name__ == "__main__":
    unittest.main()
