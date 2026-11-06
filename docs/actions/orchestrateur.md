---
layout: default
parent: Analyse
title: Orchestrateur
nav_order: 263
grand_parent: Actions
---

# Orchestrateur de scans

`scripts/vigil_scan_all.sh` lance une chaîne prédéfinie sur les supports déjà montés
dans `/investigation` et produit **un seul PDF consolidé**.

## Prérequis et lancement

Sélectionner un utilisateur et un projet, puis monter le support avant de lancer :

```bash
bash /opt/vigil/scripts/vigil_scan_all.sh
```

Le script ne bloque pas lui-même l’absence de projet, mais les analyses ciblées
l’exigent et échoueront sans ce contexte.

## Ordre des analyses

Recensement → ClamAV → images → vidéos → audio → bureautique → archives →
fichiers chiffrés → forte entropie → fichiers volumineux.

Chaque analyse est indépendante : un échec n’interrompt pas les suivantes.
Lire le bilan final et les sections en erreur dans le rapport.

## Options et résultats

| Option | Effet |
|---|---|
| `--pdf` | Générer le PDF consolidé (défaut) |
| `--no-pdf` | Ne pas générer le PDF consolidé |

Les résultats intermédiaires alimentent le générateur commun ; les PDF individuels
sont désactivés. Le rapport final est écrit dans `/opt/vigil/rapports/` et copié
dans le projet lorsque son dossier est accessible.

Le multi-scan de l’interface permet aussi de choisir un sous-ensemble d’outils.
Voir [Analyse](analyse.md) et [Rapports PDF](../rapports-pdf/README.md).
