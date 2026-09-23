---
layout: default
title: "Installation"
nav_order: 50
has_children: True
---

# 📦 Installation
> L'installation se fait via le **script de post-installation**
> `scripts/post-install/post_install_vigil.sh`, qui crée les répertoires,
> installe les dépendances, configure le système et crée la commande `vigil`.

---

## 📖 En résumé

On copie le projet sous `/opt/vigil`, puis on lance le script de post-install
en tant que root. Il crée `/investigation` et `/stockage`, installe toutes les
dépendances (depuis `requirements.txt`), propose l'accès RDP (interactif,
désactivé par défaut), désactive le montage automatique des USB (udisks2 +
purge usbguard), met en place les permissions, initialise les données, crée le
**lien symbolique `vigil`**, configure les règles `sudo` (NOPASSWD), crée le
raccourci bureau et les emplacements Dolphin, et met à jour ClamAV.

---

## 🚀 Démarrage rapide

```bash
sudo bash scripts/post-install/post_install_vigil.sh
vigil   # lance la GUI
```

## 📋 Étapes du post-install

1. **Répertoires** : `/investigation`, `/stockage`, `/opt/vigil/{data,scripts,logs,rapports}`.
2. **Dépendances** : installation depuis `requirements.txt` (`apt install`).
   Chaque paquet y est commenté (à quoi il sert). Une liste de secours
   synchronisée est intégrée au script au cas où le fichier serait absent.
3. **RDP** : proposé **interactivement** (`o`/`n`, défaut `n`). Si accepté :
   activation de `xrdp` + ouverture du port 3389/tcp (ufw). Sur une station
   locale, répondre `n` — aucun port inutile n'est ouvert.
4. **Montage automatique** : `udisks2` masqué + `auto_mount=false` pour ne pas
   monter les USB automatiquement (garantie forensique).
5. **usbguard** : purgé s'il est présent (sinon il bloque les nouveaux USB).
6. **Permissions** : `/investigation` en 755 pour l'utilisateur.
7. **Données** : création de l'arborescence `/opt/vigil/data/...` + fichiers
   `active_user`, `active_project`.
8. **Commande `vigil`** : lien symbolique
   `/usr/local/bin/vigil → /opt/vigil/gui/vigil_main_gui.py` + `chmod +x`.
9. **`sudo` (NOPASSWD)** : règles sudoers restreintes pour les commandes Vigil
   (mount, filesystem, ClamAV, systemctl, udev, MTP…), validées par `visudo -c`.
10. **Raccourci bureau** : `/usr/share/applications/vigil.desktop` + icône
    (`data/icons/vigil.svg`) installée dans le thème hicolor.
11. **Emplacements Dolphin** : `/investigation`, `/stockage`, `/rapports`
    ajoutés de façon idempotente à `~/.local/share/user-places.xbel`.
12. **ClamAV** : `freshclam` (mise à jour initiale des signatures).

## 📦 Dépendances clés

Voir `scripts/post-install/requirements.txt` (chaque paquet y est commenté).
Principales :

- **Forensique** : `dc3dd`, `ewf-tools`, `afflib-tools` (images RAW/E01/AFF),
  `sleuthkit`/`autopsy` (examen des images produites).
- **Antivirus** : `clamav`, `clamav-daemon`, `clamav-freshclam`.
- **Analyses de fichiers** : `exiftool` (EXIF), `ffmpeg` (ffprobe : durées,
  résolutions), `p7zip-full` (7za : archives chiffrées), `zstd`, `binwalk`
  (audit d'extensions trompeuses), `pv`, `file`.
- **Python** : `python3-tk`, `python3-reportlab` (rapports PDF),
  `python3-cairosvg` (icônes SVG), `python3-pil` (logo/miniatures).
- **Visages** : `facedetect`, `python3-opencv`.
- **USB/MTP** : `jmtpfs` (smartphones), `ntfs-3g`, `exfat-fuse`.
- **Terminal GUI** : `konsole` (lancement des analyses depuis la GUI),
  `kdialog`/`zenity` (dialogues système de l'export des preuves).
- **Réparation partitions (clonage)** : `gdisk` (sgdisk), `cloud-guest-utils`
  (growpart), `parted`, `resize2fs` (e2fsprogs).
- **Papier peint lsblk** : `imagemagick`, `feh`.

## 🔗 Voir aussi

- [Démarrage rapide](../index.md#-démarrage-rapide)
- `post-install-checked.txt` (à la racine) — étapes manuelles KDE restantes
  (bords d'écran, pop-up USB, barre des tâches).
