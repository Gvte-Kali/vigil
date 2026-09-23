#!/usr/bin/env python3
"""Chargeur d'icônes Vigil (Lucide) avec dégradation vers les symboles Unicode."""

import os
import tkinter as tk

_ICONS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "icons")

_CACHE = {}

FALLBACK = {
    "shield": "◆",
    "settings": "⚙",
    "folder": "▸",
    "play": "▸",
    "search": "⌕",
    "list": "▤",
    "folder-tree": "▤",
    "database": "⬢",
    "hard-drive": "⬢",
    "copy": "⧉",
    "plug": "⏏",
    "usb": "⏏",
    "power": "⏎",
    "check-square": "☑",
    "image": "▣",
    "home": "⌂",
    "info": "ℹ",
    "check": "✓",
    "x": "✕",
    "square": "■",
    "triangle-alert": "⚠",
    "trash": "🗑",
    "plus": "＋",
    "pencil": "✎",
    "arrow-left": "←",
    "user": "◉",
    "circle-user": "◉",
    "upload": "⇡",
    "flask-conical": "◆",
    "log-out": "⏎",
    "chevron-down": "▼",
    "chevron-up": "▲",
    "circle-dot": "●",
}


def _read_svg(name):
    path = os.path.join(_ICONS_DIR, name + ".svg")
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _colorize(svg, color):
    if svg is None:
        return None
    if "currentColor" in svg:
        return svg.replace("currentColor", color)
    return svg


def _rasterize(svg, size, color):
    svg = _colorize(svg, color)
    if svg is None:
        return None
    try:
        import cairosvg
    except Exception:
        return None
    try:
        return cairosvg.svg2png(bytestring=svg.encode("utf-8"), output_width=size, output_height=size)
    except Exception:
        return None


def get_icon(name, size=20, color="#c0caf5"):
    key = (name, size, color)
    if key in _CACHE:
        return _CACHE[key]
    svg = _read_svg(name)
    if svg is None:
        _CACHE[key] = None
        return None
    png = _rasterize(svg, size, color)
    if png is None:
        _CACHE[key] = None
        return None
    try:
        photo = tk.PhotoImage(data=png)
    except Exception:
        _CACHE[key] = None
        return None
    _CACHE[key] = photo
    return photo


def icon_or_symbol(name, size=20, color="#c0caf5"):
    photo = get_icon(name, size, color)
    if photo is not None:
        return photo, None
    return None, FALLBACK.get(name, "")
