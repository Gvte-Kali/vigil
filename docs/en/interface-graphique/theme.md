---
layout: english
title: Theme and design
parent: Desktop interface
grand_parent: English
nav_order: 42
translation_of: interface-graphique/theme.md
---

# Theme and visual identity

## Documentation site: Graphite

The site uses **Just the Docs** with a Graphite palette: dark charcoal backgrounds, light text, cool-blue links and system fonts (no external font download).

| Element | Value |
|---|---|
| Background | `#181b20` |
| Navigation and surfaces | `#20242b` |
| Text | `#e5e9f0` |
| Secondary text | `#aab4c2` |
| Accent | `#9cc9f5` |
| Borders | `#38414d` |

Site styling lives in `docs/_config.yml`, `docs/_sass/color_schemes/graphite.scss`, `docs/_sass/custom/setup.scss` and `docs/_sass/custom/custom.scss`. Navigation collapses on mobile; tables can scroll.

## Legacy Tkinter application

Vigil 1.0 uses shared constants (`COLOR_*`, `FONT_*`, `PAD`, `WIDGET_PAD`) in `gui/vigil_gui_base.py`; a typical background is `#1e1e2e` with accent `#7aa2f7`. Main buttons have a colored 28-pixel icon strip distinguishing actions.

**The legacy Tkinter palette does not describe the current Qt theme.** Qt styling lives in `vigil/desktop_theme.py`, and the website's stylesheet does not affect app windows or PDFs.
