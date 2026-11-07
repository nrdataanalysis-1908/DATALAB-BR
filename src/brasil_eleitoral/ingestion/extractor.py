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


_WINDOWS_RESERVED_BASENAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
    "COM¹", "COM²", "COM³", "LPT¹", "LPT²", "LPT³",
}


def _validate_portable_component(component: str, member_name: str) -> None:
    """Reject names that alias devices or streams on Windows filesystems."""
    if component.endswith((".", " ")):
        raise ExtractionError(f"Windows-incompatible trailing dot or space: {member_name!r}")
    if ":" in component:
        raise ExtractionError(f"Alternate data streams are not allowed: {member_name!r}")
    basename = component.split(".", 1)[0].upper()
    if basename in _WINDOWS_RESERVED_BASENAMES:
        raise ExtractionError(f"Reserved Windows device name: {member_name!r}")
    if len(component.encode("utf-16-le", errors="surrogatepass")) // 2 > 255:
        raise ExtractionError(f"ZIP path component exceeds 255 UTF-16 units: {member_name!r}")


def _validated_members(archive: zipfile.ZipFile, *, max_entries: int,
                       max_file_size: int, max_total_size: int,
                       max_compression_ratio: float) -> list[zipfile.ZipInfo]:
    members = archive.infolist()
    if len(members) > max_entries:
        raise ExtractionError(f"Archive has {len(members)} entries; limit is {max_entries}")

    seen: set[str] = set()
    path_kinds: dict[str, bool] = {}
    total = 0
    for info in members:
        name = info.filename
        if not name or chr(0) in name or chr(92) in name:
            raise ExtractionError(f"Unsafe ZIP member path: {name!r}")
        canonical_name = name[:-1] if name.endswith("/") else name
        raw_parts = canonical_name.split("/")
        if not canonical_name or any(part in {"", ".", ".."} for part in raw_parts):
            raise ExtractionError(f"Path traversal or non-canonical path: {name!r}")
        for component in raw_parts:
            _validate_portable_component(component, name)
        path = PurePosixPath(name)
        if path.is_absolute():
            raise ExtractionError(f"Path traversal or non-canonical path: {name!r}")
        normalized = path.as_posix().rstrip("/")
        normalized_key = normalized.casefold()
        if normalized_key in seen:
            raise ExtractionError(f"Duplicate or case-insensitive archive path: {name!r}")
        seen.add(normalized_key)
        path_kinds[normalized_key] = info.is_dir()

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

    for member_path, is_directory in path_kinds.items():
        if is_directory:
            continue
        parts = member_path.split("/")
        for index in range(1, len(parts)):
            parent = "/".join(parts[:index])
            if path_kinds.get(parent) is False:
                raise ExtractionError(
                    f"File member conflicts with a nested path: {member_path!r}"
                )
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
