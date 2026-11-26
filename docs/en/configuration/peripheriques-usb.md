---
layout: english
title: USB devices
parent: Settings and cases
grand_parent: English
nav_order: 13
translation_of: configuration/peripheriques-usb.md
---

# USB devices

Open **USB devices** in the configuration area to inspect connected hardware and manage lists applied during triage.

## Manage lists

1. Identify a device using vendor, product, `VID:PID` and available serial number.
2. Choose **Whitelist (trusted)** or **Blacklist (suspicious)**.
3. Review the entry and save.

Tables also allow manual addition and removal.

| List | File | Effect during triage |
|---|---|---|
| Trust | `data/usb/whitelist.txt` | Exempts a device from new-HID-keyboard blocking |
| Block | `data/usb/blacklist.txt` | Disauthorizes the device at kernel level, even for non-HID media |

## Keep your working keyboard available

Keep the keyboard connected when the baseline is recorded. If it must be unplugged and reconnected, add it to the trust list first. Unauthorized newly connected HID keyboards are blocked by default.

A USB identifier is a filtering criterion, not proof of physical device identity. See [Read-only mounting](../actions/montage-lecture-seule.md).
