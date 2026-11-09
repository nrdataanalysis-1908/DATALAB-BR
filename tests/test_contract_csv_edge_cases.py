import json

import pytest

from brasil_eleitoral.validation.contracts import (
    DataContract,
    FieldContract,
    load_contract,
    validate_csv,
    validate_records,
)


@pytest.mark.parametrize("delimiter", ["\\r", "\\n", "\\x00"])
def test_validate_csv_rejects_actual_control_character_delimiters(tmp_path, delimiter):
    source = tmp_path / "results.csv"
    source.write_text("state,votes\\nMG,10\\n", encoding="utf-8")
    contract = DataContract(
        name="results",
        version=1,
        fields=(FieldContract("state", "string"), FieldContract("votes", "integer")),
    )

    with pytest.raises(ValueError, match="single non-newline character"):
        validate_csv(source, contract, delimiter=delimiter)


def test_validate_csv_rejects_short_rows_even_for_nullable_fields(tmp_path):
    source = tmp_path / "results.csv"
    source.write_text("state,votes\\nMG\\n", encoding="utf-8")
    contract = DataContract(
        name="results",
        version=1,
        fields=(
            FieldContract("state", "string"),
            FieldContract("votes", "integer", nullable=True),
        ),
    )

    report = validate_csv(source, contract)

    assert not report.valid
    assert any(error["code"] == "missing_values" for error in report.errors)


@pytest.mark.parametrize(
    ("dtype", "allowed_value"),
    [
        ("string", 1),
        ("integer", "1"),
        ("number", True),
        ("boolean", 1),
    ],
)
def test_load_contract_rejects_allowed_values_that_do_not_match_dtype(
    tmp_path, dtype, allowed_value
):
    source = tmp_path / "contract.json"
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

    with pytest.raises(ValueError, match="allowed_values.*match"):
        load_contract(source)


def test_validate_records_rejects_invalid_allowed_values_in_direct_contract():
    contract = DataContract(
        name="strict",
        version=1,
        fields=(FieldContract("votes", "integer", allowed_values=("10",)),),
    )

    with pytest.raises(ValueError, match="allowed_values.*match"):
        validate_records([], contract)
