---
layout: english
title: Phase 00: original repository audit
parent: Developer reference
grand_parent: English
nav_order: 19
translation_of: development/phase-00-audit.md
---

# Phase 00 — Original Vigil 2.0 audit

**Historical baseline:** commit `a2553bada827cd0e521541b51a4bbc853d416788`. The original document contains a very large, file-by-file static inventory of the legacy project. This English reference preserves its scope and audit method; use the [French inventory](../../development/phase-00-audit.md) for individual source excerpts and line-by-line evidence.

## Inventory

The audit inspected tracked files using `git ls-files` and searched for privilege boundaries, hard-coded paths, script entrypoints, GUI state, configuration and module dependencies. It covered:

- `gui/`: Tkinter main window, navigation, configuration, projects, USB management, ClamAV update, storage, imaging, tools, icons and persistence.
- `scripts/Vigil-CLI/`: original Bash entrypoint and analysis/mount/unmount wrappers.
- `scripts/analyse/`: census, images, video, audio, archives, office, encryption, entropy, large files, face detection, format audit and mounts.
- `scripts/clamav/`: full scan, targeted scan, signature download, USB update and malware hunt.
- `scripts/imager/`, `scripts/pdf/`, `scripts/export/` and common shell libraries.
- Configuration, icons, repository documentation and the original `todo.txt`.

## Risks identified

1. GUI state and scripts had overlapping responsibilities with inconsistent operator/project context.
2. Multiple mount paths could diverge in triage, authorization and read-only protections.
3. Several operations relied on global filesystem paths or interactive terminal state.
4. Evidence integrity and chain-of-custody depended on accurate, non-overwriting exports and logs.
5. Tests were mostly static or synthetic; real-device and multi-distribution claims required separate validation.

## Decisions recorded

The project should introduce a reusable Python Core, versioned manifests, capability validation, a consistent Qt workspace, scriptable CLI and later TUI. System mutation ownership and exit verification must be explicit, with no permanent daemon.

## How to use this document

The audit is **not a current inventory**. Compare its file paths and findings with the latest source and [test baseline](test-baseline.md). In particular, its original branch and tool observations describe that point in time only.

The full historical source index remains in the corresponding French reference, linked above.
