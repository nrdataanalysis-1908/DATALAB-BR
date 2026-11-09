import json
import tempfile
import unittest
from pathlib import Path

from brasil_eleitoral.validation.contracts import (
    DataContract,
    FieldContract,
    load_contract,
    validate_csv,
    validate_records,
)


class ContractCsvEdgeCaseTests(unittest.TestCase):
    def test_validate_csv_rejects_actual_control_character_delimiters(self):
        contract = DataContract(
            name="results",
            version=1,
            fields=(FieldContract("state", "string"), FieldContract("votes", "integer")),
        )
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "results.csv"
            source.write_text("state,votes\\nMG,10\\n", encoding="utf-8")
            for delimiter in ("\\r", "\\n", "\\x00"):
                with self.subTest(delimiter=repr(delimiter)):
                    with self.assertRaisesRegex(
                        ValueError, "single non-newline character"
                    ):
                        validate_csv(source, contract, delimiter=delimiter)

    def test_validate_csv_rejects_short_rows_even_for_nullable_fields(self):
        contract = DataContract(
            name="results",
            version=1,
            fields=(
                FieldContract("state", "string"),
                FieldContract("votes", "integer", nullable=True),
            ),
        )
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "results.csv"
            source.write_text("state,votes\\nMG\\n", encoding="utf-8")

            report = validate_csv(source, contract)

        self.assertFalse(report.valid)
        self.assertIn(
            "missing_values", {error["code"] for error in report.errors}
        )

    def test_load_contract_rejects_allowed_values_that_do_not_match_dtype(self):
        invalid_domains = (
            ("string", 1),
            ("integer", "1"),
            ("number", True),
            ("boolean", 1),
        )
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "contract.json"
            for dtype, allowed_value in invalid_domains:
                with self.subTest(dtype=dtype, allowed_value=allowed_value):
                    source.write_text(
                        json.dumps(
                            {
                                "name": "strict",
                                "version": 1,
                                "fields": [
                                    {
                                        "name": "value",
                                        "type": dtype,
                                        "allowed_values": [allowed_value],
                                    }
                                ],
                            }
                        ),
                        encoding="utf-8",
                    )
                    with self.assertRaisesRegex(
                        ValueError, "allowed_values.*match"
                    ):
                        load_contract(source)

    def test_validate_records_rejects_invalid_allowed_values_in_direct_contract(self):
        contract = DataContract(
            name="strict",
            version=1,
            fields=(FieldContract("votes", "integer", allowed_values=("10",)),),
        )

        with self.assertRaisesRegex(ValueError, "allowed_values.*match"):
            validate_records([], contract)


if __name__ == "__main__":
    unittest.main()
