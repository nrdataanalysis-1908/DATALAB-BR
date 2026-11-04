import json
import tempfile
import unittest
from pathlib import Path

from brasil_eleitoral.validation.contracts import (
    DataContract, FieldContract, load_contract, validate_csv, validate_records,
)


class ContractValidationTests(unittest.TestCase):
    def setUp(self):
        self.contract = DataContract(
            name="election_results", version=1,
            fields=(
                FieldContract("year", "integer"),
                FieldContract("candidate_id", "string"),
                FieldContract("votes", "integer"),
                FieldContract("status", "string", allowed_values=("ELECTED", "NOT_ELECTED")),
            ),
            primary_key=("year", "candidate_id"), minimum_rows=1,
        )

    def test_valid_records(self):
        report = validate_records([
            {"year": 2022, "candidate_id": "123", "votes": 100, "status": "ELECTED"}
        ], self.contract)
        self.assertTrue(report.valid)

    def test_detects_type_domain_and_duplicate_key(self):
        row = {"year": "2022", "candidate_id": "123", "votes": 1, "status": "UNKNOWN"}
        report = validate_records([row, row], self.contract)
        codes = {error["code"] for error in report.errors}
        self.assertIn("invalid_type", codes)
        self.assertIn("value_out_of_domain", codes)
        self.assertIn("duplicate_primary_key", codes)

    def test_detects_missing_and_null_fields(self):
        contract = DataContract(
            name="election_results", version=1, fields=self.contract.fields,
            primary_key=self.contract.primary_key, minimum_rows=2,
        )
        report = validate_records([{"year": 2022, "candidate_id": None}], contract)
        codes = {error["code"] for error in report.errors}
        self.assertIn("missing_field", codes)
        self.assertIn("null_not_allowed", codes)
        self.assertIn("below_minimum_rows", codes)

    def test_csv_validation_streams_and_parses_types(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "results.csv"
            path.write_text("year,candidate_id,votes,status\n2022,123,100,ELECTED\n", encoding="utf-8")
            self.assertTrue(validate_csv(path, self.contract).valid)

    def test_loads_json_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "contract.json"
            path.write_text(json.dumps({
                "name": "tiny", "version": 1,
                "fields": [{"name": "id", "type": "string"}], "primary_key": ["id"]
            }), encoding="utf-8")
            self.assertEqual(load_contract(path).name, "tiny")


    def test_csv_rejects_unexpected_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "results.csv"
            path.write_text(
                "year,candidate_id,votes,status,unreviewed\n2022,123,100,ELECTED,x\n",
                encoding="utf-8",
            )
            report = validate_csv(path, self.contract)
            self.assertFalse(report.valid)
            self.assertIn("unexpected_column", {error["code"] for error in report.errors})

    def test_csv_rejects_duplicate_headers_after_csv_parsing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "results.csv"
            path.write_text(
                "year,candidate_id,votes,status,status\n2022,123,100,ELECTED,NOT_ELECTED\n",
                encoding="utf-8",
            )
            report = validate_csv(path, self.contract)
            self.assertFalse(report.valid)
            self.assertIn("duplicate_column", {error["code"] for error in report.errors})


if __name__ == "__main__":
    unittest.main()
