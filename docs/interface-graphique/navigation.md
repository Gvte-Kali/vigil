---
layout: default
parent: Interface
title: Navigation
nav_order: 41
---

# Navigation

La navigation est centralisée dans `gui/vigil_gui_base.py`.
Les pages utilisent une racine Tkinter partagée et une pile de labels `NAV`.

## Comportement

1. Le parent ouvre une page avec `window.open_child(...)`.
2. Le contenu est remplacé et le label de la page est ajouté à la pile.
3. Le titre reflète le chemin, par exemple `Vigil > Configuration > Utilisateurs`.
4. **Retour** restaure le parent ; `quit_app()` ferme l’application.

## Composants partagés

| Composant | Usage |
|---|---|
| `VigilWindow` | En-tête, corps et navigation |
| `header_title()` | Logo, titre et sous-titre |
| `Section` | Groupe repliable |
| `CategoryButton` | Bouton principal |
| `ActionButton` | Action compacte |

Réutiliser ces composants pour conserver les mêmes repères entre les pages.
