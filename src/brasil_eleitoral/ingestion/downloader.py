"""Resumable, integrity-checked resource downloads (stdlib only)."""
from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import random
import re
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

LOG = logging.getLogger(__name__)
_TRANSIENT = {408, 425, 429, 500, 502, 503, 504}
_CHUNK = 1024 * 1024
_MAX_TIMEOUT = 600.0
_MAX_RETRIES = 10
_MAX_BACKOFF = 300.0
_MAX_CHUNK_SIZE = 16 * 1024 * 1024


class DownloadError(RuntimeError):
    """Raised when a resource cannot be downloaded or verified."""


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def _digest(path: Path, algorithm: str = "sha256") -> str:
    try:
        hasher = hashlib.new(algorithm)
    except ValueError as exc:
        raise ValueError(f"Unsupported checksum algorithm: {algorithm}") from exc
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(_CHUNK), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _safe_filename(name: str) -> str:
    # Keep the filename portable and prevent path traversal from remote metadata.
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name).name).strip("._")
    if not cleaned:
        raise ValueError("Resource filename is empty after sanitization")
    return cleaned[:180]


def download_resource(
    url: str,
    destination: Path,
    *,
    resource_id: str | None = None,
    expected_checksum: str | None = None,
    checksum_algorithm: str = "sha256",
    timeout: float = 60.0,
    retries: int = 4,
    backoff: float = 1.0,
    chunk_size: int = _CHUNK,
) -> dict[str, Any]:
    """Download one HTTP(S) resource, resuming a compatible partial transfer.

    A partial transfer is resumed only when its sidecar matches the URL and
    the server confirms the byte range with HTTP 206. Otherwise it restarts.
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Only absolute HTTP(S) resource URLs are supported")
    if (
        isinstance(timeout, bool) or not isinstance(timeout, (int, float))
        or not math.isfinite(timeout) or timeout <= 0 or timeout > _MAX_TIMEOUT
    ):
        raise ValueError(f"timeout must be finite, positive and <= {_MAX_TIMEOUT:g} seconds")
    if (
        isinstance(backoff, bool) or not isinstance(backoff, (int, float))
        or not math.isfinite(backoff) or backoff < 0 or backoff > _MAX_BACKOFF
    ):
        raise ValueError(f"backoff must be finite, non-negative and <= {_MAX_BACKOFF:g} seconds")
    if isinstance(retries, bool) or not isinstance(retries, int) or retries < 0 or retries > _MAX_RETRIES:
        raise ValueError(f"retries must be an integer between 0 and {_MAX_RETRIES}")
    if (
        isinstance(chunk_size, bool) or not isinstance(chunk_size, int)
        or chunk_size < 1 or chunk_size > _MAX_CHUNK_SIZE
    ):
        raise ValueError(f"chunk_size must be an integer between 1 and {_MAX_CHUNK_SIZE}")
    try:
        checksum = hashlib.new(checksum_algorithm)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Unsupported checksum algorithm: {checksum_algorithm!r}") from exc
    if checksum.digest_size <= 0:
        raise ValueError("Variable-length checksum algorithms are not supported")
    if expected_checksum is not None:
        if (
            not isinstance(expected_checksum, str)
            or len(expected_checksum) != checksum.digest_size * 2
            or not re.fullmatch(r"[0-9a-fA-F]+", expected_checksum)
        ):
            raise ValueError(f"expected_checksum must be a {checksum.digest_size * 2}-character hexadecimal digest")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".part")
    state_path = destination.with_name(destination.name + ".part.json")
    state: dict[str, Any] = {}
    if partial.exists() and state_path.exists():
        try:
            candidate = json.loads(state_path.read_text(encoding="utf-8"))
            if candidate.get("url") == url and candidate.get("etag") is not None:
                state = candidate
        except (OSError, json.JSONDecodeError, AttributeError):
            state = {}
    if not state:
        partial.unlink(missing_ok=True)
        state_path.unlink(missing_ok=True)

    last_error: Exception | None = None
    for attempt in range(retries + 1):
        offset = partial.stat().st_size if partial.exists() else 0
        headers = {"User-Agent": "BrasilEleitoralDataLab/0.1", "Accept-Encoding": "identity"}
        if offset and state.get("etag"):
            headers["Range"] = f"bytes={offset}-"
            headers["If-Range"] = str(state["etag"])
        request = Request(url, headers=headers)
        try:
            with urlopen(request, timeout=timeout) as response:
                status = getattr(response, "status", response.getcode())
                etag = response.headers.get("ETag")
                total_header = response.headers.get("Content-Length")
                expected_total = None
                if offset and status == 206:
                    content_range = response.headers.get("Content-Range", "")
                    match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", content_range.strip())
                    if not match:
                        raise DownloadError(f"Invalid Content-Range while resuming: {content_range!r}")
                    range_start, range_end, range_total = map(int, match.groups())
                    range_size = range_end - range_start + 1
                    if range_start != offset or range_end < range_start or range_end + 1 != range_total:
                        raise DownloadError(f"Incomplete or inconsistent Content-Range: {content_range!r}")
                    if total_header and (not total_header.isdigit() or int(total_header) != range_size):
                        raise DownloadError("Content-Length does not match the resumed byte range")
                    if not etag or etag != state.get("etag"):
                        raise DownloadError("ETag missing or changed during resumed download")
                    expected_total = range_total
                    mode = "ab"
                elif status == 200:
                    # A full response restarts the transfer, even if a Range
                    # request was sent and the server ignored it.
                    offset = 0
                    mode = "wb"
                    if total_header and total_header.isdigit():
                        expected_total = int(total_header)
                    state = {"url": url, "etag": etag, "last_modified": response.headers.get("Last-Modified")}
                else:
                    raise DownloadError(f"Unexpected HTTP status for resource download: {status}")
                _atomic_json(state_path, state)
                with partial.open(mode) as output:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        output.write(chunk)
                    output.flush()
                    os.fsync(output.fileno())
            actual_size = partial.stat().st_size
            if expected_total is not None and actual_size != expected_total:
                raise DownloadError(f"Truncated response: expected {expected_total} bytes, received {actual_size}")
            actual_checksum = _digest(partial, checksum_algorithm)
            if expected_checksum and actual_checksum.lower() != expected_checksum.lower():
                # Keep the bytes for diagnosis, but invalidate their resume
                # metadata so a later invocation starts from a clean transfer.
                state_path.unlink(missing_ok=True)
                raise DownloadError(
                    f"Checksum mismatch ({checksum_algorithm}): expected {expected_checksum}, got {actual_checksum}"
                )
            os.replace(partial, destination)
            state_path.unlink(missing_ok=True)
            return {
                "resource_id": resource_id, "url": url, "path": str(destination),
                "size_bytes": destination.stat().st_size, "checksum_algorithm": checksum_algorithm,
                "checksum": actual_checksum, "expected_checksum": expected_checksum,
                "etag": state.get("etag"), "last_modified": state.get("last_modified"),
                "downloaded_at": datetime.now(timezone.utc).isoformat(), "status": "verified",
            }
        except HTTPError as exc:
            last_error = exc
            if exc.code not in _TRANSIENT or attempt >= retries:
                break
        except (URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt >= retries:
                break
        except DownloadError:
            # Integrity and protocol errors are not transient; retain partial
            # bytes for diagnosis, but never publish them as a completed file.
            raise
        delay = min(
            backoff * (2 ** attempt) + random.uniform(0, backoff / 4),
            _MAX_BACKOFF,
        )
        LOG.warning("Download failed for %s (%s); retry %d/%d in %.2fs",
                    url, last_error, attempt + 1, retries, delay)
        time.sleep(delay)
    raise DownloadError(f"Download failed after {retries + 1} attempts: {last_error}") from last_error


def _load_manifest_entries(manifest_path: Path, output_dir: Path) -> dict[str, dict[str, Any]]:
    """Load only structurally valid entries that point to direct output files."""
    if not manifest_path.exists():
        return {}
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        LOG.warning("Existing download manifest is unreadable; a new manifest will     entries = _load_manifest_entries(manifest_path, output_dir).resolve()
    for index, item in enumerate(resources):
        if not isinstance(item, dict):
            LOG.warning("Ignoring malformed manifest resource at index %d", index)
            continue
        resource_id = item.get("resource_id")
        existing_path = item.get("path")
        if (
            not isinstance(resource_id, str) or not resource_id.strip()
            or not isinstance(existing_path, str) or not existing_path.strip()
        ):
            LOG.warning("Ignoring manifest resource with invalid identity or path at index %d", index)
            continue
        try:
            if Path(existing_path).parent.resolve() != output_root:
                LOG.warning("Ignoring manifest resource outside the output directory: %s", resource_id)
                continue
        except (OSError, RuntimeError, ValueError):
            LOG.warning("Ignoring manifest resource with an invalid path: %s", resource_id)
            continue
        entries[resource_id] = item
    return entries


def download_resources(
    resources: list[dict[str, Any]],
    output_dir: Path,
    *,
    manifest_path: Path | None = None,
    timeout: float = 60.0,
    retries: int = 4,
) -> dict[str, Any]:
    """Download a list of CKAN-like resources and atomically maintain a manifest."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = Path(manifest_path) if manifest_path else output_dir / "manifest.json"
    entries: dict[str, dict[str, Any]] = {}
    if manifest_path.exists():
        try:
            old = json.loads(manifest_path.read_text(encoding="utf-8"))
            entries = {str(item["resource_id"]): item for item in old.get("resources", [])
                       if item.get("resource_id")}
        except (OSError, json.JSONDecodeError, KeyError, TypeError):
            LOG.warning("Existing download manifest is invalid; a new manifest will be built")
    failures: list[dict[str, str]] = []
    claimed_filenames: dict[str, str] = {}
    for existing_id, existing in entries.items():
        existing_path = existing.get("path")
        if existing_path:
            path = Path(existing_path)
            if path.parent.resolve() == output_dir.resolve():
                claimed_filenames[path.name.casefold()] = existing_id
    seen_resource_ids: set[str] = set()
    manifest_resolved = manifest_path.resolve()
    for index, resource in enumerate(resources):
        if not isinstance(resource, dict):
            failures.append({
                "resource_id": f"resource-{index}",
                "error": "resource metadata must be an object",
            })
            continue
        url = resource.get("url")
        rid = str(resource.get("id") or resource.get("name") or f"resource-{index}")
        if rid in seen_resource_ids:
            failures.append({"resource_id": rid, "error": "duplicate resource identifier"})
            continue
        seen_resource_ids.add(rid)
        if not url:
            failures.append({"resource_id": rid, "error": "missing URL"})
            continue
        try:
            filename = _safe_filename(resource.get("name") or rid)
        except (TypeError, ValueError) as exc:
            failures.append({"resource_id": rid, "error": str(exc)})
            continue
        target = output_dir / filename
        if target.resolve() == manifest_resolved:
            failures.append({
                "resource_id": rid,
                "error": "resource filename conflicts with the download manifest",
            })
            continue
        filename_key = filename.casefold()
        owner = claimed_filenames.get(filename_key)
        if owner is not None and owner != rid:
            failures.append({
                "resource_id": rid,
                "error": f"resource filename collides with {owner}",
            })
            continue
        claimed_filenames[filename_key] = rid
        try:
            record = download_resource(
                url, target, resource_id=rid,
                expected_checksum=resource.get("expected_checksum"),
                checksum_algorithm=resource.get("checksum_algorithm", "sha256"),
                timeout=timeout, retries=retries,
            )
            entries[rid] = record
        except Exception as exc:
            failures.append({"resource_id": rid, "error": str(exc)})
            LOG.exception("Resource download failed: %s", rid)
        _atomic_json(manifest_path, {
            "schema_version": 1, "updated_at": datetime.now(timezone.utc).isoformat(),
            "resource_count": len(entries), "failure_count": len(failures),
            "resources": [entries[key] for key in sorted(entries)],
            "failures": failures,
        })
    result = {
        "schema_version": 1, "updated_at": datetime.now(timezone.utc).isoformat(),
        "resource_count": len(entries), "failure_count": len(failures),
        "resources": [entries[key] for key in sorted(entries)], "failures": failures,
    }
    _atomic_json(manifest_path, result)
    return result
