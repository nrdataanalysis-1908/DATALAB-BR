#!/usr/bin/env python3
"""Discover the public TSE CKAN catalog and write normalized JSON metadata."""
from __future__ import annotations
import argparse
import logging
from pathlib import Path
from brasil_eleitoral.ckan.catalog import discover_catalog
from brasil_eleitoral.ckan.client import CKANClient

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="https://dadosabertos.tse.jus.br")
    parser.add_argument("--output", type=Path, default=Path("catalog/tse/datasets"))
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--retries", type=int, default=4)
    parser.add_argument("--log-level", default="INFO", choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    args = parser.parse_args()
    print("DATALAB-BR | Desenvolvido por Nadison Roberto | NR TECH | © 2026")
    logging.basicConfig(level=getattr(logging, args.log_level), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    client = CKANClient(args.base_url, timeout=args.timeout, retries=args.retries)
    manifest = discover_catalog(client, args.output, page_size=args.page_size,
        progress=lambda done, total: logging.getLogger(__name__).info("Progress: %d/%d", done, total))
    logging.getLogger(__name__).info("Finished: %d/%s datasets; complete=%s; manifest=%s",
        manifest["dataset_count"], manifest["remote_count"], manifest["complete"], args.output / "manifest.json")
    return 0 if manifest["complete"] else 2

if __name__ == "__main__": raise SystemExit(main())
