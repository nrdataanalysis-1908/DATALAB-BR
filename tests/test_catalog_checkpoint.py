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
            self.assertEqual(first_client.calls, [(0, 1)])

            updated_client = Client({
                1: {
                    "count": 2,
                    "results": [{"name": "new-dataset", "resources": []}],
                },
                2: {"count": 2, "results": []},
            })
            updated_manifest = discover_catalog(updated_client, root, page_size=1)

            self.assertEqual(updated_client.calls, [(1, 1)])
            self.assertEqual(updated_manifest["dataset_count"], 2)
            self.assertTrue(updated_manifest["complete"])
            self.assertTrue((root / "new-dataset.json").is_file())


    def test_catalog_rejects_results_beyond_reported_remote_count(self):
        class Client:
            base_url = "https://dadosabertos.tse.jus.br"

            def search_page(self, *, start, rows):
                return {
                    "count": 0,
                    "results": [{"name": "unexpected-dataset", "resources": []}],
                }

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "beyond the reported total"):
                discover_catalog(Client(), Path(tmp), page_size=10)


    def test_catalog_rejects_page_that_extends_past_reported_total(self):
        class Client:
            base_url = "https://dadosabertos.tse.jus.br"

            def search_page(self, *, start, rows):
                return {
                    "count": 1,
                    "results": [
                        {"name": "first-dataset", "resources": []},
                        {"name": "unexpected-dataset", "resources": []},
                    ],
                }

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "beyond the reported total"):
                discover_catalog(Client(), Path(tmp), page_size=2)


    def test_catalog_continues_after_a_nonempty_short_page(self):
        class Client:
            base_url = "https://dadosabertos.tse.jus.br"

            def __init__(self):
                self.calls = []

            def search_page(self, *, start, rows):
                self.calls.append((start, rows))
                pages = {
                    0: [{"name": "first-dataset", "resources": []}],
                    1: [
                        {"name": "second-dataset", "resources": []},
                        {"name": "third-dataset", "resources": []},
                    ],
                }
                return {"count": 3, "results": pages.get(start, [])}

        with tempfile.TemporaryDirectory() as tmp:
            client = Client()
            manifest = discover_catalog(client, Path(tmp), page_size=2)

            self.assertEqual(client.calls, [(0, 2), (1, 2)])
            self.assertEqual(manifest["dataset_count"], 3)
            self.assertTrue(manifest["complete"])


    def test_checkpoint_is_bound_to_its_ckan_source(self):
        class Client:
            def __init__(self, base_url, dataset_name):
                self.base_url = base_url
                self.dataset_name = dataset_name
                self.calls = []

            def search_page(self, *, start, rows):
                self.calls.append((start, rows))
                if start:
                    return {"count": 1, "results": []}
                return {
                    "count": 1,
                    "results": [{"name": self.dataset_name, "resources": []}],
                }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = Client("https://source-a.example", "source-a-dataset")
            discover_catalog(original, root, page_size=1)

            replacement = Client("https://source-b.example", "source-b-dataset")
            manifest = discover_catalog(replacement, root, page_size=1)
            checkpoint = json.loads(
                (root / ".ckan_checkpoint.json").read_text(encoding="utf-8")
            )

            self.assertEqual(replacement.calls, [(0, 1)])
            self.assertEqual(
                [item["name"] for item in manifest["datasets"]],
                ["source-b-dataset"],
            )
            self.assertEqual(checkpoint["source_url"], replacement.base_url)


    def test_completed_checkpoint_restarts_when_remote_catalog_shrinks(self):
        class Client:
            base_url = "https://dadosabertos.tse.jus.br"

            def __init__(self, count, records):
                self.count = count
                self.records = records
                self.calls = []

            def search_page(self, *, start, rows):
                self.calls.append((start, rows))
                return {
                    "count": self.count,
                    "results": self.records[start:start + rows],
                }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            initial_records = [
                {"name": "first-dataset", "resources": []},
                {"name": "removed-dataset", "resources": []},
            ]
            initial = Client(2, initial_records)
            first_manifest = discover_catalog(initial, root, page_size=1)
            self.assertTrue(first_manifest["complete"])

            reduced = Client(1, [{"name": "first-dataset", "resources": []}])
            manifest = discover_catalog(reduced, root, page_size=1)

            self.assertEqual(reduced.calls, [(2, 1), (0, 1)])
            self.assertEqual(manifest["dataset_count"], 1)
            self.assertTrue(manifest["complete"])
            self.assertEqual(
                [item["name"] for item in manifest["datasets"]],
                ["first-dataset"],
            )


    def test_checkpoint_without_remote_total_cannot_resume_at_nonzero_offset(self):
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
                    "source_url": Client.base_url,
                    "next_start": 1,
                    "total": None,
                    "seen": {},
                }),
                encoding="utf-8",
            )
            client = Client()
            manifest = discover_catalog(client, root, page_size=1)

            self.assertEqual(client.calls, [(0, 1), (1, 1)])
            self.assertEqual(manifest["dataset_count"], 2)
            self.assertTrue(manifest["complete"])


    def test_legacy_checkpoint_without_source_identity_restarts_safely(self):
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
                json.dumps({"next_start": 1, "total": 2, "seen": {}}),
                encoding="utf-8",
            )
            client = Client()
            manifest = discover_catalog(client, root, page_size=1)

            self.assertEqual(client.calls, [(0, 1), (1, 1)])
            self.assertEqual(manifest["dataset_count"], 2)
            self.assertTrue(manifest["complete"])


if __name__ == "__main__":
    unittest.main()
