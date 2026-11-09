"""Reproducible, stdlib-only Bronze/Silver/Gold transformations."""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
from typing import Iterable


class MedallionError(ValueError):
    """Raised when a medallion operation cannot be completed safely."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def bronze_ingest(source: Path, root: Path, *, source_id: str, dataset: str,
                  execution_id: str | None = None) -> dict:
    """Copy an immutable source file into Bronze, keyed by its content hash."""
    source, root = Path(source), Path(root)
    if not source.is_file():
        raise FileNotFoundError(source)
    identifier_pattern = r"[A-Za-z0-9][A-Za-z0-9_.-]{0,199}"
    for value, label in ((source_id, "source_id"), (dataset, "dataset")):
        if not isinstance(value, str) or not re.fullmatch(identifier_pattern, value):
            raise MedallionError(f"Invalid {label}")
    digest = sha256_file(source)
    execution_id = execution_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if not isinstance(execution_id, str) or not re.fullmatch(identifier_pattern, execution_id):
        raise MedallionError("Invalid execution_id")
    destination_dir = root / "bronze" / source_id / dataset / digest[:2]
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"{digest}{source.suffix.lower()}"
    metadata_path = destination.with_suffix(destination.suffix + ".metadata.json")
    if destination.is_symlink():
        raise MedallionError("Existing Bronze object must not be a symbolic link")
    if destination.exists() and not destination.is_file():
        raise MedallionError("Existing Bronze object must be a regular file")
    if metadata_path.is_symlink():
        raise MedallionError("Existing Bronze metadata must not be a symbolic link")
    already_present = destination.exists()
    if already_present and sha256_file(destination) != digest:
        raise MedallionError("Existing Bronze object does not match its content hash")
    if not already_present:
        fd, temporary = tempfile.mkstemp(prefix=".bronze.", dir=destination_dir)
        os.close(fd)
        try:
            shutil.copyfile(source, temporary)
            if sha256_file(Path(temporary)) != digest:
                raise MedallionError("Source changed while being copied")
            os.replace(temporary, destination)
        except Exception:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise
    metadata = {
        "layer": "bronze", "source_id": source_id, "dataset": dataset,
        "source_filename": source.name, "stored_filename": destination.name,
        "sha256": digest, "size_bytes": destination.stat().st_size,
        "execution_id": execution_id, "ingested_at": datetime.now(timezone.utc).isoformat(),
        "immutable": True,
    }
    if metadata_path.exists():
        try:
            existing_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise MedallionError("Existing Bronze metadata is unreadable") from exc
        expected_fields = {
            "layer": "bronze", "source_id": source_id, "dataset": dataset,
            "stored_filename": destination.name, "sha256": digest,
            "size_bytes": destination.stat().st_size, "immutable": True,
        }
        if not isinstance(existing_metadata, dict) or any(
            existing_metadata.get(key) != value for key, value in expected_fields.items()
        ):
            raise MedallionError("Existing Bronze metadata does not match its content object")
    else:
        _atomic_json(metadata_path, metadata)
    return {"path": str(destination), "metadata_path": str(metadata_path),
            "sha256": digest, "size_bytes": destination.stat().st_size,
            "already_present": already_present}


def _normalize_header(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value, flags=re.ASCII).strip("_")
    if not value:
        raise MedallionError("CSV contains an empty/invalid column name")
    return value


def silver_normalize_csv(source: Path, destination: Path, *,
                         encoding: str = "utf-8-sig", delimiter: str = ",") -> dict:
    """Normalize CSV headers and whitespace, retaining values as strings."""
    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve():
        raise MedallionError("Source and destination must be different files")
    if not source.is_file():
        raise FileNotFoundError(source)
    if (
        not isinstance(delimiter, str) or len(delimiter) != 1
        or delimiter in {"\\r", "\\n", "\\x00"}
    ):
        raise MedallionError("delimiter must be a single non-newline character")
    if not isinstance(encoding, str) or not encoding.strip():
        raise MedallionError("encoding must be a non-empty codec name")
    source_digest = sha256_file(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".silver.", suffix=".csv", dir=destination.parent)
    os.close(fd)
    rows = 0
    try:
        with source.open("r", encoding=encoding, newline="") as incoming, open(
            temporary, "w", encoding="utf-8", newline=""
        ) as outgoing:
            reader = csv.DictReader(incoming, delimiter=delimiter)
            if not reader.fieldnames:
                raise MedallionError("CSV has no header")
            headers = [_normalize_header(name or "") for name in reader.fieldnames]
            if len(headers) != len(set(headers)):
                raise MedallionError("Header normalization produced duplicate columns")
            writer = csv.DictWriter(outgoing, fieldnames=headers, extrasaction="raise")
            writer.writeheader()
            for row in reader:
                if None in row:
                    raise MedallionError(f"Row {rows + 2} has more columns than the header")
                missing = [name for name in reader.fieldnames if row.get(name) is None]
                if missing:
                    raise MedallionError(
                        f"Row {rows + 2} has fewer columns than the header: {missing}"
                    )
                writer.writerow({headers[index]: (row.get(reader.fieldnames[index]) or "").strip()
                                 for index in range(len(headers))})
                rows += 1
            outgoing.flush()
            os.fsync(outgoing.fileno())
        if sha256_file(source) != source_digest:
            raise MedallionError("Source changed during Silver transformation")
        os.replace(temporary, destination)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise
    metadata = {"layer": "silver", "rows": rows, "columns": headers,
                "source_sha256": source_digest, "output_sha256": sha256_file(destination)}
    _atomic_json(destination.with_suffix(destination.suffix + ".metadata.json"), metadata)
    return {"path": str(destination), **metadata}


def gold_aggregate_results(source: Path, destination: Path, *,
                           dimensions: Iterable[str], metric: str = "votes",
                           encoding: str = "utf-8-sig") -> dict:
    """Aggregate normalized result rows by explicit dimensions and sum a metric."""
    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve():
        raise MedallionError("Source and destination must be different files")
    if isinstance(dimensions, (str, bytes)):
        raise MedallionError("Dimensions must be an iterable of column names, not a string")
    try:
        dimensions = tuple(dimensions)
    except TypeError as exc:
        raise MedallionError("Dimensions must be an iterable of column names") from exc
    if (
        not dimensions
        or any(not isinstance(name, str) or not name or name != name.strip() for name in dimensions)
        or len(set(dimensions)) != len(dimensions)
    ):
        raise MedallionError("Provide unique, non-empty aggregation dimension names")
    if not isinstance(metric, str) or not metric or metric != metric.strip():
        raise MedallionError("Metric must be a non-empty column name")
    if metric in dimensions:
        raise MedallionError("Metric cannot also be an aggregation dimension")
    source_digest = sha256_file(source)
    totals: dict[tuple[str, ...], Decimal] = defaultdict(Decimal)
    with source.open("r", encoding=encoding, newline="") as stream:
        reader = csv.DictReader(stream)
        fieldnames = reader.fieldnames or []
        if not fieldnames or any(not name for name in fieldnames):
            raise MedallionError("Source CSV has a missing or empty header")
        duplicates = sorted({name for name in fieldnames if fieldnames.count(name) > 1})
        if duplicates:
            raise MedallionError(f"Source CSV contains duplicate headers: {duplicates}")
        if any(name not in fieldnames for name in (*dimensions, metric)):
            raise MedallionError("Source CSV is missing an aggregation column")
        for row_number, row in enumerate(reader, start=2):
            if None in row:
                raise MedallionError(f"Row {row_number} has more columns than the header")
            key = tuple((row.get(name) or "").strip() for name in dimensions)
            if any(not value for value in key):
                raise MedallionError(f"Null aggregation dimension at row {row_number}")
            try:
                value = Decimal((row.get(metric) or "").strip())
            except InvalidOperation as exc:
                raise MedallionError(f"Invalid {metric} at row {row_number}") from exc
            if not value.is_finite() or value < 0:
                raise MedallionError(f"Invalid non-negative metric at row {row_number}")
            current = totals[key]
            required_precision = (
                max(current.adjusted(), value.adjusted())
                - min(current.as_tuple().exponent, value.as_tuple().exponent)
                + 2
            )
            if required_precision > 10000:
                raise MedallionError("Metric precision exceeds the exact aggregation limit")
            with localcontext() as context:
                context.prec = max(context.prec, required_precision)
                totals[key] = current + value
    if sha256_file(source) != source_digest:
        raise MedallionError("Source changed during Gold aggregation")
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".gold.", suffix=".csv", dir=destination.parent)
    os.close(fd)
    try:
        with open(temporary, "w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow([*dimensions, f"total_{metric}"])
            for key in sorted(totals):
                writer.writerow([*key, format(totals[key], "f")])
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise
    metadata = {"layer": "gold", "dimensions": list(dimensions), "metric": metric,
                "groups": len(totals), "source_sha256": source_digest,
                "output_sha256": sha256_file(destination)}
    _atomic_json(destination.with_suffix(destination.suffix + ".metadata.json"), metadata)
    return {"path": str(destination), **metadata}
