---
layout: english
title: Remaining validation work
parent: Developer reference
grand_parent: English
nav_order: 22
translation_of: development/remaining-phases.md
---

# Remaining validation criteria

This view summarizes work historically left open after case journal and JSON export features were added. It is an engineering checklist, **not a list of defects confirmed today**.

| Phase | Outstanding validation |
|---|---|
| 00 | Human review and acceptance of the original audit |
| 01 | Closed privileged broker, RO guarantees, MTP paths, destination checks and VM tests |
| 02 | Strict module contracts, legacy adapters, CLI/GUI parity, presets and autonomous search |
| 03–05 | Case/evidence lifecycle, indexing, correlation, jobs, reports and session cleanup |
| 06–08 | Responsive UI behavior within desktop constraints, user workflows and functional parity |
| Release | Multi-distribution validation, packaging, security and documentation |

## Journal export

The case audit journal should remain attributable to operator and case, sortable and exportable without truncating required evidence. Synthetic tests must include empty history, pagination and events with Unicode or special characters.

Consult the repository's `todo.txt`, `tests.txt` and [compatibility matrix](compatibility-matrix.md) for current status. Historical checkmarks cannot replace current reproducible tests.
