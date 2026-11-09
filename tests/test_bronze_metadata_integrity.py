import json
import tempfile
import unittest
from pathlib import Path

from brasil_eleitoral.transformation.medallion import MedallionError, bronze_ingest


class BronzeMetadataIntegrityTests(unittest.TestCase):
    def _ingest(self, root):
        source = root / "source.csv"
        source.write_text("state,votes\\nMG,10\\n", encoding="utf-8")
        result = bronze_ingest(source, root / "lake", source_id="tse", dataset="results")
        return source, Path(result["path"]), Path(result["metadata_path"])

    def test_existing_metadata_must_match_the_content_object(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, _, metadata = self._ingest(root)
            payload = json.loads(metadata.read_text(encoding="utf-8"))
            payload["sha256"] = "0" * 64
            metadata.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(MedallionError, "metadata does not match"):
                bronze_ingest(source, root / "lake", source_id="tse", dataset="results")

    def test_existing_content_symlink_is_rejected_even_when_hash_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, destination, _ = self._ingest(root)
            destination.unlink()
            destination.symlink_to(source)
            with self.assertRaisesRegex(MedallionError, "symbolic link"):
                bronze_ingest(source, root / "lake", source_id="tse", dataset="results")

    def test_existing_metadata_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, _, metadata = self._ingest(root)
            external = root / "external.json"
            external.write_text("{}", encoding="utf-8")
            metadata.unlink()
            metadata.symlink_to(external)
            with self.assertRaisesRegex(MedallionError, "metadata must not be a symbolic link"):
                bronze_ingest(source, root / "lake", source_id="tse", dataset="results")


if __name__ == "__main__":
    unittest.main()
