---
layout: english
title: Unmount devices
parent: Actions & analyses
grand_parent: English
nav_order: 18
translation_of: actions/demontage.md
---

# Unmount investigation media

In the legacy analysis workspace, **Unmount** runs `scripts/analyse/vigil_usb_umount.sh` in Konsole. It handles **all active mounts** under `/investigation`.

## Procedure

1. Recompute and compare the directory-tree checksum if an initial value exists.
2. Report integrity differences; the unmount process continues and records the mismatch.
3. Unmount each partition.
4. Release the software block read-only setting with `blockdev --setrw`.
5. Remove empty mount points and display the summary.

Do not unplug media before checking the final report. Without an initial checksum, no comparison is possible and a warning is shown.

Unmounting can work without a current project; case or hunt logs are updated when available. Once the block RO setting is released, that particular software protection is no longer active.

See [Read-only mounting](montage-lecture-seule.md).
