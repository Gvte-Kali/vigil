---
layout: default
title: Matrice de compatibilité
parent: Développement
nav_order: 14
---

# Matrice de compatibilité Vigil 2.0

État statique au commit `a2553ba`. « Partiel » signifie qu'un composant existe et qu'il reste un écart de recette. « Absent » désigne la capacité cible non identifiée dans les sources suivies. Les tests effectivement exécutés figurent dans la [baseline](test-baseline.md). Les chemins relatifs des scripts sont explicités dans l'[inventaire](phase-00-audit.md).

| ID | État et preuve actuelle | Phase et recette minimale |
|---|---|---|
| F01 | Partiel, SCRIPTS statique `gui/vigil_tools_gui.py:87–165`. | 02, découvrir un module sans changement GUI, filtrer et rejeter doublons. |
| F02 | Absent, paramètres tuple `gui/vigil_tools_gui.py:74–165`. | 02, version et validation stricte, rejet de schémas et champs dangereux. |
| F03 | Partiel, `scripts/Vigil-CLI/vigil:1–20` et entrées monofonction ; symlink GUI `post_install_vigil.sh:96–100`. | 02–08, mêmes parcours, aide, JSON et codes documentés. |
| F04 | Absent, modules fournis avec scripts `gui/vigil_data.py:28`. | 04, recherche, installation explicite, activation, update, rollback et retrait contrôlés. |
| F05 | Partiel, contrôles ponctuels `vigil_usb_mount.sh:190–197`. | 02, outils/versions/droits/protections et motifs de refus. |
| F06 | Partiel, projets et profils `gui/vigil_data.py:159–218`. | 03, affaires multipreuves, opérateurs, archives, import idempotent sans perte. |
| F07 | Partiel, requête census `vigil_census_query.py:39–73`. | 06, arbre/table paginés, hex/aperçu inerte, export et index validé. |
| F08 | Absent, mtime stocké `vigil_census.sh:712–714`. | 07, zoom/filtres, UTC et fuseau source, précision, provenance et export. |
| F09 | Partiel, filtres SQL simples `vigil_census_query.py:51–71`. | 06, FTS5, filtres chemin/hash/type, portée affaire, contenu sensible exclu par défaut. |
| F10 | Absent, données projet `gui/vigil_data.py:199–218`. | 06, CRUD tracé sur IDs stables, source intacte. |
| F11 | Absent, JSON de presets pour sélections de modules `gui/vigil_data.py:252–315`. | 06, collections persistantes d'artefacts, export de sélection. |
| F12 | Partiel, indices de hash/doublons `vigil_census.sh:712–716`. | 07, liens provenance/règle/confiance, chemins, temps, IDs, hash et revue humaine. |
| F13 | Partiel, orchestration séquentielle `scripts/vigil_scan_all.sh:166–231`. | 05, file durable, annulation, logs, reprise d'état après crash. |
| F14 | Absent comme contrat de reprise, nettoyage rapporté `vigil_census.sh:138–152`. | 05, checkpoint lié aux entrées ou tentative distincte, zéro écrasement. |
| F15 | Partiel, contrôle taille du clone `vigil_disk_clone.sh:351–358`. | 05, CPU/RAM/I/O/espace, alertes et limites. |
| F16 | Absent pour ouverture d'images existantes ; création `vigil_disk_imager.sh:681–754`. | 03, RAW/E01 RO, hash, partition et nettoyage même en erreur ; AFF conditionnel. |
| F17 | Partiel, erreurs RO bloc parfois non bloquantes `vigil_usb_mount.sh:1182–1241`. | 01, identifier bloc/montage/protocole, refus strict, rapport des limites. |
| F18 | Absent pour extractions Windows normalisées ; filtre GUI `gui/vigil_tools_gui.py:194–213`. | 07, registre/USB/EVTX/MFT/USN/LNK/thumbs/PE/BOOTSTAT sur fixtures. |
| F19 | Absent, multi-scans de fichiers présents `scripts/vigil_scan_all.sh:166–212`. | 07, source RO, destination et espace validés, confirmation, provenance et hashes, parcours à part. |
| F20 | Partiel, hashes census/export et imagerie `vigil_census.sh:797–799`, `vigil_export_project.sh:164–211`. | 03, calcul/comparaison SHA-256 et écarts tracés. |
| F21 | Partiel, sections PDF `vigil_pdf.py:2281–2307`. | 08, choix sections et paramètres, limites et PDF existant. |
| F22 | Partiel, logs dans répertoires projet `gui/vigil_data.py:335`. | 05, filtrer et consulter par affaire/preuve/module/statut, résultats et tentatives. |
| F23 | Partiel, hash archive et manifeste relus séparément `vigil_export_project.sh:154–211`. | 01/08, lot figé, tailles/hash, vérification avant publication, état signature explicite. |
| F24 | Partiel, PDF multi et hunt `scripts/vigil_scan_all.sh:226–231`, `vigil_pdf.py:2105,2289`. | 08, synthèse affaire incluant sources, timeline, annotations, méthodes, custody et limites. |
| F25 | Partiel, pages Tk et Konsole `gui/vigil_gui_base.py:273`, `gui/vigil_tools_gui.py:1167`. | 04, espace unique, contexte toujours visible et parcours migrés intégrés. |
| F26 | Partiel, constantes Tk `gui/vigil_gui_base.py:511–520`, Pages Graphite `docs/_sass/color_schemes/graphite.scss:1`. | 04, Graphite/Cyan, thèmes optionnels, densité persistante. |
| F27 | Partiel, Treeview multi-scan `gui/vigil_tools_gui.py:455–501`. | 06, filtres/tri/colonnes/sélection, pagination et CSV sûr. |

## Parité des parcours existants

| Parcours | Preuve de présence et écart | Conservation |
|---|---|---|
| Configuration, opérateurs et projets | `gui/vigil_data.py:24–45,159–218` ; `gui/vigil_project_manager.py:64–180`. Les paires d'identité restent globales. | 01/03/04, importer configuration/profils/projets, figer contexte. |
| Triage HID, montage/démontage, stockage RW | `vigil_usb_mount.sh:308,527,745–769,1182–1241` ; `vigil_stockage_mount.sh:691–693`. | 01/04, préserver listes et triage, recette RO/MTP et identité. |
| Census, doublons, checksafe | `vigil_census.sh:361,569–633,679–799`. Préservation inter-runs à corriger. | 01/03/06, comparer SQLite, TSV, hash, PDF et sémantique de filtres. |
| Images/visages, vidéos, audio, Office, archives, crypto, entropie, gros fichiers | Registre/types `gui/vigil_tools_gui.py:87–180`, appels et arguments individuels dans l'inventaire. | 02/04/06, mêmes options, copies sûres, métriques, résultats et PDF, fallback standalone. |
| Antivirus/chasse autonome/mise à jour | `vigil_clamav_scan.sh:128–145,436–444`, `vigil_malware_hunt.sh:57–85,148,436` et scripts update suivis. | 01/02/04/08, conserver modes archive/chiffrement/taille, opérateur sans projet pour chasse, signatures et limites. |
| Multi-scan/presets/filtres | `vigil_tools_gui.py:194–213,455–501,1071–1170`, `vigil_data.py:252–315`, `scripts/vigil_scan_all.sh:166–231`. | 02/04/05, mêmes ensembles et params, garder la sélection visible, carve séparé. |
| Acquisition et clonage | `vigil_disk_imager.sh:681–817`, `vigil_disk_clone.sh:351–427`. AFF affiché, format effectif non vérifié. | 01/03/04, recette RAW et E01, validation format AFF, intégrité et limites. |
| Export, custody et PDF | `vigil_export_project.sh:130–211`, `vigil_pdf.py:2277–2307`, `vigil_census.sh:181–206`. | 01/08, préserver données et rapports, vérifier cohérence et historique. |

## Correspondance du backlog historique

Chaque ligne de l'ancien todo est couverte par son sous-axe ci-dessous. Les marques historiques restent des déclarations à mettre en regard de la preuve citée. Les validations matérielles et manuelles du fichier todo_tests.txt restent historiques.

| Repère todo.txt | Destination |
|---|---|
| Déjà livré, recensement/dédup/checksafe, projet sauf antivirus, custody, orchestrateur, export, ClamAV natif | Source présente, voir parité ci-dessus. L'obligation projet varie selon parcours (clone contexte non bloquant `vigil_disk_clone.sh:43`). Plafond ClamAV et options confirmés dans le code, fonctionnement à recetter. 01/02/08. |
| Règles 1–4 zones/custody/PDF/orchestrateur | 01, 02, 08 ; préserver triangle, logs, PDF et séparation carving. |
| Règle 5 intégration statique par fichier/tag/doc | 02/04 remplace par adaptateurs et manifeste ; 07 conserve catégories et docs. |
| Chantier A, privilèges et checksafe | 01 pour chaque item. |
| Chantier B, strict, triage, état MTP et rapport | 01, 08 pour la restitution. |
| Chantier C, run/contexte, conservation et export figé | 01, 03 pour la migration et 08 pour publication finale. |
| Chantier D, progression, erreurs, compteurs et liens | 02/05 pour les événements et états, 08 pour compteurs et PDF. |
| Image existante, ouverture/empreinte/choix partition et réutilisation/nettoyage | 03, intégré à census 06. |
| 0.1 montage et option PDF | Décision 00, sécurité 01 avant activation, 02 pour orchestration. |
| 0.2 scripts, réutilisation, mesure et standalone | Décision 00, 02 adaptateurs et 06 validation de l'index. |
| 0.3 formats inconnus et heuristiques | Décision 00, backlog d'analyse après 06. |
| 1.1 filtres ; 1.2 presets et JSON | Présents statiquement `vigil_tools_gui.py:194–213,455–501`, `vigil_data.py:252–315` ; parité 02/04. |
| 1.3 renommage et vérification des tags | Les chemins actuels concordent pour le registre et l'orchestrateur ; la convention nominale n'est pas universelle (ex. `vigil_census.sh`). 02/04, vérification tags continue. |
| 1.4 tableau, fenêtre, paramètres, sélection et custody preset | Implémentation présente `vigil_tools_gui.py:455–778,845–891,1053–1170` ; vérifier scénarios/fenêtre en recette 04/05. |
| 2.0 USB/HID, baseline, blocage, listes, délais, PDF et rafraîchissement | Code de triage et UI présents (`vigil_usb_mount.sh:308–530`, `gui/vigil_usb_gui.py:333`) ; recette synthétique/VM 01/04 pour chaque variante. |
| 2.1 USB, 2.2 timeline, 2.3 registre, 2.4 EVTX | 07, sorties et corrélations incluses ; lecture de l'index après 06. |
| 2.5 MFT, 2.6 USN, 2.7 LNK, 2.8 thumbs, 2.9 PE, 2.10 productkey/BOOTSTAT | 07, productkey soumis à arbitrage backlog en complément de BOOTSTAT. |
| 3.1 multi-hash/ISO | 03 SHA-256 ; algorithmes complémentaires et ISO Windows en backlog. |
| 3.2 navigateurs/credentials, 3.3 bases, 3.4 encodage | Backlog, y compris garde-fous et arbitrage des données sensibles. |
| 3.5 plein texte | 06 FTS5 métadonnées ; stack Xapian et contenu en backlog. |
| 4.1 identification, 4.2 carving guidé | 07, après MFT/USN, avec destination validée, approbation, custody et hashes. |
| 5.1 Xbox 360 | 04 préserve filtre ; XTAF et extraction en backlog. |
| 5.2 smartphone | 01 limites MTP ; acquisition conditionnelle 03 ; ADB en backlog. |
| 5.3 capture visuelle | Backlog explicite. |
| 6 maintenances requirements, installation, disponibilités scalpel et recette fraîche | 02 inventaire des capabilities, validation continue par module et recette finale 08. |
| Ordre de travail historique 0–6 | Feuille de route 00–08 pour les livraisons ; axes restants en backlog. |

Vérification documentaire reproductible avec `rg -n '^--- |^\[x\]|^Déjà livré' todo.txt` et `git ls-files`. Les cases de l'historique restent inchangées.
