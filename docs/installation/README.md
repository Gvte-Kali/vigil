---
layout: default
title: Installation
nav_order: 50
has_children: true
parent: Français
---

# Installer Vigil

Cette page décrit les procédures connues pour **`main`**, avec une GUI Qt comme parcours utilisateur principal. Les installations système qui manipulent les périphériques requièrent un administrateur et sont à réaliser d'abord dans une VM de test.

## Installation complète (Debian / Parrot)

Prérequis : compte utilisateur avec sudo, Python 3.11+, connexion Internet, espace disque suffisant. Sauvegardez vos affaires et testez d'abord dans une VM. Fermez les opérations et débranchez les supports après restitution.

```bash
sudo apt-get update
sudo apt-get install -- git python3
sudo mkdir -- /opt/vigil
sudo chown -- "$(id -u):$(id -g)" /opt/vigil
git clone --branch main --single-branch https://github.com/Gvte-Kali/vigil.git /opt/vigil
cd /opt/vigil
install -d -m 0700 logs rapports
bash scripts/post-install/post_install_vigil.sh --skip-apt-update
```

Le script configure les dépendances, Python, les zones de montage, udev, FreshClam et les lanceurs. Le journal est indiqué à l'écran. Pour examiner le plan sans installer, utilisez `--dry-run` à la place de `--skip-apt-update`.

```bash
hash -r
vigil doctor
vigil gui
```

## Raccourci bureau

Le post-install crée automatiquement `Vigil.desktop` dans le bureau XDG de l’opérateur, avec le logo officiel et un lancement GUI sans terminal intermédiaire. Aucun raccourci n’est créé si le bureau XDG est absent ou invalide. Un raccourci tiers existant est conservé.

Pour actualiser ou créer le raccourci sur une installation existante, sans réinstaller :

```bash
cd /opt/vigil
source scripts/lib/vigil-launchers.sh
vigil_install_desktop_shortcut
```

La GUI et la TUI ouvrent un terminal indépendant de bilan à la fermeture normale ; vérifiez la restitution USB et les montages résiduels avant de retirer les supports.

## Désinstaller

Fermez Vigil, sauvegardez les affaires et démontez les supports. Examinez le plan :

```bash
cd /opt/vigil
bash scripts/post-install/uninstall.sh --dry-run
bash scripts/post-install/uninstall.sh --keep-data
```

Le mode `--purge` supprime définitivement les données après confirmation. Les dépendances sont conservées par défaut ; `--purge-dependencies` est expérimental. Voir [désinstallation et restauration](desinstallation.md). Le désinstallateur reste à valider en VM.

## Démarrer les interfaces

- `vigil gui` / `vigil-gui` : GUI Qt, parcours principal.
- `vigil tui` / `vigil-tui` : interface terminal Textual, testée interactivement sous Parrot OS ; validation forensique complète en cours.
- `vigil` : aide CLI.
- `vigil doctor` : diagnostic des dépendances.

Une installation de site utilise normalement `/opt/vigil/data/state`. En développement, Vigil peut utiliser les chemins XDG. Si plusieurs `cases.sqlite` existent, **ne les superposez pas** : sauvegardez et vérifiez leur provenance.

## Mettre à jour une installation existante

Fermer Vigil et les opérations actives, vérifier que les supports sont démontés et sauvegarder les données, puis :

```bash
cd /opt/vigil
git pull --ff-only
bash scripts/post-install/update-cli.sh
hash -r
vigil doctor
```

L'outil met à jour les lanceurs et la configuration autorisée de FreshClam. Un conflit de lanceur doit être examiné, pas écrasé.

## Erreurs et restauration

Si l'installateur signale `/etc/sudoers.d/vigil`, **ne supprimez pas de règle à l'aveugle**. Depuis un compte administrateur indépendant :

```bash
sudo visudo -c
sudo cat -- /etc/sudoers.d/vigil
```

L'administrateur doit sauvegarder et migrer les règles utiles, puis valider `visudo -c`. En cas de retour arrière, suivez la [procédure de remise à zéro avec sauvegarde](desinstallation.md).

## Premier lancement

[Ma première investigation](../getting-started.md) · [ClamAV](../configuration/clamav.md) · [Compatibilité](../compatibility.md).

## Choix de la langue

L'installateur et le désinstallateur demandent au démarrage **Français** ou **English** pour les messages, étapes, confirmations et erreurs propres à Vigil. Sans terminal interactif, ils utilisent `VIGIL_LANG` ou la langue du système. Les sorties brutes d'APT et des outils tiers restent inchangées. Les opérations de montage et d'analyse lancées depuis la GUI/TUI utilisent la langue sélectionnée dans l'interface, indépendamment de la langue choisie lors de l'installation.
