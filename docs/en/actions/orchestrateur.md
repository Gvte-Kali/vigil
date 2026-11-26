---
layout: english
title: Scan orchestrator
parent: Actions & analyses
grand_parent: English
nav_order: 24
translation_of: actions/orchestrateur.md
---

# Scan orchestrator

`scripts/vigil_scan_all.sh` runs a predefined chain on media **already mounted** under `/investigation` and generates one consolidated PDF.

## Before running

Select operator and project and mount the source.

```bash
bash /opt/vigil/scripts/vigil_scan_all.sh
```

The orchestrator does not reject missing project context itself, but dependent analyses require it and will fail without it.

## Execution order

Census → ClamAV → images → video → audio → office files → archives → encrypted files → entropy → large files.

Analyses are independent: failure in one does not automatically stop subsequent modules. Review the final report for partial failures.

| Option | Result |
|---|---|
| `--pdf` | Generate the consolidated PDF (default) |
| `--no-pdf` | Do not generate it |

Intermediate data feeds the common PDF generator; individual PDFs are suppressed. The final PDF is created in `/opt/vigil/rapports/` and copied into the project when possible. The GUI's multi-scan can select a subset of tools.

See [Analyze media](../analysis.md) and [PDF reports](../rapports-pdf/README.md).
