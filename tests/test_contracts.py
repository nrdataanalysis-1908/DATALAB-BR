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


    def test_csv_reports_surplus_values_in_data_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "results.csv"
            path.write_text(
                "year,candidate_id,votes,status\n2022,123,100,ELECTED,unexpected\n",
                encoding="utf-8",
            )
            report = validate_csv(path, self.contract)
            self.assertFalse(report.valid)
            error = next(error for error in report.errors if error["code"] == "extra_values")
            self.assertEqual(error["row"], 2)
            self.assertEqual(error["count"], 1)


    def test_number_contract_rejects_nan_and_infinity(self):
        contract = DataContract(
            name="finite_metrics", version=1,
            fields=(FieldContract("metric", "number"),),
        )
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                report = validate_records([{"metric": value}], contract)
                self.assertFalse(report.valid)
                self.assertIn("invalid_type", {error["code"] for error in report.errors})


    def test_contract_rejects_inconsistent_row_bounds(self):
        for maximum in (-1, 0):
            with self.subTest(maximum=maximum):
                contract = DataContract(
                    name="bounded", version=1,
                    fields=(FieldContract("id", "string"),),
                    minimum_rows=1, maximum_rows=maximum,
                )
                with self.assertRaises(ValueError):
                    validate_records([], contract)

    def test_contract_rejects_non_integer_row_bounds(self):
        contract = DataContract(
            name="bounded", version=1,
            fields=(FieldContract("id", "string"),),
            minimum_rows=1, maximum_rows=1.5,
        )
        with self.assertRaises(ValueError):
            validate_records([], contract)


    def test_load_contract_rejects_coerced_versions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "contract.json"
            base = {"name": "strict", "fields": [{"name": "id", "type": "string"}]}
            for version in (True, 1.5, "1", 0):
                with self.subTest(version=version):
                    path.write_text(json.dumps({**base, "version": version}), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        load_contract(path)

    def test_load_contract_requires_boolean_nullable_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "contract.json"
            path.write_text(json.dumps({
                "name": "strict", "version": 1,
                "fields": [{"name": "id", "type": "string", "nullable": "false"}],
            }), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "nullable must be boolean"):
                load_contract(path)

if __name__ == "__main__":
    unittest.main()
