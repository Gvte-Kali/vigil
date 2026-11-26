---
layout: english
title: Device Manager and mounts
parent: Developer reference
grand_parent: English
nav_order: 15
translation_of: development/device-manager.md
---

# Device management in Vigil Core

Vigil's Device Manager uses Linux block inventory and kernel mount data. GUI, TUI and CLI operations should share the same selection, identity checks and protection rules.

## Commands

| Command | Behavior |
|---|---|
| `vigil devices list` | JSON block inventory |
| `vigil devices triage` | Interactive selection; `--device /dev/sdb1` for direct validation |
| `vigil devices mount` | Mounts into `/investigation` by default |
| `vigil devices mount --zone stockage --device /dev/sdb1 --confirm-write` | Controlled RW working mount |
| `vigil devices unmount --target /investigation/...` | Verified unmount |
| `vigil devices status` | Observed mount status |
| `vigil devices verify` | Identity/protection verification |

The commands use identical checks in interactive and scriptable modes.

## Protection and concurrency

Validate selection by stable device identity, expected zone, mounted subresources and USB blacklist. Hold a shared lease/lock across conflicting physical operations. No source may be silently remounted writable; destinations require explicit confirmation. Block unmounts while a child mount or operation is active.

## GUI and TUI adapters

The interfaces construct operation contexts and pass them to the shared device manager. The final state is verified against the kernel, not inferred from a zero exit status alone. RAW imaging and cloning that use block devices directly do not need a preliminary filesystem mount.

See [read-only mounting](../actions/montage-lecture-seule.md), [security audit](permissions-audit.md) and [session recovery](session-recovery.md).
