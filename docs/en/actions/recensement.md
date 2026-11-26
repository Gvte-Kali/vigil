---
layout: english
title: File census
parent: Actions & analyses
grand_parent: English
nav_order: 25
translation_of: actions/recensement.md
---

# File census

Produce a file inventory with paths, sizes, timestamps, MIME types, SHA-256 checksums, duplicates and extension/content mismatches.

Script: `scripts/analyse/vigil_census.sh`.

## Procedure

1. Select the operator and project.
2. Mount the source read-only.
3. Run the census before targeted analyses.
4. Review the PDF summary and SQLite/TSV detail.

**Running the census again replaces the previous census outputs in that project.** Export existing results first if needed.

## Options

| Option | Behavior |
|---|---|
| `--pdf` / `--no-pdf` | PDF enabled by default |
| `--no-dedup` | Do not mark duplicates |
| `--no-checksafe` | Disable external known-file filtering |
| `--no-project` | Standalone threat-hunting output in `hunt/` |

## Output

Under `data/projects/<project>/`: `census_*.sqlite`, `census_*.tsv`, `.sqlite.sha256` and `.sains.*` / `.doublons.*` results.

| SQLite table | Data |
|---|---|
| `inventory_meta` | Media, mount point, operator, project, time and summary |
| `files` | Metadata, content hash, duplicates, known-file state and extensions |

Dates are normalized to UTC but interpretation still depends on the original filesystem.

## Duplicates and known files

Duplicates are grouped by SHA-256 and remain recorded. Targeted analyses may process a representative file while documenting other locations.

Optional Checksafe lists in `/stockage` are UTF-8 TSV files with a single column:

| File | Header | Value |
|---|---|---|
| `files.safe.name.tsv` | `name` | Filename (no path), case-insensitive |
| `files.safe.hash.tsv` | `sha1` | 40 hexadecimal characters |

Use only trustworthy external lists. The absence of a filename list triggers hash checks on all files. A header-only name list finds no candidates. Malformed files or no valid hashes mean that no files are marked known. Limits: 32 MiB/list, 500,000 entries and 4096 bytes/line. SHA-256 remains the inventory reference hash. Legacy `files.safe.name` and `files.safe.hash` files are ignored.

## Extension mismatches

Detected types are compared with `config/ext_mime_map.json`. Results use `extension_mismatch` and `expected_format`. Unknown extensions and empty files do not trigger this alert.

`scripts/analyse/vigil_census_query.py` queries the index by MIME type, extension and anomaly. See [Threat hunting](menaces.md).
