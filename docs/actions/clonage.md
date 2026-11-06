---
layout: default
parent: Actions
title: Clonage
nav_order: 25
---

# Clonage d’un disque

Copier un disque source secteur par secteur vers un disque cible avec
`scripts/imager/vigil_disk_clone.sh`, depuis **Cloner un disque dur**.

**Le disque cible est entièrement écrasé.** Vérifier modèle, capacité et numéro de
série des deux supports avant de confirmer.

## Procédure

1. Choisir le disque source ; le script vérifie sa protection en lecture seule.
2. Choisir une cible dont la capacité est au moins égale à celle de la source.
3. Confirmer l’écrasement et attendre la fin de la copie.
4. Lire le bilan et les contrôles disponibles selon l’outil utilisé.
5. Si nécessaire, accepter la réparation ou l’extension des partitions sur la cible.

La copie utilise `dc3dd` avec SHA-256, ou `dd` en secours.
La réparation peut utiliser `sgdisk`, `growpart` et `resize2fs` selon le partitionnement.
Elle modifie la cible : conserver une copie intacte si la procédure le demande.

Pour produire un fichier image, voir [Copie forensique](copie-forensique.md).
