"""Run a reproducible local pipeline on an explicitly normalized CSV input."""
from __future__ import annotations

import argparse
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brasil_eleitoral.observability import get_logger
from brasil_eleitoral.transformation import bronze_ingest, gold_aggregate_results, silver_normalize_csv
from brasil_eleitoral.validation import load_contract, validate_csv


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="CSV already mapped to the declared normalized schema")
    parser.add_argument("--contract", required=True, type=Path, help="Versioned JSON data contract")
    parser.add_argument("--output", type=Path, default=Path("data"))
    parser.add_argument("--source-id", default="tse")
    parser.add_argument("--dataset", default="election_results")
    parser.add_argument("--dimensions", nargs="+", required=True, help="Gold aggregation dimensions")
    parser.add_argument("--metric", default="votes")
    args = parser.parse_args()
    print("DATALAB-BR | Desenvolvido por Nadison Roberto | NR TECH | © 2026")

    logger = get_logger()
    run_id = uuid.uuid4().hex
    started = time.monotonic()
    try:
        contract = load_contract(args.contract)
        bronze = bronze_ingest(args.input, args.output, source_id=args.source_id,
                               dataset=args.dataset, execution_id=run_id)
        logger.info("stage_finished", extra={"run_id": run_id, "stage": "bronze",
                                             "dataset": args.dataset, "status": "success"})
        report = validate_csv(args.input, contract)
        if not report.valid:
            logger.error("contract_validation_failed", extra={"run_id": run_id,
                         "stage": "validation", "dataset": args.dataset,
                         "status": "failed", "rows": report.rows_checked})
            print(report.to_dict(), file=sys.stderr)
            return 2
        silver_path = args.output / "silver" / args.dataset / f"{args.input.stem}.csv"
        silver = silver_normalize_csv(args.input, silver_path)
        logger.info("stage_finished", extra={"run_id": run_id, "stage": "silver",
                                             "dataset": args.dataset, "status": "success",
                                             "rows": silver["rows"]})
        gold_path = args.output / "gold" / args.dataset / "aggregates.csv"
        gold = gold_aggregate_results(silver_path, gold_path,
                                      dimensions=args.dimensions, metric=args.metric)
        logger.info("stage_finished", extra={"run_id": run_id, "stage": "gold",
                                             "dataset": args.dataset, "status": "success",
                                             "rows": gold["groups"]})
        logger.info("pipeline_finished", extra={"run_id": run_id, "stage": "pipeline",
                     "dataset": args.dataset, "status": "success",
                     "duration_ms": round((time.monotonic() - started) * 1000)})
        print({"bronze": bronze, "silver": silver, "gold": gold,
               "validation": report.to_dict(), "run_id": run_id})
        return 0
    except Exception:
        logger.exception("pipeline_failed", extra={"run_id": run_id, "stage": "pipeline",
                        "dataset": args.dataset, "status": "failed", "error_code": "pipeline_error"})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
