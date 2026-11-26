---
layout: english
title: Installation
parent: English
nav_order: 1
translation_of: installation/README.md
---

# Install Vigil

On Parrot or Debian, use a regular operator account with administrator
access and Python 3.11 or newer. The commands below assume `/opt/vigil` is
absent. Use the [reset procedure](reset.md) for an existing installation.

```bash
sudo apt-get update
sudo apt-get install -- git python3
sudo mkdir -- /opt/vigil
sudo chown -- "$(id -u):$(id -g)" /opt/vigil
git clone --branch vigil-2.0 --single-branch https://github.com/Gvte-Kali/vigil.git /opt/vigil
cd /opt/vigil
install -d -m 0700 logs rapports
bash scripts/post-install/post_install_vigil.sh --dry-run
bash scripts/post-install/post_install_vigil.sh &&
  hash -r && command -v vigil vigil-gui vigil-tui &&
  vigil --version && vigil --help && vigil doctor && vigil gui
```

The installer resolves and installs the APT dependencies, records newly
installed packages in `/opt/vigil/data/apt-installed-by-vigil.txt`, and
creates the virtual environment at `/opt/vigil/.venv`. It publishes the
CLI, Qt and Textual launchers, prepares the mount zones, installs the udev
helper and adds scoped AppArmor rules if the FreshClam profile is present.

Use `vigil gui` or `vigil-gui` for Qt. In an interactive terminal,
`vigil`, `vigil tui` and `vigil-tui` open the Textual workspace.
The installed site stores working data in `/opt/vigil/data/state`.
Older user data stays in its previous location. Back up both locations
before migration and keep existing `cases.sqlite` databases separate.

Open **Quick actions** and [initialize the ClamAV signatures](clamav.md)
before the first scan. Use a synthetic device to test the session protection
and its restoration at shutdown.

## Resume after the sudoers check

If installation stops at `/etc/sudoers.d/vigil`, keep the checkout and inspect
the file from an administrator account whose access is independent of that file.

```bash
sudo visudo -c
sudo cat -- /etc/sudoers.d/vigil
```

If it contains only the old Vigil rule, move it out of the sudoers include
directory. If it also contains required rules, have an administrator move
those rules into a separate file and validate it with `visudo` first.

```bash
sudo install -d -m 0700 /root/vigil-sudoers-backup
sudo mv -- /etc/sudoers.d/vigil "/root/vigil-sudoers-backup/vigil-$(date +%Y%m%d-%H%M%S)"
sudo visudo -c
sudo -l
```

From the operator account, rerun the installer.

```bash
cd /opt/vigil && bash scripts/post-install/post_install_vigil.sh &&
  hash -r && command -v vigil vigil-gui vigil-tui &&
  vigil --version && vigil gui
```

## Update an existing installation

Close Vigil and run the following from the operator account.

```bash
cd /opt/vigil
git pull --ff-only
bash scripts/post-install/update-cli.sh
hash -r
command -v vigil vigil-tui
vigil --version
vigil --help
```

The updater revalidates and publishes the launchers and reapplies the
FreshClam access rules. For nonprivileged development on Debian, Arch,
Fedora or openSUSE, inspect the native installer plan with
`python3 scripts/post-install/install_native.py --profile complet --dry-run`.
