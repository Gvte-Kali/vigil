---
layout: default
title: "Configuration"
nav_order: 60
has_children: True
---

# ⚙️ Configuration

> La **configuration** de Vigil est centralisée : une **entité statique unique**
> (organisme), des **utilisateurs** rattachés, des **projets** globaux, et un
> **logo** affiché sur les rapports.

---

## 📖 En résumé

Avant d'analyser un périphérique, on configure une fois l'**entité** (nom de
l'organisme, établissement, adresse, téléphone, email, logo) et on crée au
moins un **utilisateur** (obligatoire pour logger les actions). Les **projets**
sont globaux (non liés à un utilisateur) mais un utilisateur doit être
sélectionné pour logger la chaîne de custody.

> **Projet obligatoire (sauf antivirus).** Toutes les analyses de fichiers
> exigent un projet actif (chaîne de custody). La seule exception est le
> **scan antivirus ClamAV**, lançable sans projet. Voir
> [Analyse forensique](../analyse-forensique/README.md).

---

## 🗂️ Pages

| Page | Fichier | Rôle |
|---|---|---|
| Configuration du système | `gui/vigil_config_gui.py` | Entité, coordonnées, logo, gestion des utilisateurs |
| Gérer les projets | `gui/vigil_project_manager.py` | Création / modification des projets |
| Mise à jour ClamAV | `gui/vigil_clamav_update_gui.py` | Mise à jour des signatures virales |

## 🧪 ClamAV — mise à jour des signatures

| Script | Mode |
|---|---|
| `scripts/clamav/vigil_clamav_update.sh` | **En ligne** via `freshclam` (machine connectée) |
| `scripts/clamav/vigil_clamav_update_usb.sh` | **Par clé USB** (postes isolés hors réseau) |

La mise à jour par USB monte le périphérique en lecture seule
(`blockdev --setro`) dans `/stockage`, copie les fichiers `.cvd` (main, daily,
bytecode) dans le `DatabaseDirectory` ClamAV, puis démonte et rebloque le
périphérique.

## 🔗 Voir aussi

- [Interface graphique](../interface-graphique/README.md)
- [Antivirus](../analyse-forensique/antivirus.md)
