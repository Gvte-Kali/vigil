---
layout: default
parent: Analyse
title: Montage lecture seule
nav_order: 261
grand_parent: Actions
---

# Montage en lecture seule

Monter un support à examiner dans `/investigation` avec
`scripts/analyse/vigil_usb_mount.sh`.

## Procédure

1. Dans la page d’analyse, sélectionner l’utilisateur et le projet, puis cliquer sur **Monter**.
2. Débrancher les supports à examiner et valider l’état USB de référence ; laisser le clavier de travail branché.
3. Brancher le support et attendre la fin du triage (10 secondes).
4. Choisir le type de périphérique, puis le disque ou la partition affichés.
5. Vérifier le bilan du montage avant de lancer les analyses.

Dans la liste, `r` actualise les périphériques et `q` quitte.

## Protections appliquées

Pour les périphériques bloc, Vigil demande `blockdev --setro` et monte les partitions
avec `ro,noexec,nosuid,nodev,noatime`. Les partitions non montables sont écartées.
Un hash d’arbre est enregistré pour la comparaison au démontage lorsque le contexte le permet.

Le triage bloque les nouveaux claviers HID non autorisés par déliaison du pilote
`usbhid`. Les listes de confiance et de blocage sont gérées dans
[Périphériques USB](../configuration/peripheriques-usb.md). Le triage produit un
rapport PDF, ou une section du rapport consolidé pendant une recherche de menaces.

## Types de supports

- Clés et disques USB : sélection d’une partition ou de tout le disque.
- CD/DVD : montage en lecture seule.
- Téléphones MTP/PTP : accès via les outils MTP ; les protections bloc d’un disque ne s’y appliquent pas.

Ces protections sont logicielles et ne remplacent pas un bloqueur matériel lorsque
la procédure d’acquisition en exige un.

Terminer par le [démontage](demontage.md).
