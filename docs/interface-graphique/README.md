---
layout: default
title: Interface
nav_order: 40
has_children: true
---

# Interface graphique

Vigil 2.0 ouvre la GUI Qt avec `vigil gui` ou `vigil-gui`. La navigation
regroupe Espace de travail, Investigation et Système. La TUI Textual se lance
avec `vigil tui` ou `vigil-tui`. Voir [Installation](../installation/README.md)
pour les lanceurs et [Recette native](../development/native-recette.md) pour les essais.

Les repères détaillés ci-dessous concernent la GUI Tkinter de Vigil 1.0,
conservée dans `gui/`.

## Pages et modules

| Module dans `gui/` | Rôle |
|---|---|
| `vigil_main_gui.py` | Accueil et lancement des actions |
| `vigil_config_gui.py` | Entité et utilisateurs |
| `vigil_project_manager.py` | Gestion et export des projets |
| `vigil_usb_gui.py` | Inventaire et listes USB |
| `vigil_clamav_update_gui.py` | Mise à jour antivirus |
| `vigil_tools_gui.py` | Contexte, montage et analyses |
| `vigil_stockage_gui.py` | Supports de travail en lecture/écriture |
| `vigil_imager_gui.py` | Acquisition d’images disque |
| `vigil_data.py` | Données partagées et journal de traçabilité |
| `vigil_gui_base.py` | Fenêtre, navigation et widgets communs |
| `vigil_icons.py` | Chargement des icônes |

La recherche de menaces et le clonage se lancent directement dans Konsole.

## Repères pour contribuer

- [Navigation](navigation.md) : fenêtre partagée et retour aux pages parentes.
- [Thème](theme.md) : palette et composants de l’application ; charte Graphite du site.
- [Icônes](icones.md) : SVG Lucide, cache et solution de secours.

En développement, utiliser `VIGIL_BASE` et `VIGIL_DATA_DIR` pour isoler les données.
Voir [Installation](../installation/README.md).
