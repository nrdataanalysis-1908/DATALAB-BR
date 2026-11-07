import unittest

from brasil_eleitoral.ingestion.downloader import _safe_filename


class WindowsSafeFilenameTests(unittest.TestCase):
    def test_reserved_device_basenames_are_prefixed(self):
        for name in ("CON.csv", "nul.txt", "COM1", "LPT9.xlsx"):
            with self.subTest(name=name):
                self.assertTrue(_safe_filename(name).startswith("resource_"))

    def test_non_reserved_names_keep_their_stable_filename(self):
        self.assertEqual(_safe_filename("SINAPI_2026.csv"), "SINAPI_2026.csv")


if __name__ == "__main__":
    unittest.main()
