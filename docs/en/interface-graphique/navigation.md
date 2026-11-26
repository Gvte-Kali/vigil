---
layout: english
title: Legacy navigation
parent: Desktop interface
grand_parent: English
nav_order: 41
translation_of: interface-graphique/navigation.md
---

# Navigation — legacy Tkinter interface

**Scope:** Vigil 1.0, not the current Qt navigation.

The original navigation lives in `gui/vigil_gui_base.py`. Tkinter pages share a root window and a `NAV` label stack.

## Behavior

1. The parent opens a child page with `window.open_child(...)`.
2. Page content is replaced and the label is pushed on the stack.
3. The title follows the breadcrumb, such as `Vigil > Configuration > Users`.
4. **Back** restores the parent; `quit_app()` exits the application.

| Shared component | Purpose |
|---|---|
| `VigilWindow` | Header, body and navigation |
| `header_title()` | Logo and page titles |
| `Section` | Collapsible group |
| `CategoryButton` | Main category action |
| `ActionButton` | Compact action |

Reuse these components only when working on the legacy UI. The Qt shell uses different classes; see [Desktop interface](README.md).
