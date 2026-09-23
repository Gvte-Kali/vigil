---
layout: default
parent: "Configuration"
title: "Projets"
nav_order: 12
---

# 📁 Projets

> Bouton **« Gérer les projets »** de la section Configuration —
> page `gui/vigil_project_manager.py`.

---

## 📖 En résumé

Les **projets** sont globaux (non liés à un utilisateur) mais un
utilisateur doit être sélectionné pour logger la chaîne de custody. Un
projet actif est **obligatoire** pour lancer une analyse de fichiers
(exception : le scan antivirus et la
[recherche de menaces](../actions/menaces.md) restent autonomes).

---

## 🗂️ Gestion des projets

La page liste les projets existants avec boutons **Créer** /
**Modifier** / **Exporter** / **Supprimer**. Le dialogue de création
demande :

| Champ | Détail |
|---|---|
| Nom du projet * | Obligatoire, unique |
| Description | Optionnelle |

Chaque projet vit dans `data/projects/<projet>/` :
`chain_of_custody.log`, base SQLite du recensement, exports TSV,
rapports copiés, hashes par device.

---

## 🎬 Workflow type

```text
[Bouton GUI] Gérer les projets
    └─ [Créer] → nom + description
    └─ sélection du projet dans la barre des pages d'analyse
         └─ toutes les analyses de fichiers l'exigent (custody)
    └─ [Exporter] → vigil_export_project.sh :
         ├─ SHA-256 de chaque fichier du dossier projet
         ├─ archive tar.gz du dossier
         └─ SHA-256 de l'archive (vérifiable à réception)
    └─ [Supprimer] → suppression du dossier projet (confirmation)
```

L'**export** est journalisé dans la chaîne de custody du projet (début,
succès avec le hash de l'archive, ou erreur) — voir
[Export du projet](../actions/export.md).

---

## 🔗 Voir aussi

- [Système et utilisateurs](systeme.md)
- [Export du projet](../actions/export.md)
- [Analyse](../actions/analyse.md) — le projet actif en pratique
