---
layout: default
parent: "💾 Imagerie forensique"
nav_order: 301
---

# 📋 Copie forensique d'un disque — `vigil_disk_imager.sh`

> `scripts/imager/vigil_disk_imager.sh` réalise une **image forensique** d'un
> disque source vers un disque cible externe ou un emplacement local, au format
> **RAW, E01 ou AFF**.

---

## 📖 En résumé

On choisit le disque source (les disques internes sont exclus), le disque est
**verrouillé en lecture seule**, on choisit le **format** de sortie (RAW/E01/AFF),
le **nom** de l'image et le **dossier de destination**. L'image est créée avec
calcul d'un **SHA-256** de contrôle. Une **confirmation de lecture seule** est
exigée avant l'acquisition.

---

## 🔄 Déroulement (étapes)

1. **Bannière** + vérification des dépendances par format (dc3dd, ewfacquire, afflib).
2. **Sélection du disque source** : disques USB/externes uniquement, avec
   détails (taille, modèle, bus, vendor, série, partitions, FS, état monté).
3. **Verrouillage lecture seule** (`blockdev --setro`) + **vérification RO=1**.
4. `clear` + bannière, **sélection du format** :
   - `[1]` RAW (dc3dd) — `.raw` `.dd` `.img` — copie bit-à-bit sans compression.
   - `[2]` E01 (ewfacquire) — `.E01` (segments `.E02`…) — compression + hash + métadonnées.
   - `[3]` AFF (afflib) — `.aff` `.afd` `.afm` — format ouvert + chiffrement optionnel.
5. **Nom de l'image** (invite), sans extension.
6. **Cible de stockage** :
   - disque cible externe (recommandé), ou
   - emplacement local avec **vérification d'espace stricte** (réserve 20 % du
     disque système pour ne pas le surcharger).
7. **Choix du dossier de destination** (invite système).
8. **Confirmation** de lecture seule, puis **acquisition** (dc3dd/ewfacquire/affcat).
9. **SHA-256** de l'image + **journal** d'acquisition avec métadonnées.
10. **Déverrouillage** du disque source + bilan.

## 📦 Formats gérés

| Format | Outil | Extensions | Logiciels connus |
|---|---|---|---|
| RAW | `dc3dd` | `.raw` `.dd` `.img` | dc3dd, dd, Autopsy, FTK Imager, X-Ways |
| E01 | `ewfacquire` | `.E01` (`.E02`…) | ewfacquire, EnCase, Autopsy, FTK Imager, X-Ways, Magnet AXIOM |
| AFF | `affcat` | `.aff` `.afd` `.afm` | affcat, affuse, Autopsy, Sleuth Kit, aimage |

## 🔒 Garantie d'intégrité

- Le disque source est **verrouillé en lecture seule** et l'état RO est
  **vérifié** avant l'acquisition. En cas d'échec du verrouillage, le script
  abandonne : aucune écriture n'est possible sur le disque source.
- Le **SHA-256** de l'image permet de prouver l'**intégrité** de la copie.
- Le **journal** d'acquisition enregistre les métadonnées (source, dates, etc.).

## 🔗 Voir aussi

- [Clonage bit-à-bit](clonage.md)
- [Interface graphique](../interface-graphique/README.md)
