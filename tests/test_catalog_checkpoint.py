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
                b'{"next_start": 1, "seen": "' + bytes([0xFF]) + b'"}'
            )
            client = Client()
            manifest = discover_catalog(client, root, page_size=10)

            self.assertEqual(client.calls, [(0, 10)])
            self.assertEqual(manifest["dataset_count"], 1)
            self.assertTrue(manifest["complete"])
            self.assertTrue((root / "utf8-recovered.json").is_file())

    def test_symlinked_checkpoint_is_ignored_without_following_target(self):
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
            external = root.parent / f"{root.name}-external-checkpoint.json"
            external_payload = json.dumps({
                "next_start": 1,
                "total": 2,
                "seen": {},
            })
            external.write_text(external_payload, encoding="utf-8")
            checkpoint = root / ".ckan_checkpoint.json"
            try:
                checkpoint.symlink_to(external)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symbolic links are unavailable: {exc}")

            client = Client()
            manifest = discover_catalog(client, root, page_size=1)

            self.assertEqual(client.calls, [(0, 1), (1, 1)])
            self.assertEqual(manifest["dataset_count"], 2)
            self.assertTrue(manifest["complete"])
            self.assertFalse(checkpoint.is_symlink())
            self.assertEqual(external.read_text(encoding="utf-8"), external_payload)


    def test_completed_checkpoint_probes_for_new_remote_datasets(self):
        class Client:
            base_url = "https://dadosabertos.tse.jus.br"

            def __init__(self, pages):
                self.pages = pages
                self.calls = []

            def search_page(self, *, start, rows):
                self.calls.append((start, rows))
                return self.pages.get(
                    start,
                    {"count": 2, "results": []},
                )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first_client = Client({
                0: {
                    "count": 1,
                    "results": [{"name": "first-dataset", "resources": []}],
                },
                1: {"count": 1, "results": []},
            })
            first_manifest = discover_catalog(first_client, root, page_size=1)

            self.assertTrue(first_manifest["complete"])
            self.assertEqual(first_manifest["dataset_count"], 1)

            updated_client = Client({
                1: {
                    "count": 2,
                    "results": [{"name": "new-dataset", "resources": []}],
                },
                2: {"count": 2, "results": []},
            })
            updated_manifest = discover_catalog(updated_client, root, page_size=1)

            self.assertEqual(updated_client.calls, [(1, 1), (2, 1)])
            self.assertEqual(updated_manifest["dataset_count"], 2)
            self.assertTrue(updated_manifest["complete"])
            self.assertTrue((root / "new-dataset.json").is_file())


if __name__ == "__main__":
    unittest.main()
