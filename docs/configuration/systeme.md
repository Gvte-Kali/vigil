---
layout: default
parent: Configuration
title: Système et utilisateurs
nav_order: 11
---

# Système et utilisateurs

Depuis l’accueil, ouvrir **Configuration du système**.

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
