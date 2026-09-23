---
layout: default
parent: "Actions"
title: "Stockage"
nav_order: 23
---

# 📁 Stockage

> Le **stockage** est un montage en **lecture/écriture** d'un périphérique dans
> `/stockage`, destiné aux **fichiers de travail** — **pas** à l'analyse
> forensique.

---

## 📖 En résumé

Pour analyser un périphérique (lecture seule), il faut utiliser le menu
**« Analyse du périphérique USB »** (`vigil_usb_mount.sh`). Le menu **Stockage**
monte un périphérique en **lecture/écriture** dans `/stockage` pour déposer ou
récupérer des fichiers de travail. Une pop-up d'avertissement le rappelle à
l'ouverture de la page.

---

## 🗂️ Scripts

| Script | Rôle |
|---|---|
| `scripts/stockage/vigil_stockage_mount.sh` | Monte un périphérique en lecture/écriture dans `/stockage` |
| `scripts/stockage/vigil_stockage_umount.sh` | Démonte les périphériques de `/stockage` |

## 👤 Sélection de l'utilisateur

`vigil_stockage_mount.sh` demande l'utilisateur **avant** le triage :
écran « === Utilisateur === » listant les profils de la GUI
(`data/users/`), avec `[q] Quitter`. Le choix est persisté dans
`data/active_user` — la custody et la GUI restent synchronisées. Sans
utilisateur configuré, le script s'arrête (à créer via la GUI).

## 🦆 Triage USB anti-Rubber Ducky

`vigil_stockage_mount.sh` applique la **même procédure de triage** que
l'analyse forensique (`vigil_usb_mount.sh`) **avant** la sélection du
périphérique à monter :

- demande de débrancher les périphériques, **baseline USB**, branchement,
  décompte de 10 s avec barre de progression (purge du tampon clavier) ;
- **blocage par défaut** des claviers HID apparus au branchement
  (unbind `usbhid`) — un stockage de travail ne se présente jamais en
  clavier ;
- whitelist / blacklist persistantes (`data/usb/whitelist.txt` /
  `blacklist.txt`) partagées avec la GUI « Périphériques USB » ;
- rapport PDF de triage (`rapport_usbhid_*`) généré systématiquement ;
- si le seul périphérique détecté est un ducky bloqué ou un périphérique
  blacklisté : fin propre du script (rien à monter) ;
- un périphérique bloqué au triage n'est jamais ré-autorisé par le retry
  `authorized=0`.

## 🔗 Voir aussi

- [Analyse forensique](analyse.md) — montage lecture seule pour l'analyse
