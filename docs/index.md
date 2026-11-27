---
layout: default
title: Français
nav_order: 1
has_children: true
has_toc: false
---

<div class="vigil-hero" markdown="1">

<p class="eyebrow">Vigil · Documentation utilisateur</p>

# Examinez. Préservez. Documentez.

Vigil est un environnement d'investigation numérique pour Linux : examen des supports, accès en lecture seule, analyse de fichiers, conservation des preuves et rapports PDF.

<span class="vigil-pill">Interface graphique Qt</span><span class="vigil-pill">Preuves et SHA-256</span><span class="vigil-pill">Linux · Debian et dérivés testés</span>

[Commencer en 10 étapes](getting-started.md){: .btn .btn-primary }
[Installer Vigil](installation/README.md){: .btn }

</div>

## Que souhaitez-vous faire ?

<div class="vigil-card-grid">
  <div class="vigil-card"><h3><a href="getting-started.html">Première investigation</a></h3><p>Un parcours guidé de l'ouverture de Vigil jusqu'à l'export d'une affaire.</p></div>
  <div class="vigil-card"><h3><a href="actions/README.html">Découvrir les outils</a></h3><p>Acquisition, montage, recherche de menaces, analyses et rapports.</p></div>
  <div class="vigil-card"><h3><a href="configuration/README.html">Configurer Vigil</a></h3><p>Entité, opérateurs, signatures ClamAV et protections USB.</p></div>
  <div class="vigil-card"><h3><a href="faq.html">Aide et dépannage</a></h3><p>Questions fréquentes, erreurs courantes et bonnes pratiques.</p></div>
</div>

## Comprendre l'essentiel

1. **Source d'investigation :** un support examiné sous `/investigation` avec des protections logicielles de lecture seule.
2. **Affaire :** le contexte qui rassemble opérateur, preuves, analyses et traçabilité.
3. **Preuve conservée :** une copie contrôlée et rattachée à l'affaire, avec une empreinte de référence.
4. **Stockage de travail :** `/stockage`, destiné aux fichiers écrits et aux supports de destination.
5. **Rapports :** les résultats sont consignés en PDF et, selon l'analyse, en SQLite, TSV ou journaux.

## Quelle version est documentée ?

<div class="vigil-note"><strong>Référence : branche <code>main</code>.</strong> La GUI Qt est le parcours utilisateur principal. La TUI Textual est utilisable et a fait l’objet de tests interactifs sous Parrot OS ; sa validation forensique complète reste en cours. Certaines capacités du Core restent en développement ou en recette. Les essais documentés portent principalement sur Debian et ses dérivés. Aucune compatibilité matérielle ou multi-distribution non vérifiée n'est garantie.</div>

Consultez la [matrice de compatibilité](compatibility.md) et les [limites de sécurité](faq.md#les-sources-sont-elles-vraiment-protegees) avant de travailler sur de véritables preuves.

## Aller plus loin

- [Installation](installation/README.md) et [désinstallation](installation/desinstallation.md)
- [Guide de l'interface](interface-graphique/README.md)
- [Rapports PDF](rapports-pdf/README.md)
- [Références techniques et développement](development/architecture-v2.md)
- [Code source GitHub](https://github.com/Gvte-Kali/vigil)
