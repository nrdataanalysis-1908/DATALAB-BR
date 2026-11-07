# Safe ZIP extraction

Archives from public catalogs are treated as untrusted input. The extractor rejects path traversal, absolute/drive-qualified paths, backslash paths, duplicate paths, symlinks and special files, encrypted entries, excessive entry/file/total sizes, and suspicious compression ratios. It validates the ZIP CRC before extraction and writes into a temporary staging directory; only a fully extracted archive is atomically renamed into the requested destination.

```python
from pathlib import Path
from brasil_eleitoral.ingestion.extractor import extract_zip

result = extract_zip(
    Path("data/landing/tse/results.zip"),
    Path("data/bronze/extracted/results"),
)
print(result)
```

The destination must not already exist. Configure limits explicitly for datasets whose documented size exceeds the conservative defaults. Extraction does not execute files or follow archive-created links.


## Cross-platform path safety

ZIP members are treated as untrusted input. Before extraction, the validator rejects absolute paths, traversal and non-canonical segments, symbolic links, special files, encrypted entries, duplicate paths, case-insensitive aliases, and file/directory prefix conflicts.

For portable extraction on Windows, every path component is also checked for alternate data stream syntax, reserved device basenames (including names with extensions), trailing dots or spaces, and components longer than 255 UTF-16 code units. Archive size, entry count, compression ratio and CRC are checked before files are published.

Extraction occurs in a temporary staging directory. The destination must not already exist; a validated archive is published only after the complete extraction succeeds.
