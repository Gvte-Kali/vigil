---
layout: default
title: "Actions"
nav_order: 20
has_children: true
---

# ⚡ Actions

> La section **Actions** de la page d'accueil (`vigil_main_gui.py`) regroupe
> les cinq boutons opérationnels : recherche de menaces, analyse d'un
> périphérique, stockage, copie forensique et clonage.

---

## 📖 En résumé

| Bouton de l'accueil | Cible | Documentation |
|---|---|---|
| 🛡️ Recherche de menaces | `vigil_malware_hunt.sh` (Konsole) | [Recherche de menaces](menaces.md) |
| 🔍 Analyser un périphérique | `gui/vigil_tools_gui.py` | [Analyser un périphérique](analyse.md) |
| 📁 Monter un périphérique de stockage | `gui/vigil_stockage_gui.py` | [Stockage](stockage.md) |
| 💾 Faire une copie forensique d'un disque | `gui/vigil_imager_gui.py` | [Copie forensique](copie-forensique.md) |
| 💾 Cloner un disque dur | `vigil_disk_clone.sh` (Konsole) | [Clonage bit-à-bit](clonage.md) |

Les actions qui ouvrent une page GUI demandent l'analyse dans la page fille
(montage, choix du périphérique, lancement des scans). Les actions
**Recherche de menaces** et **Clonage** sont lancées directement dans un
terminal **Konsole** après une confirmation, avec le déroulé complet
(interactif) dans le terminal.
