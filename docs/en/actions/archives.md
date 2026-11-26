---
layout: english
title: Archive files
parent: Actions & analyses
grand_parent: English
nav_order: 12
translation_of: actions/archives.md
---

# Archive files

Locate archives, classify their formats and look for password protection when suitable tools are installed.

## Run

In **Analyze a device**, select the operator and case, mount the source, then run the archive module.

Script: `scripts/analyse/vigil_archives.sh`.

| Option | Behavior |
|---|---|
| `--pdf` / `--no-pdf` | Enable the PDF report (default) or disable it |
| `--copy-to DIR` | Copy matching files to a working directory |

## Results and limitations

The PDF contains statistics, matching file paths and available SHA-256 checksums. PDFs are normally stored under `/opt/vigil/rapports/`. Password-protected archives require additional inspection. See [encrypted files](crypto.md) and [PDF reports](../rapports-pdf/README.md).
