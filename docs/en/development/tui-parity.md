---
layout: english
title: Textual feature parity
parent: Developer reference
grand_parent: English
nav_order: 25
translation_of: development/tui-parity.md
---

# Textual workspace parity

> **Warning: the TUI is experimental and currently non-functional.** This is an engineering implementation and partial-test report, not a validated investigation interface.

The Textual workspace follows the visual and interaction reference from the Qt commit `5644a9781c68b63811dc23183493ddf41cddb0c6`. The backend data and controls depend on the current Core.

| Qt workflow | Textual implementation | Remaining qualification |
|---|---|---|
| Header, sidebar, status | Chafa logo, operator, case, language and status indicators | Language toggle, terminal sizes |
| Dashboard | CPU/RAM, uptime, cases, mounts, disks, diagnostics | Real distribution testing |
| Case manager | Search, sort, inspector, create/delete/import, explicit activation | Large/partial archives |
| Sources | Mount inventory, selection, unmount and RAW inspection | Multi-image source linking and formats |
| Explorer/evidence | Mount and local-copy trees, bounded HEX/ASCII preview, SHA-256 | Multi-selection and external open parity |
| Analyses | Module selection, PTY output, disk results and census query | Real-device tools |
| Reports/history | Paginated audit and PDF paths, exports | PDF viewing/detail |
| Quick actions | Antivirus/signatures, storage, cloning and RAW | sudo and hardware testing |
| Entity/catalog | Organization fields and module search | Community catalog |
| Supervision | Shared supervisor and `vigil-tui` launcher | Physical restoration testing |

## Integrated terminal

Quick actions use compact cards in one to three columns. Chafa renders the SVG logo where supported; non-UTF-8 terminals can use `VIGIL_ASCII=1`. Terminal output is logged while USB detection, scanning, copying, syncing and verification use distinct progress indicators.

At startup, the supervised TUI can ask for sudo authorization to arm USB protection and reconcile an earlier session. Failures must remain visible. The final session summary appears in the current terminal and detailed logs remain on disk.

Before re-installing the privileged hotplug helper, close all Vigil sessions and inspect `scripts/post-install/install-hotplug.sh`. Do not assume automated Qt tests qualify the USB hardware workflow.

See [native tests](native-recette.md), [Device Manager](device-manager.md) and [compatibility](../compatibility.md).
