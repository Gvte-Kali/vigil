---
layout: english
title: Reset the installation
parent: English
nav_order: 2
translation_of: installation/desinstallation.md
---

# Reset Vigil on Parrot or Debian

Close Vigil and its operation terminals. Unmount the media from Vigil and
disconnect test devices once restoration is confirmed. The following commands
keep a backup of the site, case files, evidence, logs and settings. Back up
any case directories stored outside `/opt/vigil` separately.

## Remove the site

Run the block in Bash from the operator account.

```bash
(
  set -euo pipefail
  cd "$HOME"
  sudo -v
  mounts=$(findmnt -rn -o TARGET)
  if grep -Eq '^/(investigation|stockage|opt/vigil)(/|$)' <<< "$mounts"; then
    echo 'A Vigil mount zone or installation directory is still mounted.' >&2
    exit 1
  fi
  backup=$(mktemp -d "$HOME/vigil-sauvegarde.XXXXXX")
  printf 'Sauvegarde %s\n' "$backup"
  . /opt/vigil/scripts/lib/vigil-launchers.sh

  if sudo test -x /usr/local/sbin/vigil-hotplug; then
    sudo /usr/local/sbin/vigil-hotplug recover | python3 -c '
import json, sys
r = json.load(sys.stdin)
print(json.dumps(r, indent=2))
sys.exit(not (r["status"] == "complete" and
              all(d["state"] in {"restored", "absent"} for d in r["devices"])))
'
  fi

  for directory in /usr/local/bin /usr/bin "$HOME/.local/bin"; do
    for name in vigil vigil-gui vigil-tui vigil2 vigil2-gui; do
      file="$directory/$name"
      if vigil_owned_launcher "$file" /opt/vigil; then
        if [[ $directory == "$HOME/.local/bin" ]]; then
          rm -- "$file"
        else
          sudo rm -- "$file"
        fi
      fi
    done
  done
  desktop=/usr/share/applications/vigil.desktop
  if vigil_managed_desktop "$desktop" /opt/vigil /usr/local/bin; then
    sudo rm -- "$desktop"
  fi
  sudo rm -f -- /etc/udev/rules.d/99-vigil-hotplug.rules
  sudo udevadm control --reload-rules
  sudo rm -f -- /usr/local/sbin/vigil-hotplug
  if sudo test -d /run/vigil-hotplug; then
    sudo mv -T -- /run/vigil-hotplug "$backup/hotplug-runtime"
  fi
  if sudo cmp -s /usr/local/sbin/vigil-mount /opt/vigil/scripts/privileged/vigil-mount; then
    sudo rm -- /usr/local/sbin/vigil-mount
    if sudo test -d /run/vigil-mount; then
      sudo mv -T -- /run/vigil-mount "$backup/mount-runtime"
    fi
  fi
  icon=/usr/share/icons/hicolor/scalable/apps/vigil.svg
  if sudo cmp -s "$icon" /opt/vigil/data/icons/vigil.svg; then
    sudo rm -- "$icon"
  fi
  profile=/etc/apparmor.d/usr.bin.freshclam
  local_profile=/etc/apparmor.d/local/usr.bin.freshclam
  if sudo test -f "$local_profile"; then
    sudo cp -a -- "$local_profile" "$backup/freshclam-local"
    sudo sed -i '\|^owner /opt/vigil/data/state/clamav/ rw,$|d;\|^owner /opt/vigil/data/state/clamav/\*\* rwk,$|d' "$local_profile"
    if [[ -f $profile && $(cat /sys/module/apparmor/parameters/enabled 2>/dev/null || :) == Y ]]; then
      sudo apparmor_parser -r "$profile"
    fi
  fi
  # rmdir preserves any nonempty directory.
  for zone in /investigation /stockage; do
    if [[ -d $zone && ! -L $zone ]]; then sudo rmdir -- "$zone"; fi
  done
  sudo mv -T -- /opt/vigil "$backup/site"
)
hash -r
```

For a legacy installation, restore the previous UDisks2 settings from
backup. Unmask the service only if Vigil originally masked it, then restore
its previous service state. Remove old Dolphin bookmarks and revert any
RDP settings that were added for Vigil. If the old sudoers rule is still
present, follow [the administrator procedure](installation.md#resume-after-the-sudoers-check).

## Review and purge APT packages

Set the backup path to the one printed above. Review the list and remove
packages used by other software. Preview the proposed removals.

```bash
backup="$HOME/vigil-sauvegarde.REMPLACER"
cp -- "$backup/site/data/apt-installed-by-vigil.txt" "$backup/apt-a-purger.txt"
"${EDITOR:-nano}" "$backup/apt-a-purger.txt"
mapfile -t vigil_packages < <(awk '/^[a-z0-9][a-z0-9+.-]*(:[a-z0-9-]+)?$/ {print}' "$backup/apt-a-purger.txt")
if (("${#vigil_packages[@]}")); then
  sudo apt-get -s purge -- "${vigil_packages[@]}"
fi
```

For an older installation without a package inventory, inspect the APT
history and put the package names from the relevant `Install:` entry in
`$backup/apt-a-purger.txt`, one per line. Packages in `Upgrade:` were already
installed. Keep packages whose origin is uncertain.

```bash
sudo zcat -f /var/log/apt/history.log* | less
```

After reviewing the simulation, run the purge if APT proposes only the
expected removals. Keep Git, sudo and the system Python for reinstallation.

```bash
if (("${#vigil_packages[@]}")); then
  sudo apt-get purge -- "${vigil_packages[@]}"
fi
sudo apt-get -s autoremove --purge
```

Check `type -a vigil vigil-gui vigil-tui` for independent installations.
Unset site overrides such as `VIGIL_STATE_DIR` for a fresh-profile test.
Follow [the installation guide](installation.md) before restoring data.
