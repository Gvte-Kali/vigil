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
**whitelist / blacklist** du triage anti-Rubber Ducky (par `VID:PID` ou
n° de série). Ces listes sont persistantes (`data/usb/whitelist.txt` /
`blacklist.txt`) et partagées avec le triage du montage
([Analyse forensique](../actions/analyse.md#-montage-en-lecture-seule)).

Un clavier HID whitelisté n'est **jamais bloqué** au triage ; un clavier
non whitelisté apparu au branchement est bloqué (unbind `usbhid`).
