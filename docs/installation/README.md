---
layout: default
title: Installation
nav_order: 50
---

# Installation

Vigil cible un poste dédié sous ParrotOS, avec une base Debian.
Le script de post-installation configure le système et nécessite les droits administrateur.

## Installer et lancer

Consulter la [procédure de transition des privilèges](../development/phase-01-transition.md), puis placer le dépôt dans `/opt/vigil` et lancer depuis la session opérateur :

```bash
cd /opt/vigil
bash scripts/post-install/post_install_vigil.sh
vigil
```

L’accès RDP est proposé pendant l’installation et désactivé par défaut.
Après installation, terminer les réglages KDE décrits dans `post-install-checked.txt`
à la racine du dépôt, puis [configurer l’entité et les utilisateurs](../configuration/systeme.md).

## Modifications du poste

- Installation des paquets de `scripts/post-install/requirements.txt`.
- Création de `/investigation`, `/stockage` et des dossiers de données, journaux et rapports.
- Désactivation du montage automatique et masquage d’`udisks2`.
- Initialisation des données. L’administrateur vérifie la politique sudo du poste.
- Création de la commande `vigil`, du raccourci et des emplacements Dolphin.
- Mise à jour initiale des signatures ClamAV.
- Si accepté : activation de `xrdp` et configuration du port 3389/tcp via UFW.

## Dépendances principales

| Besoin | Outils |
|---|---|
| Interface | Python 3, Tkinter, Konsole, Pillow, CairoSVG |
| PDF | ReportLab |
| Métadonnées | `file`, `exiftool`, `ffprobe` |
| Archives et entropie | `7za`, `zstd`, `binwalk` |
| Antivirus | ClamAV et FreshClam |
| Imagerie | `dc3dd`, outils EWF et AFFlib |
| Visages | `facedetect` ou OpenCV |
| Téléphones | Outils MTP dont `jmtpfs` |

La liste complète et commentée reste dans `requirements.txt`.

## Développement local

Depuis la racine du dépôt :

```bash
VIGIL_BASE="$PWD" VIGIL_DATA_DIR="$PWD/data" python3 gui/vigil_main_gui.py
```

Ce lancement permet d’examiner l’interface sans installer le poste complet.
Les opérations réelles sur les supports nécessitent les outils et droits système.
