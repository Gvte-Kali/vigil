---
layout: default
parent: Configuration
title: Système et utilisateurs
nav_order: 11
---

# Système et utilisateurs

Dans la GUI et la TUI, ouvrir **Système → Configuration** dans le menu
latéral. Le menu principal présente **Tableau de bord** sous **Espace de
travail**, puis **Affaire en cours** et **Actions rapides** sous
**Investigation**.

La page Configuration contient trois onglets horizontaux.

- **Entité** regroupe les informations et le logo de l’organisation.
- **Système** affiche la session graphique, les protections et le diagnostic
  des outils, filtrable par disponibilité. Choisir **Automatique** pour
  utiliser le premier terminal compatible détecté. Le choix de terminal
  est partagé entre la GUI et la TUI pour les ouvertures externes.
- **Catalogue de modules** regroupe la recherche, les filtres, le tableau,
  l’inspecteur et la création de modules.

Le tableau de bord conserve les métriques et l’activité de l’affaire,
l’inventaire des disques et l’état des montages.

## Configurer l’entité

1. Saisir le nom de l’entité, l’établissement et les coordonnées.
2. Choisir un logo, si nécessaire ; la page affiche une prévisualisation.
3. Cliquer sur **Enregistrer**.

Ces informations alimentent la couverture des rapports PDF. Le logo est copié dans `data/config/logo/`.

## Gérer les utilisateurs

Ouvrir **Utilisateurs**, puis **Ajouter**, **Modifier** ou **Supprimer**.
Le nom est obligatoire, unique et non modifiable après création.

Chaque profil a le rôle fixe `analyst`. Les profils identifient les opérateurs ;
ils ne définissent pas de permissions d’accès.

| Donnée | Emplacement |
|---|---|
| Profil | `data/users/<nom>/profile.json` |
| Utilisateur actif | `data/active_user` |

Sélectionner l’utilisateur dans la page d’analyse avant de lancer une opération.
Voir aussi [Projets](projets.md) et [Rapports PDF](../rapports-pdf/README.md).
