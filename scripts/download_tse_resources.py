#!/usr/bin/env python3
"""Download CKAN resources listed in a discovered TSE dataset catalog."""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from brasil_eleitoral.ingestion.downloader import download_resources


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=Path("catalog/tse/datasets"))
    parser.add_argument("--output", type=Path, default=Path("data/landing/tse"))
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--retries", type=int, default=4)
    parser.add_argument("--log-level", choices=("DEBUG", "INFO", "WARNING", "ERROR"), default="INFO")
    args = parser.parse_args()
    print("DATALAB-BR | Desenvolvido por Nadison Roberto | NR TECH | © 2026")
    logging.basicConfig(level=getattr(logging, args.log_level),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not args.catalog.is_dir():
        parser.error(f"Catalog directory does not exist: {args.catalog}")
    resources = []
    for path in sorted(args.catalog.glob("*.json")):
        if path.name in {"manifest.json", ".ckan_checkpoint.json"}:
            continue
        try:
            dataset = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logging.error("Skipping invalid catalog file %s: %s", path, exc)
            continue
        for resource in dataset.get("resources", []):
            resources.append({
                **resource,
                "id": resource.get("id") or f"{dataset.get('name')}:{resource.get('name')}",
                "name": f"{dataset.get('name')}_{resource.get('name') or resource.get('id') or 'resource'}",
            })
    result = download_resources(resources, args.output, manifest_path=args.manifest,
                                timeout=args.timeout, retries=args.retries)
    logging.info("Download run: %d verified, %d failed",
                 result["resource_count"], result["failure_count"])
    return 0 if not result["failure_count"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
