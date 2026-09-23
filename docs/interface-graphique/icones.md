# 🎯 Icônes (Lucide)

> Les icônes de la GUI proviennent de **Lucide** (fork open-source de Feather Icons),
> stockées en SVG dans `data/icons/`. Elles sont rasterisées à la volée en PNG
> via `cairosvg` pour Tkinter.

---

## 📖 En résumé

`gui/vigil_icons.py` expose `icon_or_symbol(name, size, color)`. S'il existe un
SVG nommé `name.svg`, il est rendu en PNG avec la `color` (le placeholder
`currentColor` est remplacé) et renvoyé comme `PhotoImage`. Sinon, on retombe
sur un symbole Unicode (table `FALLBACK`). Les icônes sont mises en cache par
clé `(name, size, color)`.

---

## 🗂️ Icônes disponibles

`shield, settings, folder, folder-tree, search, list, database, hard-drive,
copy, plug, power, check-square, image, home, info, check, x, square,
triangle-alert, plus, pencil, arrow-left, user, circle-user, upload,
flask-conical, log-out, play`.

## ⚙️ Mécanisme de rendu

1. **Lecture** du SVG (`data/icons/<name>.svg`).
2. **Colorisation** : remplacement de `currentColor` par la couleur demandée.
3. **Rasterisation** via `cairosvg.svg2png()` (taille demandée).
4. **Encapsulation** dans `tk.PhotoImage(data=png)`.
5. **Cache** dans `_CACHE[(name, size, color)]`.

> ⚠️ Si `cairosvg` ou `libcairo` est absent, le rendu échoue silencieusement et
> la GUI retombe sur le symbole Unicode — la fonctionnalité reste disponible.

## 🖌️ Usage dans la barre d'accent

Dans `_accent_button()`, l'icône est rendue en **noir** (`#1e1e2e`) sur fond de
la couleur d'accent vive, pour rester bien visible et contraster proprement.
