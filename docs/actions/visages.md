---
layout: default
parent: Analyse
title: Détection visages
nav_order: 274
grand_parent: Actions
---

# Détection des visages

Repérer les images susceptibles de contenir des visages, sans identifier les personnes.

## Utilisation

Activer `--faces` dans l’[analyse des images](images.md).
Utiliser `--copy-faces-to DIR` pour conserver une copie des images retenues.

Le script `scripts/analyse/vigil_faces_detection.sh` reçoit le dossier de travail
et la liste TSV des images. Il privilégie `facedetect`, puis utilise OpenCV (`cv2`)
en secours. Il produit `faces_result.json` dans le dossier d’analyse.

## Limites

- Les images trop petites (au plus 8192 pixels carrés) sont écartées.
- Le détecteur peut manquer des visages ou produire de faux positifs.
- Sans `facedetect` ni OpenCV, cette étape est désactivée ; l’analyse des images continue.
