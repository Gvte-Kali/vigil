---
layout: default
parent: "Analyse"
nav_order: 214
---

# 🧑 Détection des visages — `vigil_faces_detection.sh`

> `scripts/analyse/vigil_faces_detection.sh` recherche les **visages dégagés et
> de face** parmi les images détectées lors de l'analyse. Il est appelé par
> `vigil_images.sh` via l'option `--faces`.

---

## 📖 En résumé

Le script reçoit le dossier d'analyse et la liste TSV des images produite par
l'analyse des images. Il sélectionne les images suffisamment grandes
(> 8192 px², trop petites = non fiable), tente la détection via **`facedetect`**
(si disponible), sinon fallback via **Python + OpenCV** (`cv2`), et produit un
JSON `faces_result.json` dans le dossier d'analyse.

---

## 🧩 Arguments

| Argument | Rôle |
|---|---|
| `$1` | Dossier d'analyse (`OUTPUT_DIR`) créé par `vigil_images.sh` |
| `$2` | Fichier de liste d'images (TSV : `chemin<TAB>mime<TAB>taille`) |

## 🔄 Déroulement

1. Bannière, vérification des arguments et de la disponibilité d'un détecteur.
2. **Sélection** des images de plus de 8192 px².
3. **Détection** : `facedetect` (prioritaire) ou `python3 + cv2` (fallback).
4. **Production** de `faces_result.json` dans `OUTPUT_DIR`.
5. **Copie** optionnelle des images avec visages (`--copy-to`).

> ⚠️ Si aucun détecteur (`facedetect` ni `cv2`) n'est disponible, la détection
> est désactivée — l'analyse des images se poursuit sans section visages.

## 🔗 Voir aussi

- [Analyse des images](images.md)
- [Générateur PDF](../rapports-pdf/README.md)
