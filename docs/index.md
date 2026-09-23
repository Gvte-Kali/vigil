---
layout: default
title: "Vigil — Documentation technique"
nav_order: 1
---

# 🛡️ Vigil — Documentation technique

> **Vigil** est une application d'analyse forensique de périphériques USB et de disques,
> conçue pour les autorités (police, gendarmerie, administration pénitentiaire).
> Elle garantit que les preuves numériques sont examinées **sans aucune altération**
> des supports analysés.

---

## 📖 En résumé

En quelques mots : on branche un périphérique (clé USB, disque, etc.), Vigil le
**monte en lecture seule** (on ne peut que lire, jamais écrire dessus), puis on
lance des **analyses automatisées** (antivirus, images, vidéos, audio, documents,
archives, fichiers verrouillés…). Chaque analyse produit un **rapport PDF**
prêt à être joint à une procédure, avec la signature numérique (SHA-256) de
chaque fichier pertinent.

Vigil propose aussi :

- 📋 une **copie forensique** d'un disque (image RAW / E01 / AFF) ;
- 📋 un **clonage bit-à-bit** d'un disque vers un autre ;
- 📋 une **interface graphique** (mode sombre) pensée pour des utilisateurs
  non techniciens. Une interface CLI (Vigil-CLI) dédiée aux experts est **à venir**.

---

## 🗺️ Cartographie de la documentation

La documentation est organisée **comme la page d'accueil de la GUI** :
deux grandes catégories — **Configuration** et **Actions** — avec une
fiche par bouton, plus les pages transverses.

| Catégorie | Description |
|---|---|
| ⚙️ [Configuration](configuration/README.md) | Section **Configuration** de l'accueil : système, projets, périphériques USB, ClamAV |
| ⚡ [Actions](actions/README.md) | Section **Actions** de l'accueil : menaces, analyse, stockage, copie forensique, clonage |
| 📄 [Rapports PDF](rapports-pdf/README.md) | Le générateur PDF commun à toutes les analyses |
| 🖥️ [Interface graphique](interface-graphique/README.md) | La GUI Tkinter : pages, navigation, thème, icônes |
| 📦 [Installation](installation/README.md) | Post-installation, dépendances, commande `vigil` |

---

## 🚀 Démarrage rapide

```bash
# Lancer l'interface graphique
vigil
# ou directement
python3 /opt/vigil/gui/vigil_main_gui.py
```

Une fois la GUI ouverte :

1. **Configurer** l'entité, le logo et au moins un utilisateur (page Configuration).
2. **Choisir** un utilisateur (obligatoire) et un projet (optionnel).
3. **Analyser** un périphérique → montage en lecture seule → lancement des scans.
4. **Consulter** les rapports PDF dans `/opt/vigil/rapports/`.

---

## 🧱 Principes forensiques appliqués

- 🔒 **Lecture seule stricte** : les périphériques analysés sont montés avec
  `ro,noexec,nosuid,nodev,noatime` et verrouillés au niveau bloc
  (`blockdev --setro`).
- 🔏 **Intégrité** : signature SHA-256 de chaque fichier et de chaque image disque.
- 👤 **Traçabilité** : un utilisateur doit être sélectionné pour logger les actions.
- 🧩 **Modularité** : chaque analyse est un script indépendant, lançable seul ou
  via l'orchestrateur de scans complets.

---

## 📂 Structure du projet

```
/opt/vigil/
├── gui/            # Interface graphique (Python / Tkinter)
├── scripts/
│   ├── analyse/    # Montage RO + analyses de fichiers
│   ├── clamav/     # Antivirus ClamAV
│   ├── imager/     # Copie forensique + clonage
│   ├── stockage/   # Montage lecture/écriture
│   ├── pdf/        # Générateur PDF commun
│   ├── post-install/
│   └── Vigil-CLI/  # Wrappers CLI experts — **à venir** (en cours de développement)
├── data/icons/    # Icônes Lucide (SVG)
└── rapports/       # Rapports PDF générés
```
