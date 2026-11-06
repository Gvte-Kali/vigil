---
layout: default
parent: Interface
title: Icônes
nav_order: 43
---

# Icônes

Les SVG Lucide sont stockés dans `data/icons/` et chargés par `gui/vigil_icons.py`.

## Utilisation

Appeler `icon_or_symbol(name, size, color)` pour demander une icône.
Le module remplace `currentColor`, rasterise le SVG avec CairoSVG, crée une
`PhotoImage` Tkinter et conserve le résultat en cache par `(name, size, color)`.

Si le SVG ou les dépendances de rendu manquent, un symbole Unicode prend le relais.
L’action reste accessible.

## Ajouter une icône

1. Ajouter le SVG dans `data/icons/<name>.svg`.
2. Utiliser `currentColor` pour permettre la coloration.
3. Prévoir un symbole de secours dans la table `FALLBACK`.
4. Vérifier le rendu avec et sans CairoSVG.

Sur les boutons principaux, l’icône apparaît dans la barre d’accent colorée.
