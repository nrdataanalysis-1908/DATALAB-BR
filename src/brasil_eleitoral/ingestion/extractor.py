"""Safe ZIP extraction for untrusted public datasets."""
from __future__ import annotations

import math
import os
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


class ExtractionError(RuntimeError):
    """Raised when an archive is unsafe, corrupt, or exceeds configured limits."""


def _validated_members(archive: zipfile.ZipFile, *, max_entries: int,
                       max_file_size: int, max_total_size: int,
                       max_compression_ratio: float) -> list[zipfile.ZipInfo]:
    members = archive.infolist()
    if len(members) > max_entries:
        raise ExtractionError(f"Archive has {len(members)} entries; limit is {max_entries}")

    seen: set[str] = set()
    total = 0
    for info in members:
        name = info.filename
        if not name or "\x00" in name or "\\" in name:
            raise ExtractionError(f"Unsafe ZIP member path: {name!r}")
        canonical_name = name[:-1] if name.endswith("/") else name
        raw_parts = canonical_name.split("/")
        if not canonical_name or any(part in {"", ".", ".."} for part in raw_parts):
            raise ExtractionError(f"Path traversal or non-canonical path: {name!r}")
        path = PurePosixPath(name)
        if path.is_absolute():
            raise ExtractionError(f"Path traversal or non-canonical path: {name!r}")
        if path.parts and ":" in path.parts[0]:
            raise ExtractionError(f"Drive-qualified path is not allowed: {name!r}")
        normalized = path.as_posix().rstrip("/")
        if normalized in seen:
            raise ExtractionError(f"Duplicate archive path: {name!r}")
        seen.add(normalized)

        mode = (info.external_attr >> 16) & 0xFFFF
        kind = stat.S_IFMT(mode)
        if kind not in {0, stat.S_IFREG, stat.S_IFDIR}:
            raise ExtractionError(f"Links and special files are not allowed: {name!r}")
        if info.flag_bits & 0x1:
            raise ExtractionError(f"Encrypted ZIP members are not supported: {name!r}")
        if info.file_size < 0 or info.file_size > max_file_size:
            raise ExtractionError(f"Member exceeds file-size limit: {name!r}")
        total += info.file_size
        if total > max_total_size:
            raise ExtractionError("Archive exceeds total uncompressed-size limit")
        if info.file_size and info.compress_size == 0:
            raise ExtractionError(f"Invalid compressed size: {name!r}")
        if info.compress_size and info.file_size / info.compress_size > max_compression_ratio:
            raise ExtractionError(f"Compression ratio exceeds limit: {name!r}")
    return members


def extract_zip(
    archive_path: Path,
    destination: Path,
    *,
    max_entries: int = 20_000,
    max_file_size: int = 2 * 1024**3,
    max_total_size: int = 10 * 1024**3,
    max_compression_ratio: float = 200.0,
) -> dict[str, object]:
    """Validate and extract an archive into a new directory using staging + rename."""
    archive_path, destination = Path(archive_path), Path(destination)
    integer_limits = (max_entries, max_file_size, max_total_size)
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 1
        for value in integer_limits
    ):
        raise ValueError("Entry and size limits must be positive integers")
    try:
        valid_compression_ratio = (
            not isinstance(max_compression_ratio, bool)
            and isinstance(max_compression_ratio, (int, float))
            and math.isfinite(max_compression_ratio)
            and max_compression_ratio > 0
        )
    except (OverflowError, TypeError):
        valid_compression_ratio = False
    if not valid_compression_ratio:
        raise ValueError("Compression ratio limit must be a finite positive number")
    if destination.exists():
        raise FileExistsError(f"Destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)

    staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}.staging-", dir=destination.parent))
    try:
        with zipfile.ZipFile(archive_path) as archive:
            members = _validated_members(
                archive, max_entries=max_entries, max_file_size=max_file_size,
                max_total_size=max_total_size, max_compression_ratio=max_compression_ratio,
            )
            bad_member = archive.testzip()
            if bad_member is not None:
                raise ExtractionError(f"CRC validation failed for member: {bad_member}")
            for info in members:
                target = staging.joinpath(*PurePosixPath(info.filename).parts)
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info, "r") as source, target.open("xb") as output:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
                    output.flush()
                    os.fsync(output.fileno())
        os.replace(staging, destination)
    except (zipfile.BadZipFile, OSError, RuntimeError) as exc:
        shutil.rmtree(staging, ignore_errors=True)
        if isinstance(exc, ExtractionError):
            raise
        raise ExtractionError(f"ZIP extraction failed: {exc}") from exc
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    files = [p for p in destination.rglob("*") if p.is_file()]
    return {
        "archive": str(archive_path), "destination": str(destination),
        "file_count": len(files), "total_size_bytes": sum(p.stat().st_size for p in files),
        "status": "verified",
    }
