---
layout: english
title: Legacy icons
parent: Desktop interface
grand_parent: English
nav_order: 43
translation_of: interface-graphique/icones.md
---

# Icons — legacy Tkinter interface

Lucide SVGs live in `data/icons/` and are loaded by `gui/vigil_icons.py`.

Call `icon_or_symbol(name, size, color)` to request an icon. The helper replaces `currentColor`, rasterizes with CairoSVG, constructs a Tkinter `PhotoImage` and caches it by name, size and color.

If an SVG or its rendering dependencies are missing, a Unicode fallback preserves access to the action.

## Add an icon

1. Add `data/icons/<name>.svg`.
2. Use `currentColor` for tinting.
3. Register a fallback symbol under `FALLBACK`.
4. Test with and without CairoSVG.

This describes Vigil 1.0. Qt and Textual may use different rendering paths; see [Desktop interface](README.md).
