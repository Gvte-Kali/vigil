---
layout: default
parent: Analyse
title: Démontage
nav_order: 262
grand_parent: Actions
---

# Démontage

Le bouton **Démonter** de la page d’analyse lance
`scripts/analyse/vigil_usb_umount.sh` dans Konsole.
Il traite **tous les montages actifs** sous `/investigation`.

## Déroulement

1. Recalculer le hash d’arbre et le comparer à celui du montage, s’il est disponible.
2. Signaler les écarts d’intégrité ; l’écart est tracé et le démontage continue.
3. Démonter chaque partition.
4. Relâcher le verrou bloc avec `blockdev --setrw`.
5. Supprimer les points de montage vides et afficher le bilan.

Attendre le bilan avant de débrancher le support. Un hash initial absent entraîne
un avertissement : aucune comparaison d’intégrité n’est alors possible.

L’opération fonctionne sans contexte actif ; les événements sont inscrits dans
le journal du projet ou de la chasse lorsqu’un tel journal est disponible.
Le support n’est plus protégé par le verrou logiciel après sa remise en lecture/écriture.

Voir [Montage en lecture seule](montage-lecture-seule.md).
