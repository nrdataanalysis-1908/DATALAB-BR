"""Safe loader for the locally discovered TSE CKAN catalog."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_catalog(manifest_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Load manifest entries whose JSON files are direct children of its directory."""
    if not manifest_path.is_file():
        return {}, []

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Não foi possível ler o manifesto CKAN: {manifest_path}") from exc

    if not isinstance(manifest, dict):
        raise ValueError("O manifesto CKAN precisa ser um objeto JSON.")

    entries = manifest.get("datasets", [])
    if not isinstance(entries, list):
        raise ValueError("manifest.datasets precisa ser uma lista.")

    base = manifest_path.parent.resolve()
    datasets: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        filename = entry.get("path")
        if not isinstance(filename, str) or not filename.endswith(".json"):
            continue
        target = (base / filename).resolve()
        if target.parent != base or not target.is_file():
            continue
        try:
            item = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(item, dict):
            datasets.append(item)
    return manifest, datasets
