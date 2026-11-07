import tempfile
import unittest
from pathlib import Path

from brasil_eleitoral.ingestion.downloader import download_resource


class DownloadUrlValidationTests(unittest.TestCase):
    def test_rejects_embedded_credentials_control_characters_and_invalid_ports(self):
        invalid_urls = (
            "https://user:secret@example.test/resource.csv",
            "https://example.test/resource.csv\nInjected: value",
            " https://example.test/resource.csv",
            "https://example.test:invalid/resource.csv",
        )
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "resource.csv"
            for url in invalid_urls:
                with self.subTest(url=url):
                    with self.assertRaises(ValueError):
                        download_resource(url, target, retries=0)


if __name__ == "__main__":
    unittest.main()
