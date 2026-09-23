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
(organisme) et des **utilisateurs** rattachés, plus un **logo** affiché sur
les rapports.

Avant d'analyser un périphérique, on configure une fois l'**entité** (nom de
l'organisme, établissement, adresse, téléphone, email, logo) et on crée au
moins un **utilisateur** (obligatoire pour logger les actions via la chaîne
de custody).

---

## 🗂️ Champs de l'entité

| Champ | Usage |
|---|---|
| Nom de l'entité | Page de garde des rapports PDF |
| Établissement | Page de garde des rapports PDF |
| Adresse / téléphone / email | Coordonnées sur les rapports |
| Logo | Miniatures sur la GUI et la page de garde des rapports |
