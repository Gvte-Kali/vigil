---
layout: default
title: Compatibilité et versions
nav_order: 6
parent: Français
---

# Compatibilité et état du projet

Cette page décrit **les validations documentées**, pas une garantie universelle.

| Sujet | État |
|---|---|
| Branche de référence publique | `main` |
| Interface Qt | Parcours principal documenté |
| Interface Textual | **Expérimentale, non fonctionnelle actuellement ; ne pas utiliser en investigation** |
| Debian, Parrot et dérivés | Famille principale de tests |
| Arch / Omarchy, Fedora, openSUSE | Objectifs de portabilité, à valider selon le parcours |
| SSH sans interface graphique | CLI technique selon les commandes disponibles ; TUI non fonctionnelle |
| Acquisition matérielle | Nécessite des protections et recettes adaptées au périphérique |

## Référence développeur

La branche `vigil-2.0` contient des travaux en cours et ne doit pas être confondue avec un produit stabilisé. Consultez la [recette native](development/native-recette.md) et la [matrice technique](development/compatibility-matrix.md) pour les écarts et scénarios de test.

## Signaler une incompatibilité

Précisez la branche et le commit, la distribution, le noyau, Wayland/X11 ou le compositeur, le parcours effectué, le résultat attendu, le résultat observé et des journaux expurgés de données sensibles. [Ouvrir une issue GitHub](https://github.com/Gvte-Kali/vigil/issues).
