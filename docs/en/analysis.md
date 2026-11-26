---
layout: english
title: Analyze a device
parent: English
nav_order: 3
translation_of: actions/analyse.md
---

# Analyze a device

In the Qt interface, select an operator and open a case. Under **Current case**,
start the device mounting workflow. Verify the device identity and select the
source. Vigil mounts it read-only under `/investigation`. The read/write mount point for working storage is `/stockage`.

Use the case tabs to browse files, register evidence, run analyses and review
reports. For a source copy, compare its SHA-256 digest with the recorded digest.
When finished, unmount in Vigil and verify the result before disconnecting
the device. Keep exports outside `/investigation`.

For a standalone antivirus scan, use **Quick actions**. Check the local
[ClamAV signatures](clamav.md) before running the scan.
