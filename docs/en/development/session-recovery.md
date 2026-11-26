---
layout: english
title: Session supervision and recovery
parent: Developer reference
grand_parent: English
nav_order: 23
translation_of: development/session-recovery.md
---

# Supervision, restoration and external viewing

## Architecture and diagnostic

Qt is started through a supervised launcher. Earlier direct execution via `python -m vigil.desktop` or old wrappers could bypass that supervisor. A separate caretaker survives a GUI window's exit to finish session cleanup and produce a report. A graphical terminal is a presentation layer, not a prerequisite for recovery.

Operation tracking observes immediate children, PIDs and process start times, but cannot always identify arbitrary descendants or confirm a terminal window was displayed after emulator delegation.

## Snapshots and mutation journal

- Before changes, record relevant mounts/options, block identity and modes, observed UDisks state and managed policy-file fingerprints.
- Each session has a private identifier, operator/case context where available, boot identity and persistent state under `data/state/sessions`.
- A privileged root journal under `/run/vigil-hotplug` records mutations attributed to Vigil for the current boot.
- Recovery operates only on its own journal, checks device identity and observed state, waits appropriately for udev and preserves failures for later review.
- Do not restore an unrelated administrator change, previous mount or service state blindly from a snapshot.

## Exit scenarios

| Situation | Expected behavior | Limit |
|---|---|---|
| Normal Qt close | Confirm no active mounts/operations and report final checks | May block normal close while busy |
| Qt fatal error or signal | Supervisor records code and continues cleanup | Detailed Qt traceback may be stderr only |
| `SIGKILL` of Qt | Independent caretaker reports monitored changes | Untracked descendants may be missed |
| Terminal unavailable | Recovery proceeds and leaves report on disk | No graphical terminal is guaranteed |
| Login session ends, reboot or power loss | Pending state reviewed on next launch | Cannot blindly replay old device names |
| Another Vigil session active | Delay restoration until safe | Never force another session's cleanup |
| Media missing/busy | Log a warning/conflict and defer | Do not force unmount or write |

## Explorer and external applications

Opening a file in its OS-default application is an optional unprivileged graphical operation. Select once to preview metadata/HEX/ASCII; double-click or context action may open the file, with protections against direct execution of scripts and binaries. Resolve restored evidence copies using trusted paths and do not rewrite originals.

## Testing and rollback

Use synthetic mounts and isolated VMs to simulate normal close, crashes, missing terminals, active acquisition, changed device identity, stale state and concurrent sessions. Confirm actual system state rather than relying solely on process exit codes. See [Device Manager](device-manager.md).
