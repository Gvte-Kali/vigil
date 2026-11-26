---
layout: english
title: ClamAV signatures
parent: English
nav_order: 4
translation_of: configuration/clamav.md
---

# Update ClamAV signatures

FreshClam and ClamScan use the same Vigil signature directory. For an
installation in `/opt/vigil`, it is `/opt/vigil/data/state/clamav`.
Open **Quick actions** and update the signatures before the first scan.

- **Online:** run the signature update. Check the reported database directory
  and daily signature version.
- **Offline:** prepare signed `main.cvd` and `daily.cvd` files on a connected
  computer. Add `bytecode.cvd` if available. Run the USB update and follow
  device triage, confirm the verified import, and check the installed versions
  and unmount result.

If FreshClam cannot open the Vigil configuration, check whether an update
attempt created it and look for AppArmor denials.

```bash
sudo journalctl -k -b --no-pager | grep -Ei 'apparmor.*DENIED.*freshclam' | tail -15
namei -l /opt/vigil/data/state/clamav/vigil-freshclam.conf
```

On an existing site, run `bash scripts/post-install/update-cli.sh` from
`/opt/vigil` as the operator to reapply the scoped AppArmor rules and update
the launchers. Then retry the update in Vigil.
