"""Declarative data contracts and deterministic quality checks (stdlib only)."""
from __future__ import annotations

import csv
import json
from collections import Counter
import math
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


def _is_finite_number(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


_TYPE_CHECKS = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": _is_finite_number,
    "boolean": lambda v: isinstance(v, bool),
}


def validate_records(records: Iterable[dict[str, Any]], contract: DataContract) -> ValidationReport:
    """Validate required fields, primitive types, domains, row counts and key uniqueness."""
    if (
        not isinstance(contract.version, int) or isinstance(contract.version, bool)
        or contract.version < 1
        or not isinstance(contract.minimum_rows, int)
        or isinstance(contract.minimum_rows, bool)
        or contract.minimum_rows < 0
    ):
        raise ValueError("Contract version must be positive and minimum_rows non-negative")
    if contract.maximum_rows is not None:
        if (
            not isinstance(contract.maximum_rows, int)
            or isinstance(contract.maximum_rows, bool)
            or contract.maximum_rows < 0
        ):
            raise ValueError("maximum_rows must be a non-negative integer or None")
        if contract.maximum_rows < contract.minimum_rows:
            raise ValueError("maximum_rows cannot be lower than minimum_rows")
    names = [item.name for item in contract.fields]
    if any(not isinstance(name, str) or not name.strip() for name in names):
        raise ValueError("Contract field names must be non-empty strings")
    if len(names) != len(set(names)):
        raise ValueError("Contract contains duplicate field names")
    if any(not isinstance(key, str) or not key.strip() for key in contract.primary_key):
        raise ValueError("Primary key fields must be non-empty strings")
    if len(contract.primary_key) != len(set(contract.primary_key)):
        raise ValueError("Primary key fields must be unique")
    unknown_keys = set(contract.primary_key) - set(names)
    if unknown_keys:
        raise ValueError(f"Primary key references unknown fields: {sorted(unknown_keys)}")
    nullable_keys = [
        item.name for item in contract.fields
        if item.name in contract.primary_key and item.nullable
    ]
    if nullable_keys:
        raise ValueError(
            f"Primary key fields cannot be nullable: {', '.join(nullable_keys)}"
        )
    for item in contract.fields:
        if item.dtype not in _TYPE_CHECKS:
            raise ValueError(f"Unsupported dtype {item.dtype!r} for field {item.name!r}")
        if not isinstance(item.allowed_values, (tuple, list)):
            raise ValueError(f"allowed_values for field {item.name!r} must be a sequence")
        if any(not _TYPE_CHECKS[item.dtype](value) for value in item.allowed_values):
            raise ValueError(
                f"allowed_values for field {item.name!r} must match dtype {item.dtype!r}"
            )

    report = ValidationReport(contract=contract.name, rows_checked=0)
    seen_keys: set[tuple[Any, ...]] = set()
    for row_number, record in enumerate(records, start=1):
        report.rows_checked += 1
        if not isinstance(record, dict):
            report.errors.append({"row": row_number, "field": None, "code": "invalid_record",
                                  "message": "Record must be an object"})
            continue
        for field_name in record:
            if field_name not in names:
                report.errors.append({
                    "row": row_number, "field": field_name, "code": "unexpected_field"
                })
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
        if contract.primary_key and all(
            key in record and record[key] is not None
            for key in contract.primary_key
        ):
            key = tuple(record[name] for name in contract.primary_key)
            try:
                hash(key)
            except TypeError:
                # Invalid unhashable values are already reported by the
                # field-type checks above; they cannot participate in key
                # uniqueness tracking.
                continue
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
    if (
        not isinstance(delimiter, str)
        or len(delimiter) != 1
        or delimiter in {"\r", "\n", "\x00"}
    ):
        raise ValueError("delimiter must be a single non-newline character")

    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    expected = [item.name for item in contract.fields]
    with path.open("r", encoding=encoding, newline="") as stream:
        reader = csv.DictReader(stream, delimiter=delimiter)
        actual = reader.fieldnames or []
        missing = sorted(set(expected) - set(actual))
        unexpected = sorted(set(actual) - set(expected))
        duplicates = sorted(name for name, count in Counter(actual).items() if count > 1)
        header_errors = (
            [{"row": 0, "field": name, "code": "missing_column"} for name in missing]
            + [{"row": 0, "field": name, "code": "unexpected_column"} for name in unexpected]
            + [{"row": 0, "field": name, "code": "duplicate_column"} for name in duplicates]
        )
        if header_errors:
            return ValidationReport(contract.name, 0, header_errors)
        extra_value_errors: list[dict[str, Any]] = []

        def iter_records():
            for row_number, row in enumerate(reader, start=2):
                if None in row:
                    extra_value_errors.append({
                        "row": row_number, "field": None, "code": "extra_values",
                        "count": len(row[None]),
                    })
                missing_values = [name for name in actual if row.get(name) is None]
                if missing_values:
                    extra_value_errors.append({
                        "row": row_number, "field": None, "code": "missing_values",
                        "columns": missing_values,
                    })
                yield {
                    item.name: _parse_csv_value(row.get(item.name), item.dtype)
                    for item in contract.fields
                }

        report = validate_records(iter_records(), contract)
        report.errors.extend(extra_value_errors)
        return report


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



def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Build a JSON object while rejecting duplicate keys at every nesting level."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON object key: {key!r}")
        result[key] = value
    return result


def load_contract(path: Path) -> DataContract:
    """Load a JSON contract definition without coercing malformed schema values."""
    payload = json.loads(
        Path(path).read_text(encoding="utf-8"), object_pairs_hook=_unique_json_object
    )
    if not isinstance(payload, dict):
        raise ValueError("Contract document must be a JSON object")

    name = payload.get("name")
    version = payload.get("version")
    fields_payload = payload.get("fields")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Contract name must be a non-empty string")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise ValueError("Contract version must be a positive integer")
    if not isinstance(fields_payload, list) or not fields_payload:
        raise ValueError("Contract fields must be a non-empty array")

    fields = []
    for index, item in enumerate(fields_payload):
        if not isinstance(item, dict):
            raise ValueError(f"Contract field at index {index} must be an object")
        field_name = item.get("name")
        dtype = item.get("type")
        nullable = item.get("nullable", False)
        allowed_values = item.get("allowed_values", [])
        if not isinstance(field_name, str) or not field_name.strip():
            raise ValueError(f"Contract field at index {index} requires a non-empty name")
        if not isinstance(dtype, str):
            raise ValueError(f"Contract field {field_name!r} requires a string type")
        if dtype not in _TYPE_CHECKS:
            raise ValueError(f"Unsupported dtype {dtype!r} for field {field_name!r}")
        if not isinstance(nullable, bool):
            raise ValueError(f"Contract field {field_name!r} nullable must be boolean")
        if not isinstance(allowed_values, list):
            raise ValueError(f"Contract field {field_name!r} allowed_values must be an array")
        if any(not _TYPE_CHECKS[dtype](value) for value in allowed_values):
            raise ValueError(
                f"Contract field {field_name!r} allowed_values must match dtype {dtype!r}"
            )
        fields.append(FieldContract(
            name=field_name, dtype=dtype, nullable=nullable,
            allowed_values=tuple(allowed_values),
        ))

    field_names = [item.name for item in fields]
    if len(field_names) != len(set(field_names)):
        raise ValueError("Contract contains duplicate field names")

    primary_key = payload.get("primary_key", [])
    minimum_rows = payload.get("minimum_rows", 0)
    maximum_rows = payload.get("maximum_rows")
    if not isinstance(primary_key, list) or any(
        not isinstance(key, str) or not key.strip() for key in primary_key
    ):
        raise ValueError("Contract primary_key must be an array of non-empty strings")
    if len(primary_key) != len(set(primary_key)):
        raise ValueError("Contract primary_key fields must be unique")
    unknown_keys = set(primary_key) - set(field_names)
    if unknown_keys:
        raise ValueError(f"Primary key references unknown fields: {sorted(unknown_keys)}")
    nullable_keys = [
        item.name for item in fields if item.name in primary_key and item.nullable
    ]
    if nullable_keys:
        raise ValueError(
            f"Primary key fields cannot be nullable: {', '.join(nullable_keys)}"
        )
    if isinstance(minimum_rows, bool) or not isinstance(minimum_rows, int) or minimum_rows < 0:
        raise ValueError("Contract minimum_rows must be a non-negative integer")
    if maximum_rows is not None and (
        isinstance(maximum_rows, bool) or not isinstance(maximum_rows, int) or maximum_rows < 0
    ):
        raise ValueError("Contract maximum_rows must be a non-negative integer or null")
    if maximum_rows is not None and maximum_rows < minimum_rows:
        raise ValueError("Contract maximum_rows cannot be lower than minimum_rows")

    return DataContract(
        name=name, version=version, fields=tuple(fields),
        primary_key=tuple(primary_key), minimum_rows=minimum_rows,
        maximum_rows=maximum_rows,
    )
