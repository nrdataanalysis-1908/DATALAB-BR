import tempfile
import unittest
from pathlib import Path

from brasil_eleitoral.ingestion.downloader import download_resource


class DownloadLimitTests(unittest.TestCase):
    def test_rejects_unbounded_retry_and_transfer_settings_before_network_io(self):
        invalid_options = (
            {"timeout": 600.1},
            {"retries": 11},
            {"backoff": 300.1},
            {"chunk_size": 16 * 1024 * 1024 + 1},
        )
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "resource.bin"
            for options in invalid_options:
                with self.subTest(options=options):
                    with self.assertRaises(ValueError):
                        kwargs = {"retries": 0, **options}
                        download_resource(
                            "https://example.test/resource.bin",
                            target,
                            **kwargs,
                        )


if __name__ == "__main__":
    unittest.main()
