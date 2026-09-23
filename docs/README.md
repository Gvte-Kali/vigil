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
  non techniciens, avec un accès CLI pour les experts.

---

## 🗺️ Cartographie de la documentation

La documentation est organisée en **catégories** (parents) et **sous-pages**
(enfants). Chaque dossier contient son propre `README.md`.

| Catégorie | Description |
|---|---|
| 🖥️ [Interface graphique](interface-graphique/README.md) | La GUI Tkinter : pages, navigation, thème, icônes |
| 🔍 [Analyse forensique](analyse-forensique/README.md) | Montage lecture seule + toutes les analyses de fichiers + orchestrateur |
| 💾 [Imagerie forensique](imagerie-forensique/README.md) | Copie forensique (RAW/E01/AFF) et clonage bit-à-bit de disques |
| 📁 [Stockage](stockage/README.md) | Montage en lecture/écriture pour les fichiers de travail |
| 📄 [Rapports PDF](rapports-pdf/README.md) | Le générateur PDF commun à toutes les analyses |
| ⚙️ [Configuration](configuration/README.md) | Entité, utilisateurs, projets, logo |
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
│   └── Vigil-CLI/  # Wrappers CLI (à venir — en suspens)
├── data/icons/    # Icônes Lucide (SVG)
└── rapports/       # Rapports PDF générés
```
