---
layout: english
title: Large files
parent: Actions & analyses
grand_parent: English
nav_order: 29
translation_of: actions/volumineux.md
---

# Large files

Locate non-video files of at least 512 MiB and check whether they contain only zero bytes.

Select the operator and project, mount the source and run the module.

Script: `scripts/analyse/vigil_bigfiles.sh`.

| Option | Behavior |
|---|---|
| `--pdf` / `--no-pdf` | PDF enabled by default |
| `--copy-to DIR` | Copy matching files to working storage |
| `--min-size N` | Minimum size **in MiB**, default `512` |

Reports include paths and SHA-256 where available, normally under `/opt/vigil/rapports/`. A file filled with zero bytes is not necessarily sparse: logical size and physical allocation are different concepts.

See [analysis](../analysis.md) and [reports](../rapports-pdf/README.md).
