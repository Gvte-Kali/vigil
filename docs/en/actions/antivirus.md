---
layout: english
title: ClamAV antivirus
parent: Actions & analyses
grand_parent: English
nav_order: 11
translation_of: actions/antivirus.md
---

# ClamAV antivirus

The script `scripts/clamav/vigil_clamav_scan.sh` scans directories mounted under `/investigation`. It can operate without a case and therefore does not add an event to a case's chain of custody. For a complete standalone workflow, use [Threat hunting](menaces.md).

## Run the scan

```bash
bash /opt/vigil/scripts/clamav/vigil_clamav_scan.sh
```

Select the mounted directories, then review the consolidated report. Progress is an estimate, particularly with archives.

## Options

| Option | Behavior |
|---|---|
| `--pdf` / `--no-pdf` | Generate a PDF (default) or disable it |
| `--log` / `--no-log` | Save the scanner log (disabled by default) |
| `--all --yes` | Scan every mounted directory without confirmation |
| `--user NAME` | Set the operator |
| `--comment TEXT` | Add a comment in noninteractive mode |
| `--archives` / `--no-archives` | Scan archive contents (default on) |
| `--size-unlimited` / `--size-limit` | Configure the practical 2047 MiB ceiling or a lower 512 MiB limit |
| `--alert-encrypted` / `--no-alert-encrypted` | Report encrypted archives (default on) |

## Interpret results

“Unlimited” is not literally unlimited: ClamAV can skip oversized or encrypted content. `Heuristics.Encrypted.*` flags uninspected encrypted content, not a confirmed infection. No alert does not guarantee safety.

The full `scripts/clamav/vigil_clamav_full_scan.sh` sequence mounts, scans and unmounts. Check [signature updates](../clamav.md) before scanning.
