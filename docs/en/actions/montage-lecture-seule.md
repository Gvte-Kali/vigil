---
layout: english
title: Read-only mounting
parent: Actions & analyses
grand_parent: English
nav_order: 23
translation_of: actions/montage-lecture-seule.md
---

# Read-only mounting

Mount a source for examination under `/investigation` with `scripts/analyse/vigil_usb_mount.sh`.

## Procedure

1. Choose operator and project in the analysis interface, then select **Mount**.
2. Disconnect sources under examination, confirm the initial USB state and leave the working keyboard connected.
3. Connect the source and wait for USB triage (approximately 10 seconds).
4. Select device type and the displayed disk or partition.
5. Verify the mounting summary before analysis.

Within the selection menu, `r` refreshes and `q` quits.

## Software protections

For block devices, Vigil requests `blockdev --setro` and mounts with `ro,noexec,nosuid,nodev,noatime`. Unmountable partitions are skipped. A tree checksum may be recorded for comparison at unmount.

Triage blocks unauthorized newly connected HID keyboards by unbinding their `usbhid` driver. The trusted and blocked device lists are documented under [USB devices](../configuration/peripheriques-usb.md). Triage creates a PDF or a section in the consolidated threat-hunt report.

## Media

- USB drives and disks: disk or partition selection.
- CDs/DVDs: read-only mounting.
- MTP/PTP phones: accessed through MTP tooling; block-device protections do not apply.

These are software protections, not a substitute for a physical write blocker when the investigation protocol requires one.

Finish with [Unmounting](demontage.md).
