---
layout: english
title: Forensic imaging
parent: Actions & analyses
grand_parent: English
nav_order: 16
translation_of: actions/copie-forensique.md
---

# Forensic imaging

Create a disk image with `scripts/imager/vigil_disk_imager.sh` from the legacy **Make a forensic disk copy** action.

## Procedure

1. Select the source from the proposed external devices.
2. Confirm identity and read-only protection.
3. Choose the output format, filename and destination.
4. Confirm acquisition and wait for its summary.
5. Preserve the image, checksum files and acquisition log.

A destination may be external media or a local directory. The legacy script checks free local space while reserving 20% of the system disk.

## Formats

| Format | Tool | Purpose |
|---|---|---|
| RAW | `dc3dd` | Uncompressed image (`.raw`, `.dd`, `.img`) |
| E01 | `ewfacquire` | Segmented metadata-rich image, optionally compressed |
| AFF | AFFlib tools | Forensic image container |

Format dependencies and source RO state must be verified before running the relevant mode. SHA-256 can compare generated output content; preserve the log as well. **Support depends on the selected legacy/2.0 workflow and installed tools.**

See [Cloning](clonage.md) to write directly to another disk.
