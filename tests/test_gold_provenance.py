import tempfile
import unittest
from pathlib import Path

import brasil_eleitoral.transformation.medallion as medallion
from brasil_eleitoral.transformation.medallion import MedallionError, gold_aggregate_results


class GoldProvenanceTests(unittest.TestCase):
    def test_source_change_during_aggregation_preserves_previous_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "silver.csv"
            destination = root / "gold.csv"
            source.write_text("state,votes\nMG,10\n", encoding="utf-8")
            destination.write_text("previous-complete-output", encoding="utf-8")
            original_digest = medallion.sha256_file
            mutated = False

            def change_after_initial_hash(path):
                nonlocal mutated
                digest = original_digest(path)
                if Path(path) == source and not mutated:
                    mutated = True
                    source.write_text("state,votes\nSP,20\n", encoding="utf-8")
                return digest

            medallion.sha256_file = change_after_initial_hash
            try:
                with self.assertRaisesRegex(MedallionError, "Source changed"):
                    gold_aggregate_results(source, destination, dimensions=("state",))
            finally:
                medallion.sha256_file = original_digest

            self.assertEqual(destination.read_text(encoding="utf-8"), "previous-complete-output")
            self.assertEqual(list(root.glob(".gold.*.csv")), [])


if __name__ == "__main__":
    unittest.main()
