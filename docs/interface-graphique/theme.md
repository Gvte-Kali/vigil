---
layout: default
parent: "Interface"
nav_order: 102
---

# 🎨 Thème et charte graphique

> La GUI Vigil est en **mode sombre** avec une charte sobre et professionnelle.
> Les couleurs sont sémantiques : chaque catégorie d'action a sa teinte d'accent.

---

## 📖 En résumé

Le thème est centralisé dans `gui/vigil_gui_base.py` (constantes `COLOR_*`,
`FONT_*`, `PAD`, `WIDGET_PAD`). Les boutons principaux utilisent une
**barre d'accent verticale** colorée à gauche, qui rend l'icône en noir.

---

## 🎨 Palette (Tokyo Night)

| Constante | Hex | Usage |
|---|---|---|
| `COLOR_BG` | `#1e1e2e` | Fond global |
| `COLOR_SURFACE` | `#2a2a3c` | Surface des cadres |
| `COLOR_SURFACE_ALT` | `#313349` | Surface des boutons |
| `COLOR_ACCENT` | `#7aa2f7` | Bleu — accent par défaut, analyse |
| `COLOR_DANGER` | `#f7768e` | Rouge — danger, quitter |
| `COLOR_SUCCESS` | `#9ece6a` | Vert — succès, scan antivirus |
| `COLOR_TEXT` | `#c0caf5` | Texte principal |
| `COLOR_TEXT_DIM` | — | Texte secondaire |

## 🌈 Teintes d'accent des boutons

| Constante | Hex | Sens |
|---|---|---|
| `_ACCENT_CONFIG` | `#bb9af7` | Violet — configuration |
| `_ACCENT_PROJET` | `#9d7cd8` | Violet profond — projets |
| `_ACCENT_AV_UPDATE` | `#e0af68` | Ambre — mise à jour ClamAV |
| `_ACCENT_ANALYSE` | `COLOR_ACCENT` | Bleu — analyse |
| `_ACCENT_STOCKAGE` | `#7dcfff` | Cyan clair — stockage |
| `_ACCENT_IMAGER` | `#7dcfff` | Cyan clair — imagerie / clonage |
| `_ACCENT_AV_SCAN` | `COLOR_SUCCESS` | Vert — scan antivirus |
| `_ACCENT_QUIT` | `COLOR_DANGER` | Rouge — quitter |

## 🔘 Barre d'accent + icône

La fonction `_accent_button(parent, accent_color, make_button, icon_name="")`
dans `gui/vigil_main_gui.py` :

1. crée une ligne (`tk.Frame`) pleine largeur ;
2. ajoute une **barre** `tk.Frame` de 28 px de la couleur d'accent
   (`pack_propagate(False)` pour fixer la largeur) ;
3. y place l'**icône Lucide** rendue en noir (`#1e1e2e`) via
   `icons.icon_or_symbol(icon_name, 18, "#1e1e2e")` ;
4. ajoute le bouton `CategoryButton` à droite, qui occupe le reste de la largeur.

L'icône n'apparaît **que** dans la barre colorée — le bouton lui-même ne porte
ni icône ni emoji, pour éviter tout doublon.
