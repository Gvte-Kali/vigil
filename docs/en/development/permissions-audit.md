---
layout: english
title: Permissions and privilege audit
parent: Developer reference
grand_parent: English
nav_order: 18
translation_of: development/permissions-audit.md
---

# Permissions and privilege audit

This engineering review originally described the code near commit `886ce03`. Reproduce the inventory rather than assuming it still matches current HEAD.

```bash
git ls-files '*.sh' '*.py' scripts/Vigil-CLI/vigil scripts/post-install/vigil-qt scripts/privileged/vigil-mount
git grep -nE '\bsudo\b|\$EUID|id -u|os\.geteuid' -- '*.sh' '*.py' scripts/privileged/vigil-mount
```

A mention in documentation or a help string is not necessarily an executed privilege escalation.

## Privilege boundaries

| Area | Policy |
|---|---|
| GUI, TUI and CLI | Run under an ordinary operator account |
| Read-only evidence inspection | Read existing RO mounts and verified local copies |
| Block operations | Use a narrowly scoped privileged helper / controlled sudo |
| Working storage | Write only to an explicitly chosen destination |
| Case databases, logs and reports | Keep out of `/investigation` and protect ownership |
| Module execution | Validate manifests and capabilities before invoking scripts |

Do not give a generalized passwordless sudo rule, run an entire GUI as root, or alter unrelated system services to work around an installation issue.

## Mount zones

`/investigation` is for RO sources; `/stockage` is for validated RW destinations. Inspect device identity before and after each operation, prevent source/destination confusion, and keep audit records of attributed mutations.

## Validation

Review effective permissions, script ownership, symbolic links, protected destinations and mount namespace behavior. Test as an ordinary operator, then in isolated VMs with controlled removable media. Document failure paths and restitution reports. See [Device Manager](device-manager.md) and [session recovery](session-recovery.md).
