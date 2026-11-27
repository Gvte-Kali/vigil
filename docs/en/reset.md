---
layout: english
title: Reset the installation
parent: English
nav_order: 2
translation_of: installation/desinstallation.md
---

# Uninstall Vigil on Debian or Parrot

Close Vigil and operation terminals, unmount volumes and disconnect media after verified restoration. Back up external case directories separately. Run as the operator.

```bash
cd /opt/vigil
bash scripts/post-install/uninstall.sh --dry-run
bash scripts/post-install/uninstall.sh --keep-data
```

Keep-data is the default and creates an archive in ~/vigil-uninstall.*. For permanent site data deletion:

```bash
bash scripts/post-install/uninstall.sh --dry-run --purge --purge-dependencies
bash scripts/post-install/uninstall.sh --purge --purge-dependencies
```

Review the APT simulation before confirming UNINSTALL and PURGE. Dependency removal is optional and limited to the APT inventory; retain shared packages. No automatic autoremove. The --legacy option includes historical site archives. Nonempty mount zones are retained.

The ~/vigil-uninstall.*.log journal survives purge. Review reported residuals. Active sessions block removal; close Vigil and retry. VIGIL_LANG=fr or en overrides the locale.

For legacy installations, restore UDisks2 only from a known previous state; review old sudoers rules with visudo, Dolphin bookmarks and RDP settings. Never reset services blindly. Without a reliable APT inventory, retain packages.

Return to your home directory, run hash -r and check type -a vigil vigil-gui vigil-tui. Follow the [installation guide](installation.md) to reinstall.
