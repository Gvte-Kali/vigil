---
layout: english
title: Native testing procedure
parent: Developer reference
grand_parent: English
nav_order: 17
translation_of: development/native-recette.md
---

# Native test procedure for Vigil 2.0

Run as an ordinary user from the `vigil-2.0` branch. Prepare two snapshots: one Debian/Parrot VM and one Arch Linux VM, optionally with Hyprland/Omarchy. Record the commit, OS, kernel, compositor, Python and Qt versions.

## Prepare an isolated workspace

```bash
git switch vigil-2.0
git pull --ff-only
git rev-parse --short HEAD
python3 scripts/post-install/install_native.py --profile complet --dry-run
dev=$(mktemp -d)
python3 scripts/dev/workspace.py --workspace "$dev" setup
python3 scripts/dev/workspace.py --workspace "$dev" doctor
python3 scripts/dev/workspace.py --workspace "$dev" test
```

On Omarchy, omitting `--workspace "$dev"` uses the ordinary `~/.local/share/vigil-dev` location. This workspace keeps a venv, fixtures, SQLite, custody, logs and XDG directories isolated. Development mode blocks mounting, imaging, hotplug protection and external privileged tools.

The native installer reads `/etc/os-release` and offers `minimal`, `forensic` and `complet` profiles. System package changes require explicit `--system-packages`; review the dry run and distribution-specific hooks before using it. UDisks2, mounts and the desktop are separate host settings.

## Nonprivileged GUI/TUI tests

```bash
python3 scripts/dev/workspace.py --workspace "$dev" gui
python3 scripts/dev/workspace.py --workspace "$dev" gui-legacy
python3 scripts/dev/workspace.py --workspace "$dev" tui
```

On X11/XWayland, test `QT_QPA_PLATFORM=xcb`; on Wayland, test `QT_QPA_PLATFORM=wayland` where installed. Under Hyprland, check dialog focus and window transitions.

Test operator selection, bilingual FR/EN, case creation and activation, legacy import, Vigil 2.0 export/reimport, metadata, evidence SHA-256, audit export and preference persistence. The fixture `disk.raw` is a synthetic MBR image with one partition, **not** a mountable filesystem.

Confirm that blocked privileged actions in development mode do not open admin terminals. Compare results with `tests.txt`.

## Privileged tests in a dedicated VM

Use two disposable, distinguishable virtual block devices, snapshots and explicit consent. Verify source RO, target RW, mount identity, census, capacity checks and the refusal to target the source. Acquire RAW and clone using the same defined hash scope. Simulate cancellation, concurrent use, disconnection and shutdown. Confirm actual device and service state is restored, not just a successful command exit.

Never apply these tests to real evidence or an ordinary personal workstation. See [session recovery](session-recovery.md) and [security](permissions-audit.md).
