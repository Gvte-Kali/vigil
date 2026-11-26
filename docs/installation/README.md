---
layout: default
title: Installation
nav_order: 50
has_children: true
---

# Installer Vigil

Cette page décrit les procédures connues pour **`main`**, avec une GUI Qt comme parcours utilisateur principal. Les installations système qui manipulent les périphériques requièrent un administrateur et sont à réaliser d'abord dans une VM de test.

## Quel mode choisir ?

| Mode | Public | Modifications |
|---|---|---|
| **Développement utilisateur** | Essayer la GUI, les affaires et les données de démonstration | Venv et fichiers locaux ; pas de configuration de montage privilégié |
| **Installation de site** | Poste Debian/Parrot dédié aux opérations forensiques | Paquets APT, `/opt/vigil`, lanceurs, règles udev et protections contrôlées |
| **Autres Linux** | Développeurs et testeurs | Recette `install_native.py --dry-run` ; opérations matérielles à valider |

## Prérequis

- Debian, Parrot ou dérivé pour l'installation de site documentée.
- Compte utilisateur ordinaire avec `sudo` pour les modifications système.
- Git, Python **3.11+**, espace disque suffisant et une sauvegarde des affaires existantes.
- Support de test pour la première recette ; ne pas utiliser de preuve irremplaçable.

## Essayer la GUI sans post-installation

Dans un dossier utilisateur :

```bash
git clone --branch main https://github.com/Gvte-Kali/vigil.git
cd vigil
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[desktop]'
.venv/bin/vigil doctor
.venv/bin/vigil-gui
```

Cette installation **ne configure pas** les protections système, les règles udev ou les zones de montage privilégiées. Les opérations matérielles nécessitant ces composants peuvent être indisponibles. Pour des tests sans privilèges et avec des fixtures, voir la [recette native](../development/native-recette.md).

## Installation de site sur Debian/Parrot

**Attention : cette procédure modifie le système.** Faites-la d'abord dans une VM avec instantané. Vérifiez le plan avant de confirmer l'installation.

```bash
sudo apt-get update
sudo apt-get install -- git python3
sudo mkdir -- /opt/vigil
sudo chown -- "$(id -u):$(id -g)" /opt/vigil
git clone --branch main --single-branch https://github.com/Gvte-Kali/vigil.git /opt/vigil
cd /opt/vigil
install -d -m 0700 logs rapports
bash scripts/post-install/post_install_vigil.sh --dry-run
```

Après examen du plan APT, des modifications système, de vos sauvegardes et des règles sudoers éventuelles :

```bash
bash scripts/post-install/post_install_vigil.sh
hash -r
vigil --version
vigil doctor
vigil gui
```

Le post-install prépare `/opt/vigil/.venv`, `/investigation`, `/stockage`, les lanceurs, les règles udev et l'intégration FreshClam/AppArmor lorsque pertinente. Les paquets ajoutés par APT sont consignés dans `/opt/vigil/data/apt-installed-by-vigil.txt`.

## Démarrer les interfaces

- `vigil gui` / `vigil-gui` : GUI Qt, parcours principal.
- `vigil` / `vigil tui` / `vigil-tui` : lanceurs expérimentaux de la TUI, **non fonctionnelle actuellement**. Utiliser `vigil gui` pour les investigations.
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
