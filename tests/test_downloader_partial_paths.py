import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from brasil_eleitoral.ingestion.downloader import DownloadError, download_resource, download_resources


class PartialDownloadPathTests(unittest.TestCase):
    @patch("brasil_eleitoral.ingestion.downloader.urlopen")
    def test_symlinked_partial_never_modifies_its_target(self, urlopen):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            destination = root / "resource.bin"
            protected = root / "protected.bin"
            protected.write_bytes(b"do-not-change")
            partial = destination.with_name(destination.name + ".part")
            partial.symlink_to(protected)
            partial.with_name(partial.name + ".json").write_text(
                json.dumps({"url": "https://example.test/resource", "etag": '"v1"'}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(DownloadError, "symbolic link"):
                download_resource("https://example.test/resource", destination)
            self.assertEqual(protected.read_bytes(), b"do-not-change")
            urlopen.assert_not_called()

    @patch("brasil_eleitoral.ingestion.downloader.urlopen")
    def test_directory_at_partial_path_is_rejected_before_request(self, urlopen):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "resource.bin"
            destination.with_name(destination.name + ".part").mkdir()
            with self.assertRaisesRegex(DownloadError, "regular file"):
                download_resource("https://example.test/resource", destination)
            urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()

    @patch("brasil_eleitoral.ingestion.downloader.urlopen")
    def test_symlinked_partial_metadata_is_rejected_without_reading_target(self, urlopen):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            destination = root / "resource.bin"
            partial = destination.with_name(destination.name + ".part")
            partial.write_bytes(b"partial bytes")
            state_path = destination.with_name(destination.name + ".part.json")
            protected = root / "protected-state.json"
            protected_payload = json.dumps({
                "url": "https://example.test/resource",
                "etag": '"v1"',
            })
            protected.write_text(protected_payload, encoding="utf-8")
            state_path.symlink_to(protected)

            with self.assertRaisesRegex(DownloadError, "metadata path.*symbolic link"):
                download_resource("https://example.test/resource", destination)

            self.assertEqual(protected.read_text(encoding="utf-8"), protected_payload)
            self.assertEqual(partial.read_bytes(), b"partial bytes")
            urlopen.assert_not_called()

    @patch("brasil_eleitoral.ingestion.downloader.urlopen")
    def test_directory_at_partial_metadata_path_is_rejected(self, urlopen):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "resource.bin"
            destination.with_name(destination.name + ".part").write_bytes(b"partial")
            destination.with_name(destination.name + ".part.json").mkdir()

            with self.assertRaisesRegex(DownloadError, "metadata path.*regular file"):
                download_resource("https://example.test/resource", destination)

            urlopen.assert_not_called()

    def test_symlinked_download_manifest_is_rejected_without_following_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "output"
            output.mkdir()
            external = root / "protected-manifest.json"
            payload = json.dumps({"resources": [], "private": "preserve"})
            external.write_text(payload, encoding="utf-8")
            manifest = output / "manifest.json"
            manifest.symlink_to(external)

            with self.assertRaisesRegex(DownloadError, "manifest path.*symbolic link"):
                download_resources([], output, manifest_path=manifest)

            self.assertTrue(manifest.is_symlink())
            self.assertEqual(external.read_text(encoding="utf-8"), payload)

