# Quality gates for TSE data ingestion

This document defines the minimum acceptance checks before a downloaded TSE resource can move from raw storage into analytical processing.

## 1. Discovery and provenance

For every dataset/resource, retain:

- CKAN package identifier and resource identifier;
- source URL exactly as published by CKAN;
- dataset title, organization and declared format;
- catalog retrieval timestamp in UTC;
- resource metadata returned by CKAN;
- a stable manifest entry so later runs can detect metadata changes.

Do not infer a successful download from catalog discovery alone.

## 2. Download acceptance

A resource is accepted only when all applicable checks pass:

1. The HTTP request completes successfully.
2. The final file exists at the expected destination.
3. The file size is greater than zero.
4. The recorded byte count matches the final file size.
5. The SHA-256 digest is calculated from the completed file.
6. A resumed download is validated as a complete artifact, not merely as a successful Range response.
7. Temporary files are not promoted to the final path after an interrupted or failed transfer.

For servers that do not provide a trustworthy checksum, the locally calculated SHA-256 is an integrity fingerprint, not proof of authenticity.

## 3. Archive safety

Before extracting an archive:

- reject absolute paths and parent-directory traversal;
- reject symbolic links and unsupported special entries;
- enforce limits for entry count, individual expanded size and total expanded size;
- prevent extraction outside the designated destination;
- avoid overwriting unrelated existing files;
- preserve the original archive and its digest for reproducibility.

A failed extraction must not leave a partially populated directory that looks complete.

## 4. Schema and semantic validation

Validate each source layout against an explicit, versioned contract before normalization.

At minimum, record:

- required and optional columns;
- source data types and normalized data types;
- nullability rules;
- primary/natural key definition;
- allowed code domains where documented;
- date and numeric parsing failures;
- duplicate-key counts;
- rejected-row counts and reasons.

Do not silently coerce malformed values or discard rows. Rejections must be measurable and traceable to the source resource.

## 5. Medallion promotion rules

| Layer | Acceptance rule |
|---|---|
| Bronze | Original artifact, provenance metadata and checksum retained |
| Silver | Parsing and contract validation completed; rejected records accounted for |
| Gold | Business grain, dimensions, measures and aggregation rules documented |

Gold tables must not be published from illustrative fixtures or catalog metadata. They require successfully ingested electoral source data and documented transformations.

## 6. Run-level evidence

Each ingestion run should produce a machine-readable summary containing:

- run identifier and UTC start/end timestamps;
- dataset/resource identifiers;
- source URL and artifact path;
- expected and observed byte counts;
- SHA-256 digest;
- extraction outcome;
- contract version;
- accepted and rejected row counts;
- warning/error details;
- final status.

Suggested statuses: `DISCOVERED`, `DOWNLOADED`, `CHECKSUMMED`, `EXTRACTED`, `VALIDATED`, `REJECTED`, `FAILED`.

A status must describe the last completed stage, not the intended next stage.

## 7. Release checklist

Before considering a source resource production-ready:

- [ ] Catalog metadata and source identifiers are retained.
- [ ] Download is complete and independently measurable.
- [ ] SHA-256 is stored with the run evidence.
- [ ] Archive safety checks passed, when applicable.
- [ ] The correct source contract version was applied.
- [ ] Duplicate and rejected-row counts are reported.
- [ ] Bronze/Silver/Gold boundaries are respected.
- [ ] Tests cover malformed, incomplete and boundary-case inputs.
- [ ] The run can be repeated without corrupting existing artifacts.
- [ ] Published indicators disclose source coverage and limitations.

## Scope

These gates are an operational standard for the repository. They do not claim that all TSE datasets have already been ingested or that every source layout has been mapped. Actual readiness must be demonstrated by run evidence and tests.
