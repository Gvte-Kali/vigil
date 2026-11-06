---
layout: default
parent: Configuration
title: Projets
nav_order: 12
---

# Projets

Un projet regroupe les résultats d’une analyse et son journal de traçabilité
(`chain_of_custody.log`). Il est partagé entre les opérateurs.

## Créer et utiliser un projet

1. Ouvrir **Gérer les projets** depuis l’accueil.
2. Cliquer sur **Créer** et saisir un nom unique ; la description est facultative.
3. Sélectionner le projet et l’utilisateur dans la page d’analyse.

Le gestionnaire permet aussi de modifier, exporter et supprimer un projet.
La suppression retire son dossier après confirmation.

## Données conservées

Le dossier `data/projects/<projet>/` contient le journal, les empreintes des supports,
le recensement SQLite/TSV et les rapports qui y sont copiés.
Un nouveau recensement remplace le précédent : exporter le projet avant de le relancer si l’ancien doit être conservé.

L’[export](../actions/export.md) produit une archive et des fichiers de contrôle SHA-256.
La [recherche de menaces](../actions/menaces.md) fonctionne séparément, sans modifier de projet.
