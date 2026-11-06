---
layout: default
parent: Interface
title: Thème
nav_order: 42
---

# Thème et charte graphique

## Site de documentation : Graphite

La documentation utilise **Just the Docs** avec une palette Graphite : fond anthracite,
surfaces gris sombre, texte clair et liens bleu glacier. La typographie système
évite le chargement de polices externes.

| Élément | Couleur |
|---|---|
| Fond | `#181b20` |
| Navigation et surfaces | `#20242b` |
| Texte | `#e5e9f0` |
| Texte secondaire | `#aab4c2` |
| Accent | `#9cc9f5` |
| Bordures | `#38414d` |

Les réglages sont répartis entre `docs/_config.yml`,
`docs/_sass/color_schemes/graphite.scss` (palette),
`docs/_sass/custom/setup.scss` (dimensions) et
`docs/_sass/custom/custom.scss` (composants et mise en page).
La navigation se replie sur mobile et les tableaux restent défilables.

## Application Tkinter

La palette de l’application reste définie dans `gui/vigil_gui_base.py`
(constantes `COLOR_*`, `FONT_*`, `PAD` et `WIDGET_PAD`).
Elle utilise notamment `#1e1e2e` en fond et `#7aa2f7` comme accent bleu.

Les boutons principaux de l’accueil possèdent une barre colorée de 28 pixels
avec une icône sombre. Les accents distinguent configuration, analyse, stockage,
imagerie et actions sensibles.

Pour modifier l’application, agir sur ses constantes partagées ; les styles du site
n’ont aucun effet sur les fenêtres Tkinter ni sur les rapports PDF.
