---
layout: default
parent: "Configuration"
title: "Périphériques USB"
nav_order: 13
---

# 🔌 Périphériques USB

> Bouton **« Périphériques USB »** de la section Configuration —
> page `gui/vigil_usb_gui.py`.

---

## 📖 En résumé

Inventaire des périphériques USB **connectés** et gestion des listes
**whitelist / blacklist** du triage anti-Rubber Ducky. Ces listes sont
persistantes (`data/usb/whitelist.txt` / `blacklist.txt`) et partagées
avec le triage de **tous** les montages (analyse, stockage, recherche de
menaces).

---

## 🖥️ La page

- **Inventaire connecté** : port, fabricant/produit, `VID:PID`, n° de
  série, interface clavier (oui/non), statut
  **Whitelisté / Blacklisté / Non listé**.
- Bouton **Whitelister (confiance)** : ajoute le périphérique à la
  whitelist (par `VID:PID` ou n° de série) — un clavier whitelisté
  n'est **jamais bloqué** au triage.
- Bouton **Blacklister (suspect)** : ajoute à la blacklist — le
  périphérique est bloqué d'office au niveau noyau (`authorized=0`),
  même non-HID, invisible de `lsblk`, non montable.
- **Tableaux des listes** avec boutons Ajouter / Retirer / Enregistrer
  (édition manuelle des entrées `VID:PID` ou n° de série).

---

## 🛡️ Rôle dans le triage

Le [triage USB](../actions/montage-lecture-seule.md#-triage-usb-anti-rubber-ducks)
de chaque montage compare les périphériques apparus au branchement à ces
listes :

1. clavier HID **whitelisté** → jamais bloqué (clavier de travail) ;
2. périphérique **blacklisté** → bloqué immédiatement, rapport de triage
   « Blacklisté — bloqué », fin propre si c'est le seul périphérique ;
3. clavier HID **non listé** apparu au branchement → **bloqué par
   défaut** (unbind `usbhid`) — c'est le comportement attendu pour un
   Rubber Ducky.

**Cas d'usage typique** : un clavier de travail débranché pendant la
baseline du triage puis rebranché serait bloqué comme « nouveau ». Pour
l'éviter, l'ajouter **une fois** via cette page — il reste ensuite
pleinement fonctionnel à chaque montage.

---

## 🔗 Voir aussi

- [Montage lecture seule](../actions/montage-lecture-seule.md) — le triage détaillé
- [Stockage](../actions/stockage.md) — même triage, montage lecture/écriture
