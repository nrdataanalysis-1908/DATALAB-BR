import csv
import tempfile
import unittest
from pathlib import Path

from brasil_eleitoral.transformation.medallion import (
    MedallionError, bronze_ingest, gold_aggregate_results, silver_normalize_csv,
)


class MedallionTests(unittest.TestCase):
    def test_bronze_rejects_dot_segment_identifiers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "raw.csv"
            source.write_text("a,b\\n1,2\\n", encoding="utf-8")
            invalid_pairs = (
                ("..", "results"),
                ("tse", ".."),
                (".", "results"),
                ("tse", "."),
            )
            for source_id, dataset in invalid_pairs:
                with self.subTest(source_id=source_id, dataset=dataset):
                    with self.assertRaises(MedallionError):
                        bronze_ingest(
                            source, root / "lake",
                            source_id=source_id, dataset=dataset,
                        )

    def test_bronze_is_content_addressed_and_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "raw.csv"
            source.write_text("a,b\n1,2\n", encoding="utf-8")
            first = bronze_ingest(source, root / "lake", source_id="tse", dataset="results",
                                  execution_id="run-1")
            second = bronze_ingest(source, root / "lake", source_id="tse", dataset="results",
                                   execution_id="run-2")
            self.assertFalse(first["already_present"])
            self.assertTrue(second["already_present"])
            self.assertEqual(first["sha256"], second["sha256"])
            self.assertEqual(Path(first["path"]).read_bytes(), source.read_bytes())
            self.assertTrue(Path(first["metadata_path"]).is_file())

    def test_silver_rejects_rows_with_missing_trailing_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, output = root / "raw.csv", root / "silver.csv"
            source.write_text("state,votes\\nMG\\n", encoding="utf-8")
            with self.assertRaisesRegex(MedallionError, "fewer columns"):
                silver_normalize_csv(source, output)
            self.assertFalse(output.exists())

    def test_silver_normalizes_headers_and_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, output = root / "raw.csv", root / "silver.csv"
            source.write_text(" Candidate Name , Votes \n Alice , 12 \n", encoding="utf-8")
            result = silver_normalize_csv(source, output)
            self.assertEqual(result["columns"], ["candidate_name", "votes"])
            with output.open(encoding="utf-8", newline="") as stream:
                self.assertEqual(next(csv.DictReader(stream))["candidate_name"], "Alice")

    def test_silver_rejects_duplicate_normalized_headers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "raw.csv"
            source.write_text("Candidate Name,candidate-name\nA,B\n", encoding="utf-8")
            with self.assertRaises(MedallionError):
                silver_normalize_csv(source, root / "silver.csv")

    def test_silver_and_gold_reject_in_place_transformations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            silver_source = root / "silver-source.csv"
            silver_source.write_text("state,votes\\nMG,10\\n", encoding="utf-8")
            with self.assertRaisesRegex(MedallionError, "different files"):
                silver_normalize_csv(silver_source, silver_source)

            gold_source = root / "gold-source.csv"
            gold_source.write_text("state,votes\\nMG,10\\n", encoding="utf-8")
            with self.assertRaisesRegex(MedallionError, "different files"):
                gold_aggregate_results(
                    gold_source, gold_source, dimensions=("state",)
                )

    def test_gold_aggregates_with_explicit_grain(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, output = root / "silver.csv", root / "gold.csv"
            source.write_text("state,office,votes\nMG,Governor,10\nMG,Governor,15\nSP,Governor,7\n",
                              encoding="utf-8")
            result = gold_aggregate_results(source, output, dimensions=("state", "office"))
            self.assertEqual(result["groups"], 2)
            with output.open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(rows[0]["total_votes"], "25")
            self.assertEqual(list(rows[0]), ["state", "office", "total_votes"])

    def test_gold_rejects_null_dimensions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "silver.csv"
            source.write_text("state,votes\n,10\n", encoding="utf-8")
            with self.assertRaises(MedallionError):
                gold_aggregate_results(source, root / "gold.csv", dimensions=("state",))


if __name__ == "__main__":
    unittest.main()
