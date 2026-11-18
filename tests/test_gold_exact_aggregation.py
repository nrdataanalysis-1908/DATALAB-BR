import tempfile
import unittest
from pathlib import Path

from brasil_eleitoral.transformation.medallion import gold_aggregate_results


class GoldExactAggregationTests(unittest.TestCase):
    def test_large_vote_totals_are_summed_without_decimal_rounding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "silver.csv"
            destination = root / "gold.csv"
            source.write_text(
                "state,votes\nMG,12345678901234567890123456789\nMG,2\n",
                encoding="utf-8",
            )
            gold_aggregate_results(source, destination, dimensions=("state",))
            self.assertEqual(
                destination.read_text(encoding="utf-8").splitlines()[1],
                "MG,12345678901234567890123456791",
            )


if __name__ == "__main__":
    unittest.main()
