# Vigil
**Surcouche Linux pour l'analyse forensique sécurisée de périphériques USB.**

[![License: GPLv3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-green.svg)](https://www.python.org/)

---

## 📌 À propos
Vigil est un poste d'analyse **clé en main** basé sur **ParrotOS**, conçue pour :
- **Analyser** des périphériques USB (clés, disques, smartphones MTP) en **lecture seule**.
- **Garantir** une **chaîne de custody** (journal des actions, horodatage, SHA-256).
- **Isoler** les périphériques analysés du système hôte (montage automatique désactivé,
  triage anti-Rubber Ducky).
- **Offrir** une **interface graphique intuitive** (tkinter) pour les utilisateurs non techniques.

---

## 🎯 Fonctionnalités

✅ **Isolation** : Montage des périphériques en **lecture seule** (`ro,noexec,nosuid,nodev,noatime`)
et verrouillage bloc (`blockdev --setro`).

✅ **Traçabilité** : chaîne de custody par projet, journalisation automatique des actions
(qui ? quoi ? quand ?), SHA-256 de chaque fichier retenu.

✅ **Sécurité** : triage USB anti-Rubber Ducky (blocage des claviers HID apparus au
branchement), désactivation du montage automatique (udisks2), règles sudo restreintes.

✅ **Modularité** : chaque analyse est un script indépendant, lançable seul ou via
l'orchestrateur de scans complets.

✅ **GUI** : interface tkinter sombre. Une interface CLI (Vigil-CLI) dédiée aux
experts est **à venir**.

✅ **Analyses** : recensement (base SQLite), antivirus ClamAV, images (EXIF),
vidéos/audio (ffprobe), bureautique, archives, fichiers chiffrés, forte entropie,
fichiers volumineux, détection de visages, audit d'extensions trompeuses —
chacune avec **rapport PDF** normalisé.

✅ **Imagerie** : copie forensique d'un disque (RAW / E01 / AFF) et clonage bit-à-bit.

---

## 🖥️ Interface graphique

L'interface Vigil est écrite en **tkinter** et organisée en fenêtres parent/enfant.
La hiérarchie courante est toujours affichée dans le titre de la fenêtre
(ex. `Vigil > Configuration > Utilisateurs`).

- `gui/vigil_main_gui.py` — page d'accueil : section **Configuration**
  (système, projets, périphériques USB, mise à jour ClamAV) et section **Actions**
  (recherche de menaces, analyse, stockage, copie forensique, clonage).
- `gui/vigil_config_gui.py` — configuration statique du système (entité,
  établissement, adresse, téléphone, email, logo) et gestion des utilisateurs.
- `gui/vigil_project_manager.py` — gestion des projets (les projets ne sont
  plus liés à un utilisateur ; un utilisateur reste obligatoire pour logger
  les actions via la chaîne de custody).
- `gui/vigil_usb_gui.py` — page **Périphériques USB** : inventaire USB connecté,
  whitelist et blacklist du triage anti-Rubber Ducky.
- `gui/vigil_tools_gui.py` — page **Analyse du périphérique USB** : montage /
  démontage lecture seule, choix du type de périphérique, analyses de fichiers
  individuelles ou multi-scans. Le projet est **obligatoire** (chaîne de custody).
- `gui/vigil_stockage_gui.py` — page **Stockage** : montage d'un périphérique
  en lecture/écriture dans `/stockage` (réservé aux fichiers de travail, pas à
  l'analyse forensique).
- `gui/vigil_imager_gui.py` — page **Copie forensique** : image RAW/E01/AFF
  d'un disque vers une cible externe ou locale.
- `gui/vigil_clamav_update_gui.py` — page **Mise à jour ClamAV** : mise à jour
  des signatures virales en ligne (freshclam) ou par clé USB (postes isolés).
- `gui/vigil_data.py` — couche d'accès aux données partagée.
- `gui/vigil_gui_base.py` — thème, widgets, fenêtre racine unique et navigation.
- `gui/vigil_icons.py` — chargement des icônes SVG (Lucide) avec fallback texte.

Les scripts d'analyse sont lancés dans un terminal **Konsole** (les analyses sont
interactives : choix du périphérique, confirmations).

Démarrage :

```bash
python3 gui/vigil_main_gui.py
```

En développement, redirigez les chemins via les variables d'environnement
`VIGIL_BASE` et `VIGIL_DATA_DIR` pour tester sans droits root.

---

## 📦 Installation

Sur une ParrotOS (ou Debian), copier le projet sous `/opt/vigil` puis lancer :

```bash
sudo bash scripts/post-install/post_install_vigil.sh
```

Le script installe les dépendances (`scripts/post-install/requirements.txt`),
crée `/investigation` et `/stockage`, désactive le montage automatique USB,
crée la commande `vigil`, configure les règles sudo et met à jour ClamAV.
L'accès RDP (xrdp) est proposé **interactivement** (désactivé par défaut).

Voir [docs/installation/README.md](docs/installation/README.md) et
`post-install-checked.txt` (étapes manuelles KDE restantes).

---

## 🗓️ À venir

- **Vigil-CLI** : les wrappers CLI experts (`scripts/Vigil-CLI/`) sont en cours de
  développement et **non garantis fonctionnels** pour l'instant.

---

## 📚 Documentation

La documentation complète est dans [docs/](docs/index.md) :
[interface graphique](docs/interface-graphique/README.md),
[analyse forensique](docs/analyse-forensique/README.md),
[imagerie](docs/imagerie-forensique/README.md),
[stockage](docs/stockage/README.md),
[rapports PDF](docs/rapports-pdf/README.md),
[configuration](docs/configuration/README.md).

---

## 📜 Licence

Projet sous licence **GPLv3** — voir [LICENSE](LICENSE).
