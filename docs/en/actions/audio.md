---
layout: english
title: Audio files
parent: Actions & analyses
grand_parent: English
nav_order: 13
translation_of: actions/audio.md
---

# Audio files

Identify audio files and extract their duration and bitrate using `ffprobe`.

## Run

In **Analyze a device**, select an operator and case, mount the source, and launch the audio module.

Script: `scripts/analyse/vigil_audio.sh`.

| Option | Behavior |
|---|---|
| `--pdf` / `--no-pdf` | Enable the PDF report (default) or disable it |
| `--copy-to DIR` | Copy matching files into working storage |

The PDF lists statistics, paths, metadata and SHA-256 values where available, under `/opt/vigil/rapports/`. Duration and bitrate help classify recordings but do not establish origin.

See [analysis workflow](../analysis.md) and [reports](../rapports-pdf/README.md).
