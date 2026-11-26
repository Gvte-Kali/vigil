---
layout: english
title: High entropy
parent: Actions & analyses
grand_parent: English
nav_order: 19
translation_of: actions/entropie.md
---

# High-entropy files

Identify poorly compressible `application/octet-stream` files using `zstd`, recording their alignment on 512-byte boundaries.

## Run

Select operator and case, mount the source, then launch the entropy module.

Script: `scripts/analyse/vigil_entropy.sh`.

| Option | Behavior |
|---|---|
| `--pdf` / `--no-pdf` | Enable or disable PDF (default enabled) |
| `--copy-to DIR` | Copy matching files to working storage |
| `--min-size N` | Minimum bytes (default `4194304`, 4 MiB) |
| `--threshold N` | Compression ratio threshold in hundredths of a percent (default `9800`, 98%) |

High entropy is an indicator of low compressibility, **not proof of encryption**. Without `zstd`, measurement is unavailable. The unit for `--min-size` differs from the large-files module.

See [analysis](../analysis.md) and [reports](../rapports-pdf/README.md).
