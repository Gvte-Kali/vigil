---
layout: default
title: Installation
nav_order: 50
---

# Installation

Vigil s’installe sur les postes Linux utilisant udev et systemd, avec `apt`
(Debian, Ubuntu, Kali, Parrot), `dnf` (Fedora et dérivés RHEL) ou `pacman`
(Arch et dérivés). Sur RHEL, certains paquets nécessitent EPEL et, selon la
version, CodeReady Builder ou CRB. Sur Arch, synchroniser et mettre à jour
le système avec `pacman -Syu` avant l’installation.

## Installer et lancer

Placer le dépôt dans `/opt/vigil`, puis exécuter depuis le compte opérateur :

```bash
cd /opt/vigil
sudo bash scripts/post-install/post_install_vigil.sh
vigil
```

L’installateur configure les dossiers de travail, le raccourci, la règle udev
et les droits sudo du compte opérateur. Ce compte doit être administrateur.
L’accès RDP est proposé pendant l’installation interactive via `apt` et
reste facultatif. Après installation, [configurer l’entité et les utilisateurs](../configuration/systeme.md).

L’interface Tkinter utilise X11 ou XWayland. Les actions interactives
s’ouvrent dans le terminal par défaut de la session. Vigil utilise le réglage
de Plasma ou de Xfce lorsqu’il est accessible, puis le lanceur
`xdg-terminal-exec` ou l’alternative `x-terminal-emulator` de Debian.
L’installateur propose `xdg-terminal-exec` si le paquet est disponible.

Sur une session minimale, définir le terminal préféré dans
`${XDG_CONFIG_HOME:-$HOME/.config}/xdg-terminals.list` avec son identifiant
`.desktop`. Si la session ne propose pas de lanceur compatible, on peut
aussi définir `VIGIL_TERMINAL` avec le chemin du lanceur et les options
requises pour exécuter une commande. Par exemple, pour un terminal qui
accepte l’option `-e`, utiliser `VIGIL_TERMINAL='mon-terminal -e' vigil`.

La protection udev s’applique indépendamment du bureau et du gestionnaire
de fenêtres.

## Protection des supports

Lancer Vigil **avant** de brancher les supports. Pendant que l’interface est
ouverte, udev demande au noyau de mettre en lecture seule les nouveaux
périphériques bloc USB et MMC/SD et demande à UDisks de les ignorer.
Cela empêche notamment Plasma d’automonter ces supports. Les supports déjà
branchés gardent leur état. Après la fermeture, les prochains branchements
suivent le comportement habituel du système. Rebrancher les supports déjà
protégés hors session Vigil pour retrouver leur comportement habituel.

L’action **Périphérique de stockage** autorise l’écriture sur le support
sélectionné pour le monter dans `/stockage`. Pour une partition, elle doit
aussi rendre le disque parent inscriptible. Les autres partitions protégées
restent en lecture seule. Le démontage depuis Vigil réapplique la protection.
Un support protégé ne peut pas servir de cible brute de clonage. Pour exporter
une image, utiliser un dossier sur le support monté via **Stockage**.

Les appareils MTP suivent le flux de montage MTP de Vigil, car ils ne sont
pas des périphériques bloc. Un automonteur indépendant d’UDisks peut encore
tenter un montage. Vérifier l’état du support avec `lsblk -o NAME,TRAN,RO,MOUNTPOINTS`
et les erreurs éventuelles avec `journalctl -t vigil-usb`.

### Migration depuis une ancienne installation

Si l’ancien installateur de Vigil a masqué UDisks, réactiver le service pour
retrouver le montage de bureau hors session Vigil :

```bash
sudo systemctl unmask udisks2.service
sudo systemctl start udisks2.service
```

## Dépendances

La liste `scripts/post-install/requirements.txt` indique les noms par
gestionnaire de paquets. Une dépendance facultative absente est signalée.
Les fonctions correspondantes, comme MTP ou certains formats d’imagerie,
dépendent des paquets disponibles dans les dépôts activés.

| Fonction | Debian (`apt`) | Fedora (`dnf`) | Arch (`pacman`) |
|---|---|---|---|
| Tkinter | `python3-tk` | `python3-tkinter` | `tk` |
| Pillow/Tk | `python3-pil.imagetk` | `python3-pillow-tk` | `python-pillow` |
| ExifTool | `libimage-exiftool-perl` | `perl-Image-ExifTool` | `perl-image-exiftool` |
| FFmpeg | `ffmpeg` | `ffmpeg-free` | `ffmpeg` |
| FreshClam | `clamav-freshclam` | `clamav-freshclam` | `clamav` |

Sources des noms de paquets : [Debian](https://packages.debian.org/stable/),
[Fedora et EPEL](https://packages.fedoraproject.org/), [Arch Linux](https://archlinux.org/packages/).

## Développement local

Depuis la racine du dépôt :

```bash
VIGIL_BASE="$PWD" VIGIL_DATA_DIR="$PWD/data" python3 gui/vigil_main_gui.py
```

Ce lancement permet d’examiner l’interface d’une copie locale. La protection
au branchement nécessite une installation dans `/opt/vigil`.
