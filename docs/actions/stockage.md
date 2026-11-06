---
layout: default
parent: Actions
title: Stockage
nav_order: 23
---

# Stockage de travail

Monter un périphérique **en lecture/écriture** dans `/stockage` pour conserver
les fichiers de travail, les exports ou les bases externes.
Pour examiner une pièce numérique, utiliser le [montage en lecture seule](montage-lecture-seule.md).

## Procédure

1. Ouvrir **Monter un périphérique de stockage** depuis l’accueil.
2. Choisir un utilisateur configuré ; ce choix devient l’utilisateur actif.
3. Suivre le triage USB, puis sélectionner le périphérique.
4. Utiliser le dossier monté sous `/stockage`.
5. Démonter le périphérique depuis cette page avant de le débrancher.

| Script | Rôle |
|---|---|
| `scripts/stockage/vigil_stockage_mount.sh` | Triage USB et montage en lecture/écriture |
| `scripts/stockage/vigil_stockage_umount.sh` | Démontage des supports de stockage |

Le triage partage les [listes USB](../configuration/peripheriques-usb.md) avec
l’analyse et produit un rapport. Un périphérique bloqué n’est pas proposé au montage.
