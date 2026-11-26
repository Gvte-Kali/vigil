---
layout: default
parent: Configuration
title: Affaires et projets
nav_order: 12
---

# Affaires et projets

Une **affaire Vigil 2.0** regroupe un contexte d'investigation, des preuves, leurs empreintes, les analyses, les rapports et la traçabilité.

## Créer une affaire (GUI Qt)

1. Ouvrir **Investigation → Affaire en cours** puis le gestionnaire d'affaires.
2. Cliquer sur **Créer une affaire** et saisir son nom (et les métadonnées proposées).
3. Sélectionner l'affaire puis l'activer explicitement.
4. Conserver des preuves et consulter les résultats dans les onglets de l'affaire.

La liste des affaires et les actions de création, importation et suppression sont distinctes des actions sur une affaire active.

## Importer et exporter

Pour une archive Vigil 2.0, choisir **Importer → Importer une archive Vigil 2.0** et sélectionner le `tar.gz`. Le contrôle affiche le niveau de couverture et les copies disponibles. Confirmer pour restaurer, puis activer l'affaire.

Pour un projet historique avec `info.json`, utiliser **Importer un ancien projet Vigil 1.0**. Voir [Export](../actions/export.md).

## Projets historiques Vigil 1.0

L'ancien gestionnaire **Gérer les projets** conserve résultats et `chain_of_custody.log` sous `data/projects/<projet>/`. Les projets sont partagés entre opérateurs. Un nouveau recensement peut remplacer les sorties précédentes : exporter avant de relancer si leur conservation est nécessaire.

La [recherche de menaces](../actions/menaces.md) dispose d'un parcours autonome sans affaire.
