---
layout: default
parent: Configuration
title: Mise à jour ClamAV
nav_order: 14
---

# Mise à jour ClamAV

Depuis **Mettre à jour l’antivirus ClamAV**, choisir le mode de mise à jour.
Les opérations s’exécutent dans Konsole.

## Poste connecté

Lancer le mode **En ligne**. Le script `scripts/clamav/vigil_clamav_update.sh`
arrête temporairement `clamav-freshclam`, exécute `freshclam`, redémarre le service
et affiche les versions des bases installées.

## Poste isolé

1. Préparer les bases `.cvd` sur un poste connecté.
2. Choisir **Par clé USB** et suivre le triage USB.
3. Sélectionner le support contenant les bases.
4. Laisser le script monter le support en lecture seule, copier les bases dans le répertoire ClamAV et démonter le support.
5. Vérifier les versions affichées.

Script : `scripts/clamav/vigil_clamav_update_usb.sh`.

La mise à jour des signatures est distincte du [scan antivirus](../actions/antivirus.md).
