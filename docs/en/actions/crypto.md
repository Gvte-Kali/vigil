---
layout: english
title: Encrypted files
parent: Actions & analyses
grand_parent: English
nav_order: 17
translation_of: actions/crypto.md
---

# Encrypted files

Look for password protection in supported archives, Office documents, PDFs and OpenDocument files using `7za` and `file`.

## Run

Select operator and case in **Analyze a device**, mount the source, then launch the module.

Script: `scripts/analyse/vigil_crypto.sh`.

| Option | Behavior |
|---|---|
| `--pdf` / `--no-pdf` | Enable the PDF report (default) or disable it |
| `--copy-to DIR` | Copy matching files to working storage |

The report includes only files with confirmed protection, plus their paths and available SHA-256 checksums. Encryption is not evidence of malicious concealment. See [analysis](../analysis.md) and [reports](../rapports-pdf/README.md).
