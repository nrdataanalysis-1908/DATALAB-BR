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
            json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n"); stream.flush(); os.fsync(stream.fileno())
        os.replace(temp_name, path)
    except Exception:
        try: os.unlink(temp_name)
        except FileNotFoundError: pass
        raise

def normalize_dataset(dataset: dict[str, Any], *, source_url: str, extracted_at: str) -> dict[str, Any]:
    resources = []
    for resource in dataset.get("resources") or []:
        resources.append({"id": resource.get("id"), "name": resource.get("name"),
            "description": resource.get("description"), "format": (resource.get("format") or "").upper() or None,
            "url": resource.get("url"), "created": resource.get("created"),
            "last_modified": resource.get("last_modified"), "size": resource.get("size"),
            "hash": resource.get("hash"), "datastore_active": resource.get("datastore_active"),
            "mimetype": resource.get("mimetype")})
    return {"id": dataset.get("id"), "name": dataset.get("name"), "title": dataset.get("title"),
        "notes": dataset.get("notes"), "organization": (dataset.get("organization") or {}).get("title"),
        "organization_id": (dataset.get("organization") or {}).get("id"),
        "groups": [g.get("title") or g.get("name") for g in dataset.get("groups") or []],
        "tags": [t.get("name") for t in dataset.get("tags") or []],
        "metadata_created": dataset.get("metadata_created"), "metadata_modified": dataset.get("metadata_modified"),
        "license_id": dataset.get("license_id"), "license_title": dataset.get("license_title"),
        "url": dataset.get("url"), "resources": resources, "source": "Tribunal Superior Eleitoral",
        "source_url": source_url, "extracted_at": extracted_at}

def _load_checkpoint(path: Path) -> dict[str, Any]:
    default: dict[str, Any] = {"next_start": 0, "total": None, "seen": {}}
    if not path.exists():
        return default
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        LOG.warning("Ignoring invalid checkpoint %s: %s", path, exc)
        return default

    if not isinstance(loaded, dict):
        LOG.warning("Ignoring checkpoint with an invalid root object: %s", path)
        return default
    next_start = loaded.get("next_start", 0)
    total = loaded.get("total")
    seen = loaded.get("seen")
    valid = (
        isinstance(next_start, int) and not isinstance(next_start, bool) and next_start >= 0
        and (total is None or (
            isinstance(total, int) and not isinstance(total, bool) and total >= 0
        ))
        and isinstance(seen, dict)
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
    return {"next_start": next_start, "total": total, "seen": dict(seen)}


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
    verified_seen: dict[str, str] = {}
    checkpoint_incomplete = False
    for name, expected_digest in seen.items():
        cached_path = output_dir / f"{name}.json"
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
    while total is None or start < total:
        page = client.search_page(start=start, rows=page_size)
        total, results = int(page.get("count", 0)), page["results"]
        if not results: break
        for dataset in results:
            if not isinstance(dataset, dict) or not dataset.get("name"):
                LOG.warning("Skipping malformed CKAN dataset at offset %d", start); continue
            normalized = normalize_dataset(dataset, source_url=client.base_url, extracted_at=extracted_at)
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}", normalized["name"]):
                LOG.warning("Skipping unsafe CKAN dataset slug: %r", normalized["name"]); continue
            target = output_dir / f"{normalized['name']}.json"
            _atomic_json(target, normalized)
            seen[normalized["name"]] = hashlib.sha256(target.read_bytes()).hexdigest()
        start += len(results)
        checkpoint = {"next_start": start, "total": total, "seen": seen, "updated_at": datetime.now(timezone.utc).isoformat()}
        _atomic_json(checkpoint_path, checkpoint)
        if progress: progress(start, total)
        LOG.info("Catalog discovery: %d/%d datasets", start, total)
        if len(results) < page_size: break
    manifest = {"source": "Tribunal Superior Eleitoral", "source_url": client.base_url,
        "api": f"{client.base_url}/api/3/action/", "action": "package_search",
        "discovered_at": datetime.now(timezone.utc).isoformat(), "dataset_count": len(seen),
        "remote_count": total, "complete": total is not None and len(seen) >= total,
        "datasets": [{"name": name, "sha256": digest, "path": f"{name}.json"} for name, digest in sorted(seen.items())]}
    _atomic_json(output_dir / "manifest.json", manifest)
    return manifest
