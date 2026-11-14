import json
import tempfile
import unittest
from pathlib import Path

from brasil_eleitoral.ingestion.downloader import download_resources


class ManifestEntryTests(unittest.TestCase):
    def test_only_valid_direct_child_entries_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            kept = root / "kept.csv"
            kept.write_text("verified", encoding="utf-8")
            outside = root.parent / f"{root.name}-outside.csv"
            outside.write_text("outside", encoding="utf-8")
            tampered = root / "tampered.csv"
            tampered.write_text("changed", encoding="utf-8")
            linked = root / "linked.csv"
            try:
                linked.symlink_to(outside)
            except OSError:
                linked = None
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "resources": [
                    {"resource_id": "kept", "path": str(kept), "status": "verified"},
                    "not-an-object",
                    {"resource_id": "missing-path"},
                    {"resource_id": "wrong-path-type", "path": ["kept.csv"]},
                    {"resource_id": "outside", "path": str(outside)},
                    {"resource_id": "missing-file", "path": str(root / "missing.csv")},
                    {"resource_id": "tampered", "path": str(tampered), "checksum": "0" * 64},
                    *([{"resource_id": "symlink", "path": str(linked)}] if linked else []),
                    {"resource_id": 42, "path": str(kept)},
                ]
            }), encoding="utf-8")

            result = download_resources([], root, manifest_path=manifest)

            self.assertEqual(result["resource_count"], 1)
            self.assertEqual([item["resource_id"] for item in result["resources"]], ["kept"])


if __name__ == "__main__":
    unittest.main()
