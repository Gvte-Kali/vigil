---
layout: english
title: Desktop interface
parent: English
nav_order: 12
has_children: true
translation_of: interface-graphique/README.md
---

# Desktop interface guide

The **PySide6/Qt GUI** is the primary workflow for exploring Vigil on `main`.

## Navigation

| Main area | Purpose |
|---|---|
| **Workspace → Dashboard** | Activity, inventory and device status |
| **Investigation → Current case** | Cases, file browser, evidence, analysis, reports and export |
| **Investigation → Quick actions** | Antivirus, working storage, RAW imaging and cloning |
| **System → Configuration** | Organization, session, terminal and module catalog |

Use the header to choose the operator and language. The status bar shows protections and mount-zone state. Hardware operations continue to require Vigil's safety checks.

Follow [Your first investigation](../getting-started.md) for a guided example.

## Qt and Textual

- **Qt GUI:** `vigil gui` or `vigil-gui`, requiring a graphical session.
- **Textual TUI:** `vigil tui` and `vigil-tui` are experimental entrypoints, but the interface is **currently non-functional** and must not be used for investigations.

## Legacy interface references

The [Navigation](navigation.md), [Theme](theme.md) and [Icons](icones.md) subpages partly describe the **Vigil 1.0 Tkinter UI** still present under `gui/`. They are developer references, not a promise about current Qt controls.

Qt sources include `vigil/desktop.py`, `vigil/desktop_theme.py` and related panels. See the [architecture](../development/architecture-v2.md) and [Qt execution flow](../development/qt-execution.md).
