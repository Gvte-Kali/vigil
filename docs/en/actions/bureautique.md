---
layout: english
title: Office documents
parent: Actions & analyses
grand_parent: English
nav_order: 14
translation_of: actions/bureautique.md
---

# Office documents

Identify office documents by their content type as detected by `file`, not by extension alone.

## Run

In **Analyze a device**, select operator and case, mount the source, and launch the office-document analysis.

Script: `scripts/analyse/vigil_office.sh`.

| Option | Behavior |
|---|---|
| `--pdf` / `--no-pdf` | Enable the PDF report (default) or disable it |
| `--copy-to DIR` | Copy matching files to working storage |

Reports include statistics, source paths and available SHA-256 checksums. Check [encrypted files](crypto.md) separately for password protection. See [PDF reports](../rapports-pdf/README.md).
