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
vigil --help
/usr/local/bin/vigil-gui
```

Le post-install place le venv dans `/opt/vigil/.venv`. En terminal interactif,
`vigil`, `vigil tui` et `vigil-tui` ouvrent le workspace Textual supervisé.
Les sous-commandes CLI restent automatisables. Le raccourci graphique appelle `/usr/local/bin/vigil-gui`, qui démarre Qt
avec les données de travail dans `/opt/vigil/data/state`.
La configuration des signatures se trouve dans le sous-dossier `clamav`.
Un lancement éditable depuis le code dans /opt/vigil utilise aussi cet
emplacement pour la base, la custody historique, les signatures, les
instantanés et les préférences Qt de chaque UID. Hors de /opt/vigil,
le mode développement continue à utiliser XDG ou ~/.local/state, sauf
si VIGIL_STATE_DIR désigne un chemin absolu. Les scans rapides conservent
l’original PDF par exécution et publient une copie distincte dans
/opt/vigil/rapports.

Les anciennes données utilisateur ne sont pas déplacées automatiquement.
Fermer toutes les sessions Vigil et leurs scripts, sauvegarder les deux
arbres et vérifier si les deux contiennent déjà une base cases.sqlite.
S’il existe deux bases, choisir laquelle ouvrir pour organiser la
migration des affaires. Ne pas superposer les deux. Si le dossier cible
ne contient aucune donnée de travail, copier l’arbre d’état utilisateur
vers /opt/vigil/data/state. Qt reprend la langue de l’ancienne configuration
au premier démarrage si le nouveau fichier de préférences est absent.

L’accès RDP est proposé pendant l’installation et désactivé par défaut.
Après installation, terminer les réglages KDE décrits dans `post-install-checked.txt`
à la racine du dépôt, puis [configurer l’entité et les utilisateurs](../configuration/systeme.md).

## Mettre à jour les lanceurs d’une installation existante

Fermer Vigil, puis lancer depuis la session opérateur.

```bash
cd /opt/vigil
git pull --ff-only
bash scripts/post-install/update-cli.sh
hash -r
command -v vigil vigil-tui
vigil --version
vigil --help
```

Cette mise à jour réinstalle le paquet, prépare les lanceurs reconnus et réapplique l’accès FreshClam au dossier de signatures du site.
Un conflit de commande est signalé avec son chemin. Le détail des
emplacements gérés, du retour arrière et des raccourcis personnalisés
figure dans [la transition CLI](../development/cli-command-transition.md).

## Lancer le workspace Textual

Sur un poste Parrot déjà installé dans `/opt/vigil`, fermer les sessions et
mettre à jour les lanceurs avec la procédure précédente. Le script publie
`/usr/local/bin/vigil-tui` et installe les dépendances dans le venv du site.
Lancer ensuite `vigil`, `vigil tui` ou `vigil-tui` depuis un terminal local
ou une session SSH interactive. Ces trois commandes ouvrent la même TUI
supervisée. `vigil-gui` et `vigil gui` ouvrent Qt.

La TUI utilise la base du site et se lance depuis le compte opérateur.
Les opérations privilégiées demandent une autorisation dans le terminal
intégré. Options utiles : `vigil-tui --lang en` pour l’anglais et
`vigil-tui --db /chemin/vers/vigil-dev.sqlite` pour une base de test.

La [matrice de parité](../development/tui-parity.md) détaille les parcours
raccordés et les recettes encore ouvertes.

## Modifications du poste

- Installation des paquets de `scripts/post-install/requirements.txt`.
- Création de `/investigation`, `/stockage` et des dossiers de données, journaux et rapports.
- Désactivation du montage automatique et masquage d’`udisks2`.
- Initialisation des données. L’administrateur vérifie la politique sudo du poste.
- Création de la commande `vigil`, du raccourci et des emplacements Dolphin.
- Configuration de l’accès FreshClam aux signatures sous /opt/vigil. La mise à jour est lancée depuis Qt.
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
