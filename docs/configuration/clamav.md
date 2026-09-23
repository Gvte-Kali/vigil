---
layout: default
parent: "Configuration"
title: "Mise à jour ClamAV"
nav_order: 14
---

# 🧪 Mise à jour ClamAV

> Bouton **« Mettre à jour l'antivirus ClamAV »** de la section
> Configuration — page `gui/vigil_clamav_update_gui.py`.

---

## 📖 En résumé

Mise à jour des **signatures virales** ClamAV, en ligne ou par clé USB
(postes isolés hors réseau).

| Script | Mode |
|---|---|
| `scripts/clamav/vigil_clamav_update.sh` | **En ligne** via `freshclam` (machine connectée) |
| `scripts/clamav/vigil_clamav_update_usb.sh` | **Par clé USB** (postes isolés hors réseau) |

La mise à jour par USB monte le périphérique en lecture seule
(`blockdev --setro`) dans `/stockage`, copie les fichiers `.cvd` (main,
daily, bytecode) dans le `DatabaseDirectory` ClamAV, puis démonte et
rebloque le périphérique.
