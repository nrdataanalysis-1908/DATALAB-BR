import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from brasil_eleitoral.ckan.catalog import discover_catalog


class CheckpointCardinalityTests(unittest.TestCase):
    def test_checkpoint_with_more_seen_datasets_than_scanned_offsets_restarts(self):
        class Client:
            base_url = "https://dadosabertos.tse.jus.br"

            def __init__(self):
                self.calls = []

            def search_page(self, *, start, rows):
                self.calls.append((start, rows))
                records = [
                    {"name": "first-dataset", "resources": []},
                    {"name": "second-dataset", "resources": []},
                ]
                return {"count": 2, "results": records[start:start + rows]}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = b"previously verified"
            digest = hashlib.sha256(payload).hexdigest()
            for name in ("first-dataset", "second-dataset"):
                (root / f"{name}.json").write_bytes(payload)
            (root / ".ckan_checkpoint.json").write_text(
                json.dumps({
                    "source_url": Client.base_url,
                    "next_start": 1,
                    "total": 2,
                    "seen": {
                        "first-dataset": digest,
                        "second-dataset": digest,
                    },
                }),
                encoding="utf-8",
            )

            client = Client()
            manifest = discover_catalog(client, root, page_size=1)

            self.assertEqual(client.calls, [(0, 1), (1, 1)])
            self.assertEqual(manifest["dataset_count"], 2)
            self.assertTrue(manifest["complete"])


if __name__ == "__main__":
    unittest.main()
