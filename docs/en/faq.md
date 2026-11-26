---
layout: english
title: FAQ and troubleshooting
parent: English
nav_order: 6
translation_of: faq.md
---

# FAQ and troubleshooting

## Are investigation sources fully protected?

Vigil uses **software** read-only protections, including block-device controls where applicable and read-only mount flags. They are not a substitute for a hardware write blocker. MTP/PTP phones do not use identical block-device protections. Check the actual operation report.

## Why keep /investigation separate from /stockage?

`/investigation` is for examining sources without writing to them. `/stockage` is for writable work files and destinations. Never confuse an acquisition destination with its source.

## Does SHA-256 prove authenticity?

No. It compares **content integrity**; it does not authenticate the origin or operator on its own.

## Does a clean ClamAV scan mean the source is safe?

No. Results depend on the engine, signature age, files actually read, size limits, encrypted archives and errors. See [ClamAV](clamav.md).

## Is the TUI as complete as the GUI?

No. The TUI is experimental and **currently non-functional**. Use the Qt GUI for investigations. See [compatibility](compatibility.md).

## Vigil cannot find my USB drive

Check `lsblk`, USB triage and possible HID/device blocks. Do not bypass udev protections to force mounting. See [USB devices](configuration/peripheriques-usb.md).

## Mounting or shutdown failed

Do not unplug media during an operation. Record the device identity, mounts, session report and error. See the [unmount guide](actions/demontage.md). Avoid blindly restarting acquisition tools.

## Where are the reports and evidence?

In a site installation, reports are generally under `/opt/vigil/rapports` and case data under its designated custody directory. Development installations may use XDG paths. See [reports](rapports-pdf/README.md) and [cases](configuration/projets.md).

## Can I install Vigil on Fedora or Omarchy?

User-space development testing is possible, but privileged workflows and the site installer are primarily documented for Debian-based Linux. Start with the [non-intrusive native test guide](development/native-recette.md).

## How do I report a bug?

[Open an issue](https://github.com/Gvte-Kali/vigil/issues) with the OS, commit, steps and logs redacted to remove sensitive data.
