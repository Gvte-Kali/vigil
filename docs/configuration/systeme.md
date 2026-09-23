---
layout: default
parent: "Configuration"
title: "Système et utilisateurs"
nav_order: 11
---

# ⚙️ Système et utilisateurs

> Bouton **« Configuration du système »** de la section Configuration —
> page `gui/vigil_config_gui.py`.

---

## 📖 En résumé

La configuration de Vigil est centralisée : une **entité statique unique**
(organisme) et des **utilisateurs** rattachés, plus un **logo** affiché
sur les rapports. Avant d'analyser un périphérique, on configure une fois
l'entité et on crée au moins un utilisateur (obligatoire pour logger les
actions via la chaîne de custody).

---

## 🏢 Entité (page principale)

Le formulaire **« Configuration du système »** rassemble les champs de
l'entité, utilisés sur la **page de garde de tous les rapports PDF** :

| Champ | Usage |
|---|---|
| Nom de l'entité | En-tête des rapports |
| Établissement | En-tête des rapports |
| Adresse / téléphone / email | Coordonnées sur les rapports |
| Logo | Miniature GUI + page de garde des rapports |

- **Choisir un logo** : boîte de dialogue de sélection d'image ; une
  **prévisualisation** s'affiche dans la page (miniature générée par
  PIL).
- **Retirer** : supprime le logo (le champ redevient « (aucun logo) »).
- **Enregistrer** : persiste la configuration statique (le logo est
  copié dans `data/config/logo/`).
- Le bouton **Utilisateurs** ouvre la gestion des utilisateurs
  (page fille).

---

## 👤 Utilisateurs (page fille)

Liste des profils créés, avec boutons **Ajouter** / **Modifier** /
**Supprimer**. Le **dialogue de création/modification** demande :

| Champ | Détail |
|---|---|
| Nom * | Obligatoire, unique (création) ; non modifiable ensuite |

Tous les utilisateurs sont enregistrés avec le rôle fixe `analyst` — Vigil ne
gère **pas de permissions** par utilisateur. Le profil
(`data/users/<nom>/profile.json`) contient le nom, le rôle (`analyst`)
et la date de création.

L'utilisateur actif (`data/active_user`) est utilisé par tous les scripts
pour la chaîne de custody — c'est lui qui apparaît dans les rapports.

---

## 🎬 Workflow type

```text
[Bouton GUI] Configuration du système
    └─ saisie de l'entité (nom, établissement, adresse, tel, email)
    └─ choix du logo (preview)
    └─ [Enregistrer]
    └─ [Utilisateurs]
         └─ [Ajouter] → nom (rôle analyst attribué automatiquement)
         └─ l'utilisateur apparaît dans la barre de sélection des pages
            d'analyse (obligatoire pour la custody)
```

---

## 🔗 Voir aussi

- [Projets](projets.md) — le projet actif, obligatoire pour l'analyse
- [Rapports](../rapports-pdf/README.md) — où l'entité et le logo sont utilisés
