import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from brasil_eleitoral.ingestion.extractor import ExtractionError, extract_zip


class SinglePassZipCrcTests(unittest.TestCase):
    def test_crc_is_checked_during_extraction_without_a_preflight_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive_path = root / "valid.zip"
            with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_STORED) as archive:
                archive.writestr("data.csv", b"year,votes\n2022,10\n")

            with patch.object(
                zipfile.ZipFile,
                "testzip",
                side_effect=AssertionError("separate CRC preflight must not run"),
            ):
                result = extract_zip(archive_path, root / "out")

            self.assertEqual(result["status"], "verified")
            self.assertEqual((root / "out/data.csv").read_bytes(), b"year,votes\n2022,10\n")

    def test_streaming_extraction_still_rejects_a_crc_mismatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive_path = root / "corrupt.zip"
            with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_STORED) as archive:
                archive.writestr("data.csv", b"year,votes\n2022,10\n")

            raw = bytearray(archive_path.read_bytes())
            filename_length = struct.unpack_from("<H", raw, 26)[0]
            extra_length = struct.unpack_from("<H", raw, 28)[0]
            data_offset = 30 + filename_length + extra_length
            raw[data_offset] ^= 0x01
            archive_path.write_bytes(raw)

            destination = root / "out"
            with self.assertRaisesRegex(ExtractionError, "CRC"):
                extract_zip(archive_path, destination)

            self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
