---
layout: english
title: Installation
parent: English
nav_order: 1
translation_of: installation/README.md
---

# Install Vigil

This guide covers the **`main`** branch with Qt as the primary user workflow. Privileged device operations require system administration; test a site installation in a snapshot-equipped VM first.

## Choose a mode

| Mode | For | System impact |
|---|---|---|
| **User development** | Try the GUI, cases and test files | Local venv and files, no privileged mount configuration |
| **Site installation** | Dedicated Debian/Parrot forensic workstation | APT, `/opt/vigil`, launchers, udev and controlled protection |
| **Other Linux** | Developers and testers | `install_native.py --dry-run`; hardware workflows remain to be verified |

## Requirements

Debian/Parrot or a derivative for the documented site installer, an ordinary account with `sudo`, Git, Python **3.11+**, sufficient disk space and backups of any existing case data.

## Try Qt without a privileged post-install

```bash
git clone --branch main https://github.com/Gvte-Kali/vigil.git
cd vigil
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[desktop]'
.venv/bin/vigil doctor
.venv/bin/vigil-gui
```

This does **not** configure udev rules, system protections or privileged mounts. Hardware functions may be unavailable. See the [native test guide](development/native-recette.md) for synthetic fixtures.

## Site installation on Debian/Parrot

**Warning: the following changes the host.** Use a disposable VM and review the plan before proceeding.

```bash
sudo apt-get update
sudo apt-get install -- git python3
sudo mkdir -- /opt/vigil
sudo chown -- "$(id -u):$(id -g)" /opt/vigil
git clone --branch main --single-branch https://github.com/Gvte-Kali/vigil.git /opt/vigil
cd /opt/vigil
install -d -m 0700 logs rapports
bash scripts/post-install/post_install_vigil.sh --dry-run
```

After reviewing dependencies, system changes, backups and any legacy sudoers rule:

```bash
bash scripts/post-install/post_install_vigil.sh
hash -r
vigil --version
vigil doctor
vigil gui
```

The installer prepares `/opt/vigil/.venv`, `/investigation`, `/stockage`, launchers, the udev helper and appropriate FreshClam/AppArmor integration. Newly added APT packages are recorded in `/opt/vigil/data/apt-installed-by-vigil.txt`.

## Launch Vigil

- `vigil gui` / `vigil-gui`: Qt workspace, primary documented workflow.
- `vigil` / `vigil tui` / `vigil-tui`: experimental TUI launchers; the TUI is **currently non-functional**. Use `vigil gui` for investigations.
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
