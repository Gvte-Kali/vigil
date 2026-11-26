---
layout: english
title: UI, terminals and acquisition specification
parent: Developer reference
grand_parent: English
nav_order: 11
translation_of: development/cahier-des-charges-interface.md
---

# Vigil 2.0 — UI/UX and terminal engineering specification

**Status:** historical implementation specification. Check the current Qt/Textual code and tests before applying any item.

## Goals

Vigil is a modular DFIR framework, not simply a GUI that invokes Bash scripts. The design work addresses four related areas: a consistent Qt workspace, external terminal handling, acquisition/clone progress presentation and a storage-mount context error.

## A. Graphical interface

- Unified Graphite/Cyan palette, original Vigil logo, semantic action colors and reusable Lucide-style icons.
- Persistent shell containing header, navigation, workspace and status strip.
- Structured pages for dashboard, cases, evidence explorer, module catalog, entity configuration and quick actions.
- Fixed navigational structure with Qt layouts, splitters and local scroll areas rather than web-style responsive reflow.
- Explicit empty/error/loading states, bilingual FR/EN and keyboard/mouse access.
- Preserve source RO and destination RW information even when the interface is simplified.

## B. External operations

Remove the redundant in-GUI task center where requested. Launch tracked operations in a suitable desktop terminal with verified argument handling, without building unsafe shell commands. Support different X11/Wayland environments and Hyprland without editing the user's window-manager configuration.

Do not tie a running acquisition's lifetime to the GUI window; the session supervisor and tracked processes remain responsible for cleanup and reporting.

## C. Terminal presentation

- Consistent banner/logo, ANSI semantic colors and plain/NO_COLOR fallbacks.
- In-place progress lines rather than repeated per-second logs.
- Real measured percentages only; show indeterminate elapsed state while synchronizing.
- Distinct acquisition, synchronization, SHA-256 verification and finalization phases.
- Preserve the original exit code, exact byte counts, audit logs and final result.

The USB 2.0 observation did **not** justify changing underlying copy, sync, cache or hashing algorithms for performance.

## D. Storage context bug

Trace the quick-action mount path through Qt, adapters, context construction and scripts to the root cause of `invalid storage context`. Permit authorized storage operations without an active case where specified; do not bypass device identity, RO/RW or privilege checks.

## Validation

Test small/large window layouts, X11/Wayland, external terminal choices, cancellation, errors and device-operation simulations. Confirm identical backend behavior in the CLI/TUI/GUI. See [Qt execution paths](qt-execution.md) and [permissions](permissions-audit.md).

The original French design specification contains detailed screen descriptions and phase-by-phase acceptance criteria; this English engineering reference organizes the same work by subsystem.
