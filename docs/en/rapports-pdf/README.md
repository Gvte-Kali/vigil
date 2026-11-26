---
layout: english
title: PDF reports
parent: English
nav_order: 13
translation_of: rapports-pdf/README.md
---

# Read Vigil reports

Analysis modules use the shared `scripts/pdf/vigil_pdf.py` generator based on ReportLab. On a site installation, PDFs are typically stored in `/opt/vigil/rapports/`. Some are also linked to individual cases or runs.

## How to read a report

1. **Cover:** check the organization, logo, operator, context and date.
2. **Scope:** identify the source and operations actually performed.
3. **Statistics:** distinguish examined files, skipped items, errors and detections.
4. **Detailed results:** review paths and checksums when provided.
5. **Conclusion:** “no detections” never proves that content is harmless.

Consolidated reports combine multiple sections with a table of contents. Large inventories have their detail in SQLite/TSV and generally only a summary in the PDF.

## Report types

| Category | `--kind` |
|---|---|
| Files | `images`, `videos`, `audio`, `office`, `archives`, `crypto`, `entropy`, `bigfiles` |
| Inventory | `census`, `formataudit` |
| Antivirus and USB | `clamav`, `usbhid` |
| Audit | `custody` |
| Multi-section report | `multi` |

## Advanced usage

Generate a PDF from previously produced JSON:

```bash
python3 /opt/vigil/scripts/pdf/vigil_pdf.py \
  --kind images --json /path/result.json \
  --user "Operator" --project "Case" --dir /path/reports
```

ClamAV supports `--log` and consolidated reports accept repeated `--section` arguments. See `--help` for `--comment`, `--config-dir`, `--fname-prefix` and others. The Graphite website theme does not style PDF output.
