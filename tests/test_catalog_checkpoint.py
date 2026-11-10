import json
import tempfile
import unittest
from pathlib import Path

from brasil_eleitoral.ckan.catalog import discover_catalog


class CheckpointRecoveryTests(unittest.TestCase):
    def test_missing_checkpoint_dataset_restarts_from_first_page(self):
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
            (root / ".ckan_checkpoint.json").write_text(
                json.dumps({
                    "next_start": 1,
                    "total": 2,
                    "seen": {"first-dataset": "a" * 64},
                }),
                encoding="utf-8",
            )
            client = Client()
            manifest = discover_catalog(client, root, page_size=1)

            self.assertEqual(client.calls, [(0, 1), (1, 1)])
            self.assertEqual(manifest["dataset_count"], 2)
            self.assertTrue(manifest["complete"])
            self.assertTrue((root / "first-dataset.json").is_file())
            self.assertTrue((root / "second-dataset.json").is_file())

    def test_invalid_checkpoint_is_ignored_and_discovery_restarts_safely(self):
        class Client:
            base_url = "https://dadosabertos.tse.jus.br"

            def __init__(self):
                self.calls = []

            def search_page(self, *, start, rows):
                self.calls.append((start, rows))
                return {
                    "count": 1,
                    "results": [{"name": "valid-dataset", "resources": []}],
                }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".ckan_checkpoint.json").write_text(
                json.dumps({
                    "next_start": "not-an-offset",
                    "total": True,
                    "seen": {"../outside": "not-a-sha256"},
                }),
                encoding="utf-8",
            )
            client = Client()
            manifest = discover_catalog(client, root, page_size=10)

            self.assertEqual(client.calls, [(0, 10)])
            self.assertEqual(manifest["dataset_count"], 1)
            self.assertTrue(manifest["complete"])
            self.assertEqual(
                manifest["datasets"][0]["path"],
                "valid-dataset.json",
            )
            self.assertEqual(
                [item["name"] for item in manifest["datasets"]],
                ["valid-dataset"],
            )


    def test_non_utf8_checkpoint_is_ignored_and_discovery_restarts(self):
        class Client:
            base_url = "https://dadosabertos.tse.jus.br"

            def __init__(self):
                self.calls = []

            def search_page(self, *, start, rows):
                self.calls.append((start, rows))
                return {
                    "count": 1,
                    "results": [{"name": "utf8-recovered", "resources": []}],
                }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".ckan_checkpoint.json").write_bytes(
                b'{"next_start": 1, "seen": "\\xff"}'
            )
            client = Client()
            manifest = discover_catalog(client, root, page_size=10)

            self.assertEqual(client.calls, [(0, 10)])
            self.assertEqual(manifest["dataset_count"], 1)
            self.assertTrue(manifest["complete"])
            self.assertTrue((root / "utf8-recovered.json").is_file())


if __name__ == "__main__":
    unittest.main()
