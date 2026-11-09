import json
import tempfile
import unittest
from pathlib import Path

from brasil_eleitoral.validation.contracts import load_contract


class ContractLoadEagerValidationTests(unittest.TestCase):
    def _write(self, root, payload):
        path = root / "contract.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_unknown_field_type_is_rejected_when_contract_is_loaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(Path(tmp), {
                "name": "strict", "version": 1,
                "fields": [{"name": "id", "type": "datetime"}],
            })
            with self.assertRaisesRegex(ValueError, "Unsupported dtype"):
                load_contract(path)

    def test_inconsistent_row_bounds_are_rejected_when_contract_is_loaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(Path(tmp), {
                "name": "strict", "version": 1,
                "fields": [{"name": "id", "type": "string"}],
                "minimum_rows": 10, "maximum_rows": 5,
            })
            with self.assertRaisesRegex(ValueError, "cannot be lower"):
                load_contract(path)


if __name__ == "__main__":
    unittest.main()
