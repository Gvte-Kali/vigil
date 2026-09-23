---
layout: default
parent: "Analyse"
title: "Orchestrateur"
nav_order: 263
---

# 🎼 Orchestrateur de scans — `vigil_scan_all.sh`

> `scripts/vigil_scan_all.sh` lance **l'intégralité des analyses forensiques** en
> une seule commande, dans un ordre fixe.

---

## 📖 En résumé

L'orchestrateur enchaîne toutes les analyses disponibles (recensement,
antivirus, images, vidéos, audio, bureautique, archives, fichiers verrouillés,
forte entropie, fichiers volumineux), chaque analyse générant son propre
rapport PDF. Les scripts sont lancés de façon **indépendante** : l'échec
d'une analyse n'interrompt pas les suivantes. Un **bilan global** est affiché
à la fin.

La **chaîne de custody** est gérée par chaque script individuel (dans le
dossier du projet), pas par l'orchestrateur. Les analyses de fichiers
exigent un projet actif ; le scan antivirus (ClamAV) reste l'exception
(sans custody, sans projet).

---

## 📋 Ordre des analyses

1. **Recensement des fichiers** (`vigil_census.sh`) — inventorie tous les
   fichiers et alimente la base SQLite du projet (exige un projet actif).
2. Antivirus (ClamAV) — mode non-interactif (`--all --yes --comment ""`),
   sans custody.
3. Fichiers image
4. Fichiers vidéo
5. Fichiers audio
6. Fichiers bureautiques
7. Fichiers archives
8. Fichiers verrouillés (crypto)
9. Fichiers à forte entropie
10. Fichiers volumineux

## ⚙️ Options

| Option | Effet |
|---|---|
| `--pdf` | forcer la génération des rapports PDF (défaut) |
| `--no-pdf` | désactiver la génération des rapports PDF |

## 🔧 Prérequis

- Un **utilisateur** actif doit être sélectionné (obligatoire).
- Un **projet** est optionnel (`(no-project)` si aucun).
- Le périphérique doit déjà être **monté** dans `/investigation/`.

## 🛠️ Fonctionnement

- Chaque analyse reçoit une **entrée vide** pour satisfaire son `read` final
  sans bloquer la chaîne.
- La sortie et le code retour de chaque script sont capturés.
- Un **bilan** récapitule le nombre d'analyses lancées, réussies et en erreur.
- Les rapports PDF (si activés) sont disponibles dans `/opt/vigil/rapports/`.

## 🔗 Voir aussi

- [Montage en lecture seule](montage-lecture-seule.md)
- [Générateur PDF](../rapports-pdf/README.md)
