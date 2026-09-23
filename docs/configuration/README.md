---
layout: default
title: "Configuration"
nav_order: 10
has_children: true
---

# ⚙️ Configuration

> La section **Configuration** de la page d'accueil (`vigil_main_gui.py`)
> regroupe les quatre boutons de paramétrage : système, projets,
> périphériques USB et mise à jour ClamAV.

---

## 📖 En résumé

| Bouton de l'accueil | Page GUI | Documentation |
|---|---|---|
| ⚙️ Configuration du système | `gui/vigil_config_gui.py` | [Système et utilisateurs](systeme.md) |
| 📁 Gérer les projets | `gui/vigil_project_manager.py` | [Projets](projets.md) |
| 🔌 Périphériques USB | `gui/vigil_usb_gui.py` | [Périphériques USB](peripheriques-usb.md) |
| 🧪 Mettre à jour l'antivirus ClamAV | `gui/vigil_clamav_update_gui.py` | [Mise à jour ClamAV](clamav.md) |

Chaque bouton ouvre une page fille spécialisée. La hiérarchie courante est
toujours affichée dans le titre de la fenêtre
(ex. `Vigil > Configuration > Utilisateurs`).

---

## 🔗 Voir aussi

- [Actions](../actions/README.md) — les cinq boutons opérationnels de l'accueil
- [Installation](../installation/README.md)
