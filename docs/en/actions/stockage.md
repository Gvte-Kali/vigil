---
layout: english
title: Working storage
parent: Actions & analyses
grand_parent: English
nav_order: 26
translation_of: actions/stockage.md
---

# Working storage

Mount a destination **read/write** under `/stockage` for intermediate results, exports or external databases. For an investigation source, use [read-only mounting](montage-lecture-seule.md) instead.

## Procedure

1. Open **Mount working storage** from the legacy home screen.
2. Choose a configured operator, who becomes active.
3. Follow USB triage and select the intended destination.
4. Work with the directory under `/stockage`.
5. Unmount through Vigil before unplugging.

| Script | Function |
|---|---|
| `scripts/stockage/vigil_stockage_mount.sh` | USB triage and RW mounting |
| `scripts/stockage/vigil_stockage_umount.sh` | Unmount working storage |

The storage workflow shares the [USB trust/block lists](../configuration/peripheriques-usb.md) with investigations and produces a triage report. Blocked devices cannot be selected.
