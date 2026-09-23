---
layout: default
parent: "Actions"
title: "Clonage"
nav_order: 25
---

# 📋 Clonage bit-à-bit — `vigil_disk_clone.sh`

> `scripts/imager/vigil_disk_clone.sh` copie le **contenu intégral** d'un disque
> source vers un disque cible, **secteur par secteur**, via `dc3dd` (fallback
> `dd`). Le disque cible est **entièrement écrasé**.

---

## 📖 En résumé

On choisit un disque source (verrouillé en lecture seule) et un disque cible
dont on **vérifie la taille** (elle doit être ≥ au disque source, sinon
abandon pour éviter un dépassement). La copie se fait bit-à-bit avec calcul
d'un **SHA-256**. Si de l'espace non assigné reste sur la cible, le script
propose de **réparer/étendre les partitions** (sgdisk, growpart, resize2fs).

---

## 🔄 Déroulement (4 étapes)

1. **Sélection du disque source** (disques USB/externes, détails enrichis) +
   **verrouillage lecture seule** (`blockdev --setro`) + vérification RO.
2. **Sélection du disque cible** + **vérification de taille**
   (cible ≥ source, sinon abandon) + **déverrouillage** de la cible en
   lecture/écriture.
3. **Clonage** bit-à-bit via `dc3dd` (avec `hash=sha256`), fallback `dd` si
   `dc3dd` absent.
4. **Réparation optionnelle des partitions** :
   - correction de la table GPT via `sgdisk -e` ;
   - extension de la partition via `growpart` + `resize2fs` (ext) ;
   - fallback `parted`/`fdisk` si `sgdisk` absent.

## 🛡️ Sécurités

- **Anti-dépassement** : la taille de la cible doit être ≥ à celle du source.
- **Lecture seule source** : verrouillage bloc + vérification RO=1.
- **Cible écrasée** : avertissement explicite avant l'opération.
- `sudo` requis pour l'accès aux devices.

## 🔗 Voir aussi

- [Copie forensique d'un disque](copie-forensique.md)
- [Interface graphique](../interface-graphique/README.md)
