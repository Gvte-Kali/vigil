---
layout: default
parent: Actions
title: Clonage
nav_order: 25
---

# Clonage d’un disque

## Vigil 2.0

Dans **Actions rapides → Acquisition**, choisir **Cloner un disque** ou
**Créer une image RAW**. Les deux actions ouvrent le terminal par défaut
et demandent une authentification sudo.

Le clonage sélectionne deux disques démontés, dont une cible USB. La
confirmation reprend le chemin de la cible. La copie écrase les premiers
octets de la cible sur la longueur exacte de la source. Le SHA-256 est
comparé après relecture de cette même plage.

L’image RAW peut être enregistrée dans un dossier local existant ou sur
une partition USB compatible. Vigil monte temporairement cette partition
dans un espace de montage privé, relit l’image, écrit le fichier
`.raw.sha256` et démonte la partition. Les noms existants sont refusés.

## Vigil 1.0

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
