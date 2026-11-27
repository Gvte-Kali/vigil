---
layout: english
title: Installation
parent: English
nav_order: 1
translation_of: installation/README.md
---

# Install Vigil

This guide covers the **`main`** branch with Qt as the primary user workflow. Privileged device operations require system administration; test a site installation in a snapshot-equipped VM first.

## Complete installation (Debian / Parrot)

Requirements: ordinary account with sudo, Python 3.11+, Internet access and sufficient disk space. Back up cases and test in a VM first. Close operations and disconnect media after verified restoration.

```bash
sudo apt-get update
sudo apt-get install -- git python3
sudo mkdir -- /opt/vigil
sudo chown -- "$(id -u):$(id -g)" /opt/vigil
git clone --branch main --single-branch https://github.com/Gvte-Kali/vigil.git /opt/vigil
cd /opt/vigil
install -d -m 0700 logs rapports
bash scripts/post-install/post_install_vigil.sh --skip-apt-update
```

The installer configures dependencies, Python, mount zones, udev, FreshClam and launchers. The log path is displayed. To inspect the plan without installing, use `--dry-run` instead of `--skip-apt-update`.

```bash
hash -r
vigil doctor
vigil gui
```

## Desktop shortcut

The post-install script automatically creates `Vigil.desktop` in the operator’s XDG desktop directory, with the official logo and direct GUI launch. No shortcut is created if the XDG desktop is missing or invalid. Existing third-party shortcuts are retained.

To create or refresh the shortcut on an existing installation without reinstalling:

```bash
cd /opt/vigil
source scripts/lib/vigil-launchers.sh
vigil_install_desktop_shortcut
```

Both GUI and TUI open a separate shutdown report terminal on normal exit; verify USB restoration and remaining mounts before disconnecting media.

## Uninstall

Close Vigil, back up cases and unmount media. Review the plan:

```bash
cd /opt/vigil
bash scripts/post-install/uninstall.sh --dry-run
bash scripts/post-install/uninstall.sh --keep-data
```

`--purge` permanently deletes data after confirmation. Dependencies are retained by default; `--purge-dependencies` is experimental. See [removal and rollback](reset.md). The uninstaller still requires VM validation.

## Launch Vigil

- `vigil gui` / `vigil-gui`: Qt workspace, primary documented workflow.
- `vigil tui` / `vigil-tui`: Textual terminal workspace, interactively tested on Parrot OS; full forensic validation is ongoing.
- `vigil`: CLI help.
- `vigil doctor`: dependency diagnostics.

Site installations usually store state at `/opt/vigil/data/state`. User development may use XDG locations. **Never merge two `cases.sqlite` databases blindly.**

## Update an existing site

Close Vigil and active operations, unmount media and back up data:

```bash
cd /opt/vigil
git pull --ff-only
bash scripts/post-install/update-cli.sh
hash -r
vigil doctor
```

Investigate launcher conflicts; do not overwrite unrelated applications.

## Installer failure and rollback

If the installer stops at `/etc/sudoers.d/vigil`, do not delete that rule blindly. Use an independent administrator account:

```bash
sudo visudo -c
sudo cat -- /etc/sudoers.d/vigil
```

Have the administrator preserve any required privileges and revalidate the complete sudoers configuration with `visudo -c`. See [backed-up removal](reset.md) for rollback.

## Next steps

[Your first investigation](getting-started.md) · [ClamAV](clamav.md) · [Compatibility](compatibility.md).

## Language selection

At launch, the installer and uninstaller prompt for **Français** or **English** for Vigil's progress messages, confirmations and errors. If there is no interactive terminal, they use `VIGIL_LANG` or the system locale. Raw APT and other third-party diagnostics are preserved unchanged. The GUI and TUI each have their own language selection; the language of launched mounting and analysis operations follows the currently selected interface language.
