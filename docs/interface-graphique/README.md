---
layout: default
title: Interface
nav_order: 40
has_children: true
---

# Guide de l'interface graphique

La **GUI PySide6/Qt** constitue le parcours principal pour découvrir Vigil sur la branche `main`.

## Se repérer

| Navigation principale | Utilité |
|---|---|
| **Espace de travail → Tableau de bord** | Activité, inventaire et état des supports |
| **Investigation → Affaire en cours** | Gestion des affaires, explorateur, preuves, analyses, rapports et export |
| **Investigation → Actions rapides** | Antivirus, stockage, acquisition RAW et clonage |
| **Système → Configuration** | Entité, session, terminal et catalogue de modules |

L'en-tête donne accès à l'opérateur et au choix de langue. La barre d'état rappelle les protections et les zones de montage. Les opérations matérielles restent soumises aux contrôles de Vigil.

Pour une démonstration complète, consultez [Ma première investigation](../getting-started.md).

## GUI et TUI

- **GUI Qt :** `vigil gui` ou `vigil-gui`, pour les sessions graphiques.
- **TUI Textual :** `vigil tui` ou `vigil-tui` existent comme points d'entrée expérimentaux, mais l'interface est **non fonctionnelle à ce stade**. Ne pas l'utiliser pour des investigations.

## Documentation de l'interface historique

Les sous-pages [Navigation](navigation.md), [Thème](theme.md) et [Icônes](icones.md) décrivent en partie **la GUI Tkinter de Vigil 1.0**, conservée sous `gui/`. Ces informations sont utiles aux contributeurs, mais ne représentent pas nécessairement les composants Qt actuels.

Le développement Qt se trouve notamment dans `vigil/desktop.py`, `vigil/desktop_theme.py` et les panneaux associés. Voir la [documentation d'architecture](../development/architecture-v2.md) et le [parcours d'exécution Qt](../development/qt-execution.md).
