# Data contracts and quality validation

Contracts are versioned JSON documents. Each field declares a primitive type, nullability and optional allowed domain. A contract can also enforce minimum/maximum row counts and composite primary-key uniqueness.

The validation module uses only the Python standard library and streams CSV rows, so large source files do not need to be loaded entirely into memory. Contract JSON is parsed strictly: version and row bounds must be integers, nullability must be boolean, and primary keys and allowed values must be arrays. Invalid declarations are rejected rather than silently coerced.

```bash
python - <<'PY'
from pathlib import Path
from brasil_eleitoral.validation import load_contract, validate_csv

contract = load_contract(Path("contracts/tse/election-results.v1.json"))
report = validate_csv(Path("data/landing/election-results.csv"), contract)
print(report.to_dict())
if not report.valid:
    raise SystemExit(1)
PY
```

The included TSE results contract is a normalized target schema, not an assertion that every TSE resource already uses these column names. Each source resource must be mapped using its official data dictionary before it is validated against this contract. Validation reports contain stable error codes suitable for CI and pipeline monitoring.
