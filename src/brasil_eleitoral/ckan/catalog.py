"""Paginated CKAN discovery and deterministic local catalog export."""
from __future__ import annotations
import hashlib
import json
import logging
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from .client import CKANClient

LOG = logging.getLogger(__name__)

def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n"); stream.flush(); os.fsync(stream.fileno())
        os.replace(temp_name, path)
    except Exception:
        try: os.unlink(temp_name)
        except FileNotFoundError: pass
        raise

_WINDOWS_RESERVED_BASENAMES = {
    "CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
    "COM¹", "COM²", "COM³", "LPT¹", "LPT²", "LPT³",
}


def _dataset_filename(name: str) -> str:
    """Return a portable filename without Windows device-name aliases."""
    basename = name.split(".", 1)[0].upper()
    if basename in _WINDOWS_RESERVED_BASENAMES or name.endswith("."):
        digest = hashlib.sha256(name.encode("utf-8")).hexdigest()[:16]
        return f"_dataset_{digest}.json"
    return f"{name}.json"

def _optional_text(value: Any, field: str) -> str | None:
    if value is not None and not isinstance(value, str):
        raise ValueError(f"CKAN dataset {field} must be text or null")
    return value


def normalize_dataset(dataset: dict[str, Any], *, source_url: str, extracted_at: str) -> dict[str, Any]:
    if not isinstance(dataset, dict):
        raise ValueError("CKAN dataset must be an object")

    organization = dataset.get("organization")
    if organization is None:
        organization = {}
    if not isinstance(organization, dict):
        raise ValueError("CKAN dataset organization must be an object")
    organization_title = _optional_text(organization.get("title"), "organization title")
    organization_id = _optional_text(organization.get("id"), "organization id")

    collections = {
        "resources": dataset.get("resources"),
        "groups": dataset.get("groups"),
        "tags": dataset.get("tags"),
    }
    for label, value in collections.items():
        if value is not None and (
            not isinstance(value, list)
            or any(not isinstance(item, dict) for item in value)
        ):
            raise ValueError(f"CKAN dataset {label} must be an array of objects")

    resources = []
    for resource in collections["resources"] or []:
        format_value = _optional_text(resource.get("format"), "resource format")
        size_value = resource.get("size")
        if (
            size_value is not None
            and (
                isinstance(size_value, bool)
                or not isinstance(size_value, int)
                or size_value < 0
            )
        ):
            raise ValueError("CKAN dataset resource size must be a non-negative integer or null")
        datastore_active = resource.get("datastore_active")
        if datastore_active is not None and not isinstance(datastore_active, bool):
            raise ValueError("CKAN dataset resource datastore_active must be boolean or null")
        resources.append({
            "id": _optional_text(resource.get("id"), "resource id"),
            "name": _optional_text(resource.get("name"), "resource name"),
            "description": _optional_text(resource.get("description"), "resource description"),
            "format": format_value.upper() if format_value else None,
            "url": _optional_text(resource.get("url"), "resource URL"),
            "created": _optional_text(resource.get("created"), "resource creation timestamp"),
            "last_modified": _optional_text(resource.get("last_modified"), "resource modification timestamp"),
            "size": size_value,
            "hash": _optional_text(resource.get("hash"), "resource hash"),
            "datastore_active": datastore_active,
            "mimetype": _optional_text(resource.get("mimetype"), "resource MIME type"),
        })
    return {
        "id": _optional_text(dataset.get("id"), "dataset id"),
        "name": _optional_text(dataset.get("name"), "dataset name"),
        "title": _optional_text(dataset.get("title"), "dataset title"),
        "notes": _optional_text(dataset.get("notes"), "dataset notes"),
        "organization": organization_title,
        "organization_id": organization_id,
        "groups": [
            _optional_text(group.get("title"), "group title")
            or _optional_text(group.get("name"), "group name")
            for group in collections["groups"] or []
        ],
        "tags": [
            _optional_text(tag.get("name"), "tag name")
            for tag in collections["tags"] or []
        ],
        "metadata_created": _optional_text(dataset.get("metadata_created"), "dataset creation timestamp"),
        "metadata_modified": _optional_text(dataset.get("metadata_modified"), "dataset modification timestamp"),
        "license_id": _optional_text(dataset.get("license_id"), "dataset license id"),
        "license_title": _optional_text(dataset.get("license_title"), "dataset license title"),
        "url": _optional_text(dataset.get("url"), "dataset URL"),
        "resources": resources,
        "source": "Tribunal Superior Eleitoral",
        "source_url": source_url,
        "extracted_at": extracted_at,
    }

def _load_checkpoint(path: Path) -> dict[str, Any]:
    default: dict[str, Any] = {"source_url": None, "next_start": 0, "total": None, "seen": {}}
    if path.is_symlink():
        LOG.warning("Ignoring symbolic-link checkpoint: %s", path)
        return default
    if not path.exists():
        return default
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        LOG.warning("Ignoring invalid checkpoint %s: %s", path, exc)
        return default

    if not isinstance(loaded, dict):
        LOG.warning("Ignoring checkpoint with an invalid root object: %s", path)
        return default
    next_start = loaded.get("next_start", 0)
    total = loaded.get("total")
    seen = loaded.get("seen")
    source_url = loaded.get("source_url")
    valid = (
        isinstance(next_start, int) and not isinstance(next_start, bool) and next_start >= 0
        and (total is None or (
            isinstance(total, int) and not isinstance(total, bool) and total >= 0
        ))
        and (total is not None or next_start == 0)
        and (source_url is None or isinstance(source_url, str))
        and isinstance(seen, dict)
        and len(seen) <= next_start
        and (total is None or next_start <= total)
        and all(
            isinstance(name, str)
            and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}", name)
            and isinstance(digest, str)
            and re.fullmatch(r"[0-9a-f]{64}", digest)
            for name, digest in seen.items()
        )
    )
    if not valid:
        LOG.warning("Ignoring checkpoint with invalid offsets, dataset names or SHA-256 values: %s", path)
        return default
    return {
        "source_url": source_url,
        "next_start": next_start,
        "total": total,
        "seen": dict(seen),
    }


def discover_catalog(client: CKANClient, output_dir: Path, *, page_size: int = 100,
                     checkpoint_path: Path | None = None,
                     progress: Callable[[int, int], None] | None = None) -> dict[str, Any]:
    if (
        isinstance(page_size, bool)
        or not isinstance(page_size, int)
        or not 1 <= page_size <= 1000
    ):
        raise ValueError("page_size must be an integer between 1 and 1000")
    checkpoint_path = checkpoint_path or output_dir / ".ckan_checkpoint.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = _load_checkpoint(checkpoint_path)
    start, seen, total = checkpoint["next_start"], checkpoint["seen"], checkpoint["total"]
    source_url = client.base_url
    if checkpoint.get("source_url") != source_url:
        if seen or start or total is not None:
            LOG.warning("Checkpoint belongs to a different CKAN source; restarting discovery")
        start, seen, total = 0, {}, None
    verified_seen: dict[str, str] = {}
    checkpoint_incomplete = False
    for name, expected_digest in seen.items():
        cached_path = output_dir / _dataset_filename(name)
        if cached_path.is_symlink() or not cached_path.is_file():
            checkpoint_incomplete = True
            continue
        try:
            actual_digest = hashlib.sha256(cached_path.read_bytes()).hexdigest()
        except OSError:
            checkpoint_incomplete = True
            continue
        if actual_digest != expected_digest:
            checkpoint_incomplete = True
            continue
        verified_seen[name] = expected_digest
    if checkpoint_incomplete:
        LOG.warning("Checkpoint references missing or changed datasets; restarting pagination")
        start = 0
    seen = verified_seen
    extracted_at = datetime.now(timezone.utc).isoformat()
    # A completed checkpoint gets one remote probe so newly appended datasets are discovered.
    probe_completed_checkpoint = total is not None and start >= total
    catalog_restart_used = False
    while total is None or start < total or probe_completed_checkpoint:
        probe_completed_checkpoint = False
        page = client.search_page(start=start, rows=page_size)
        if not isinstance(page, dict):
            raise ValueError("CKAN page response must be an object")
        remote_count = page.get("count")
        results = page.get("results")
        if (
            isinstance(remote_count, bool)
            or not isinstance(remote_count, int)
            or remote_count < 0
        ):
            raise ValueError("CKAN page response count must be a non-negative integer")
        if not isinstance(results, list):
            raise ValueError("CKAN page response results must be an array")
        if len(results) > page_size:
            raise ValueError("CKAN page response exceeds the requested page size")
        if total is not None and remote_count < total:
            if start > 0:
                if catalog_restart_used:
                    raise ValueError("CKAN catalog shrank repeatedly during discovery")
                LOG.warning("CKAN catalog shrank during pagination; restarting from offset zero")
                start, seen = 0, {}
                total = remote_count
                catalog_restart_used = True
                continue
            seen = {}
        total = remote_count
        if not results:
            if start < total:
                raise ValueError(
                    "CKAN returned an empty page before the reported total was reached"
                )
            break
        if start + len(results) > total:
            raise ValueError("CKAN page returned results beyond the reported total")
        for dataset in results:
            if not isinstance(dataset, dict) or not dataset.get("name"):
                LOG.warning("Skipping malformed CKAN dataset at offset %d", start); continue
            try:
                normalized = normalize_dataset(
                    dataset, source_url=client.base_url, extracted_at=extracted_at
                )
            except ValueError as exc:
                LOG.warning("Skipping malformed CKAN dataset at offset %d: %s", start, exc)
                continue
            if (
                not isinstance(normalized["name"], str)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}", normalized["name"])
            ):
                LOG.warning("Skipping unsafe CKAN dataset slug: %r", normalized["name"]); continue
            target = output_dir / _dataset_filename(normalized["name"])
            _atomic_json(target, normalized)
            seen[normalized["name"]] = hashlib.sha256(target.read_bytes()).hexdigest()
        start += len(results)
        checkpoint = {
            "source_url": source_url,
            "next_start": start,
            "total": total,
            "seen": seen,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        _atomic_json(checkpoint_path, checkpoint)
        if progress: progress(start, total)
        LOG.info("Catalog discovery: %d/%d datasets", start, total)
        # Continue after short non-empty pages while the remote count says
        # additional offsets remain; some CKAN deployments underfill pages.
    manifest = {"source": "Tribunal Superior Eleitoral", "source_url": client.base_url,
        "api": f"{client.base_url}/api/3/action/", "action": "package_search",
        "discovered_at": datetime.now(timezone.utc).isoformat(), "dataset_count": len(seen),
        "remote_count": total, "complete": total is not None and len(seen) >= total,
        "datasets": [{"name": name, "sha256": digest, "path": _dataset_filename(name)} for name, digest in sorted(seen.items())]}
    _atomic_json(output_dir / "manifest.json", manifest)
    return manifest
