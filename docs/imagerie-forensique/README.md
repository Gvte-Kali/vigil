---
layout: default
title: "💾 Imagerie forensique"
nav_order: 30
has_children: True
---

# 💾 Imagerie forensique

> Vigil permet de réaliser une **copie forensique** (image disque RAW/E01/AFF)
> ou un **clonage bit-à-bit** d'un disque vers un autre. Dans les deux cas, le
> disque source est **verrouillé en lecture seule** pour garantir l'intégrité
> des preuves.

---

## 📖 En résumé

- **Copie forensique** : on crée un **fichier image** (RAW, E01 ou AFF) d'un
  disque source, vers un disque cible externe ou un emplacement local, avec
  choix du **nom** de l'image, du **dossier de destination**, et calcul d'un
  **SHA-256** de contrôle.
- **Clonage** : on copie **secteur par secteur** un disque source vers un
  disque cible (qui est **entièrement écrasé**), avec protection anti-
  dépassement de taille, et réparation optionnelle des partitions.

---

## 🗺️ Sommaire

- [Copie forensique d'un disque](copie-forensique.md) — `vigil_disk_imager.sh`
- [Clonage bit-à-bit](clonage.md) — `vigil_disk_clone.sh`

---

## 🔒 Principes communs

- **Lecture seule stricte** : le disque source est verrouillé au niveau bloc
  (`sudo blockdev --setro`) et son état RO est **vérifié** avant de continuer.
  Si le verrouillage échoue, le script **abandonne** (sécurité forensique).
- **`sudo`** : l'accès aux devices `/dev/` nécessite les privilèges root ;
  le mot de passe est demandé au lancement.
- **Disques internes exclus** : les disques système internes ne sont pas
  proposés comme source.
- **Bannière ASCII** « VIGIL » + `clear` entre chaque étape.
