---
layout: english
title: Linux portability
parent: Developer reference
grand_parent: English
nav_order: 16
translation_of: development/linux-portability.md
---

# Vigil 2.0 on Linux

The CLI/Core uses **Python 3.11+** on Linux, SQLite and a user-owned virtual environment. Basic operation does not require Tkinter, Qt or a graphical session.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/vigil doctor
.venv/bin/vigil modules list
```

## Target distributions

Debian, Kali and Parrot, Fedora, Arch and openSUSE are portability targets; Alpine and alternative architectures require additional dependency review. The Debian-family installation has the most concrete operator testing. A successful Python install does **not** certify privileged mounting.

`install_native.py` detects `/etc/os-release` and prepares a minimal, forensic or complete profile. Without `--system-packages`, it should leave system package installation to the operator. Always inspect `--dry-run` before accepting changes.

## Native checks

Use a private venv, XDG data/state paths and synthetic fixture media. Confirm `vigil doctor`, JSON command output, Qt (when selected), Textual in a terminal and the installed launchers. Test mount namespace, USB triage, acquisition, session recovery and SELinux/AppArmor separately on disposable VMs.

Never treat absent hardware or unavailable optional dependencies as passing tests. See [native test recipe](native-recette.md), [compatibility](../compatibility.md) and [permissions](permissions-audit.md).
