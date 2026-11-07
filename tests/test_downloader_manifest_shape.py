import json
import tempfile
import unittest
from pathlib import Path

from brasil_eleitoral.ingestion.downloader import download_resources


class ManifestShapeTests(unittest.TestCase):
    def test_non_object_or_non_list_manifest_resources_are_rebuilt(self):
        malformed_payloads = (
            [],
            "not-an-object",
            {"resources": {"resource_id": "x"}},
            {"resources": "not-a-list"},
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / "manifest.json"
            for payload in malformed_payloads:
                with self.subTest(payload=payload):
                    manifest.write_text(json.dumps(payload), encoding="utf-8")
                    result = download_resources([], root, manifest_path=manifest)
                    persisted = json.loads(manifest.read_text(encoding="utf-8"))
                    self.assertEqual(result["resource_count"], 0)
                    self.assertEqual(persisted["resources"], [])
                    self.assertEqual(persisted["schema_version"], 1)

    def test_invalid_json_manifest_is_rebuilt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / "manifest.json"
            manifest.write_text("{invalid", encoding="utf-8")
            result = download_resources([], root, manifest_path=manifest)
            self.assertEqual(result["resources"], [])


if __name__ == "__main__":
    unittest.main()
