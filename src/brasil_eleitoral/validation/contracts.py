"""Declarative data contracts and deterministic quality checks (stdlib only)."""
from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class FieldContract:
    name: str
    dtype: str
    nullable: bool = False
    allowed_values: tuple[Any, ...] = ()


@dataclass(frozen=True)
class DataContract:
    name: str
    version: int
    fields: tuple[FieldContract, ...]
    primary_key: tuple[str, ...] = ()
    minimum_rows: int = 0
    maximum_rows: int | None = None


@dataclass
class ValidationReport:
    contract: str
    rows_checked: int
    errors: list[dict[str, Any]] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["valid"] = self.valid
        return result


_TYPE_CHECKS = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
}


def validate_records(records: Iterable[dict[str, Any]], contract: DataContract) -> ValidationReport:
    """Validate required fields, primitive types, domains, row counts and key uniqueness."""
    if contract.version < 1 or contract.minimum_rows < 0:
        raise ValueError("Contract version and minimum_rows must be positive/non-negative")
    names = [item.name for item in contract.fields]
    if len(names) != len(set(names)):
        raise ValueError("Contract contains duplicate field names")
    unknown_keys = set(contract.primary_key) - set(names)
    if unknown_keys:
        raise ValueError(f"Primary key references unknown fields: {sorted(unknown_keys)}")
    for item in contract.fields:
        if item.dtype not in _TYPE_CHECKS:
            raise ValueError(f"Unsupported dtype {item.dtype!r} for field {item.name!r}")

    report = ValidationReport(contract=contract.name, rows_checked=0)
    seen_keys: set[tuple[Any, ...]] = set()
    for row_number, record in enumerate(records, start=1):
        report.rows_checked += 1
        if not isinstance(record, dict):
            report.errors.append({"row": row_number, "field": None, "code": "invalid_record",
                                  "message": "Record must be an object"})
            continue
        for item in contract.fields:
            value = record.get(item.name)
            if item.name not in record:
                report.errors.append({"row": row_number, "field": item.name, "code": "missing_field"})
                continue
            if value is None:
                if not item.nullable:
                    report.errors.append({"row": row_number, "field": item.name, "code": "null_not_allowed"})
                continue
            if not _TYPE_CHECKS[item.dtype](value):
                report.errors.append({"row": row_number, "field": item.name, "code": "invalid_type",
                                      "expected": item.dtype, "actual": type(value).__name__})
                continue
            if item.allowed_values and value not in item.allowed_values:
                report.errors.append({"row": row_number, "field": item.name, "code": "value_out_of_domain",
                                      "allowed_values": list(item.allowed_values), "actual": value})
        if contract.primary_key and all(record.get(key) is not None for key in contract.primary_key):
            key = tuple(record[key] for key in contract.primary_key)
            if key in seen_keys:
                report.errors.append({"row": row_number, "field": list(contract.primary_key),
                                      "code": "duplicate_primary_key", "value": list(key)})
            seen_keys.add(key)

    if report.rows_checked < contract.minimum_rows:
        report.errors.append({"row": None, "field": None, "code": "below_minimum_rows",
                              "minimum": contract.minimum_rows, "actual": report.rows_checked})
    if contract.maximum_rows is not None and report.rows_checked > contract.maximum_rows:
        report.errors.append({"row": None, "field": None, "code": "above_maximum_rows",
                              "maximum": contract.maximum_rows, "actual": report.rows_checked})
    return report


def validate_csv(path: Path, contract: DataContract, *, delimiter: str = ",",
                 encoding: str = "utf-8-sig") -> ValidationReport:
    """Stream a CSV file through a contract without loading it fully into memory."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    expected = [item.name for item in contract.fields]
    with path.open("r", encoding=encoding, newline="") as stream:
        reader = csv.DictReader(stream, delimiter=delimiter)
        actual = reader.fieldnames or []
        missing = sorted(set(expected) - set(actual))
        unexpected = sorted(set(actual) - set(expected))
        duplicates = sorted({name for name in actual if actual.count(name) > 1})
        header_errors = (
            [{"row": 0, "field": name, "code": "missing_column"} for name in missing]
            + [{"row": 0, "field": name, "code": "unexpected_column"} for name in unexpected]
            + [{"row": 0, "field": name, "code": "duplicate_column"} for name in duplicates]
        )
        if header_errors:
            return ValidationReport(contract.name, 0, header_errors)
        records = (
            {key: _parse_csv_value(value, next(f.dtype for f in contract.fields if f.name == key))
             for key, value in row.items() if key is not None}
            for row in reader
        )
        return validate_records(records, contract)


def _parse_csv_value(value: str | None, dtype: str) -> Any:
    if value is None or value == "":
        return None
    try:
        if dtype == "integer":
            return int(value)
        if dtype == "number":
            return float(value)
        if dtype == "boolean":
            normalized = value.strip().lower()
            if normalized in {"true", "1", "sim"}:
                return True
            if normalized in {"false", "0", "nao", "não"}:
                return False
            return value
        return value
    except ValueError:
        return value


def load_contract(path: Path) -> DataContract:
    """Load a JSON contract definition."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return DataContract(
        name=payload["name"], version=int(payload["version"]),
        fields=tuple(FieldContract(
            name=item["name"], dtype=item["type"], nullable=bool(item.get("nullable", False)),
            allowed_values=tuple(item.get("allowed_values", [])),
        ) for item in payload["fields"]),
        primary_key=tuple(payload.get("primary_key", [])),
        minimum_rows=int(payload.get("minimum_rows", 0)),
        maximum_rows=payload.get("maximum_rows"),
    )
