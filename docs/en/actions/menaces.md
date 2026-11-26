---
layout: english
title: Threat hunting
parent: Actions & analyses
grand_parent: English
nav_order: 22
translation_of: actions/menaces.md
---

# Threat hunting

From the legacy home screen, **Threat hunting** starts `scripts/clamav/vigil_malware_hunt.sh` in Konsole. This is a standalone process with an operator and its own journal, **without creating a project**.

## Procedure

1. Confirm the action and select the operator, or supply `--user NAME`.
2. Optionally enter a report name.
3. Follow USB triage and read-only mounting.
4. Let census, format audit, ClamAV and unmounting complete.
5. Read the consolidated PDF; decide whether to export intermediate evidence.

## Stages

| Stage | Output |
|---|---|
| Triage and mounting | Newly attached media, HID blocks and RO status |
| Census | SQLite/TSV inventory, SHA-256, duplicates and misleading extensions |
| Format audit | Suspicious extension mismatches and high-entropy binaries |
| ClamAV | Detections and scan limitations, including archive contents |
| Unmount | Integrity comparison and release of the source |

The format audit uses `config/forensic_signatures.json` and, where available, `binwalk`. It flags `application/octet-stream` samples with Shannon entropy at or above 7.5 bits/byte. High entropy may also result from compression or encryption.

## Report and data retention

The consolidated PDF includes USB triage, ClamAV, audit, census and a chronological log under `/opt/vigil/rapports/`. Temporary results and `chain_of_custody.json` are kept in `$VIGIL_BASE/hunt/`.

**Important:** `hunt/` is purged at the start and end of a hunt. Export results before closing. If accepted export fails or is cancelled, final cleanup is withheld so you can recover data. If the sole support is blocked by triage, a triage-only report may still be produced.

See [Antivirus](antivirus.md) and [Census](recensement.md).
