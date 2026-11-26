---
layout: default
title: Installation
nav_order: 50
---

# Installation

Vigil cible un poste dédié sous ParrotOS, avec une base Debian.
Le script de post-installation configure le système et nécessite les droits administrateur.

## Installation native dans un venv utilisateur

L’installateur détecte Debian et ses dérivés, Arch, Fedora et openSUSE.
Pour une validation sans privilèges sur Parrot/Debian ou Arch/Omarchy,
suivre la [recette native GUI et TUI](../development/native-recette.md).

    python3 scripts/post-install/install_native.py --profile complet --dry-run
    python3 scripts/dev/workspace.py setup
    python3 scripts/dev/workspace.py doctor

## Installer et lancer

Sur Parrot/Debian, partir d’un compte opérateur avec sudo, Git et
Python 3.11 ou plus récent. La procédure suivante suppose que `/opt/vigil`
est absent ou vient d’être sauvegardé. Sur un site existant, consulter
[la transition des privilèges](../development/phase-01-transition.md).

```bash
sudo apt-get update
sudo apt-get install -- git python3
sudo mkdir -- /opt/vigil
sudo chown -- "$(id -u):$(id -g)" /opt/vigil
git clone --branch vigil-2.0 --single-branch https://github.com/Gvte-Kali/vigil.git /opt/vigil
cd /opt/vigil
install -d -m 0700 logs rapports
bash scripts/post-install/post_install_vigil.sh --dry-run
bash scripts/post-install/post_install_vigil.sh
hash -r
command -v vigil vigil-gui vigil-tui
vigil --version
vigil --help
vigil doctor
vigil gui
```

Le post-install met à jour les index APT, simule la résolution des paquets,
puis les installe. Il enregistre les paquets nouvellement installés dans
`/opt/vigil/data/apt-installed-by-vigil.txt`. Pour refaire l’installation depuis
zéro, suivre la [procédure de remise à zéro](desinstallation.md).

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

Après installation, [configurer l’entité et les utilisateurs](../configuration/systeme.md).
Dans Actions rapides, lancer la mise à jour des signatures avant le premier
scan. Pendant la recette, ouvrir aussi `vigil tui` et vérifier la protection
et sa restitution à la fermeture avec un support synthétique.

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

- Installation APT des paquets de `scripts/post-install/requirements.txt`, avec les hooks habituels de la distribution.
- Préparation des zones démontées `/investigation` et `/stockage`, et des dossiers de travail.
- Publication des trois lanceurs, du raccourci et de l’icône.
- Installation de l’assistant et de la règle udev. L’autorisation sudo à l’ouverture active la protection des nouveaux périphériques pendant la session.
- Ajout des règles AppArmor ciblées si le profil FreshClam est présent.
- La politique UDisks2, le bureau et l’accès RDP relèvent de l’administration du poste. Sur une machine dédiée, configurer ces options séparément si nécessaire.

Les dépendances système comprennent notamment Chafa et Konsole, les
bibliothèques Qt hôtes, ClamAV, les outils d’imagerie et ReportLab pour les
rapports historiques. PySide6, Textual et les dépendances Core sont installés
par pip dans le venv.

## Développement local

Utiliser la [recette native GUI et TUI](../development/native-recette.md)
pour un venv, des données de test et des fixtures isolés. Le post-install de
site vise la famille Debian. Sur les autres distributions, utiliser
`install_native.py --profile complet --dry-run` pour contrôler le plan
utilisateur et les paquets proposés.
