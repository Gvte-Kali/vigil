---
layout: english
title: Video files
parent: Actions & analyses
grand_parent: English
nav_order: 27
translation_of: actions/videos.md
---

# Video files

Identify videos and extract duration and resolution using `ffprobe`.

Choose an operator and project in **Analyze a device**, mount the source and launch the video module.

Script: `scripts/analyse/vigil_videos.sh`.

| Option | Behavior |
|---|---|
| `--pdf` / `--no-pdf` | PDF enabled by default |
| `--copy-to DIR` | Copy matching files to working storage |

The report includes matching paths, types, available characteristics and SHA-256 checksums, normally under `/opt/vigil/rapports/`. See [reports](../rapports-pdf/README.md).
