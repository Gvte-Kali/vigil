# Vigil 2.0 — Refonte UI/UX, terminaux externes, présentation des acquisitions et correction du stockage

## 1. Contexte et objectifs

Travailler exclusivement sur la branche `vigil-2.0` du dépôt Vigil.

Vigil doit être considéré comme un framework professionnel de Digital Forensics / DFIR, extensible, modulaire et maintenable, et non comme une simple interface graphique permettant de lancer des scripts.

L'interface graphique actuelle constitue une bonne base fonctionnelle. L'objectif est désormais d'améliorer significativement sa finition visuelle, son ergonomie, la cohérence de ses composants et l'expérience utilisateur dans les terminaux.

Cette intervention comporte quatre chantiers principaux :

1. Refonte ergonomique et harmonisation graphique de la GUI.
2. Suppression du centre des tâches graphique au profit des terminaux système.
3. Amélioration de l’affichage des acquisitions RAW et du clonage de disques.
4. Correction du bug `invalid storage context` lors du montage d'un stockage depuis les actions rapides.

Effectuer un audit préalable du code existant. Réutiliser les composants fonctionnels et éviter les réécritures inutiles.

---

# PARTIE A — REFONTE DE L'INTERFACE GRAPHIQUE

## 2. Direction artistique

Conserver PySide6 / Qt Widgets.

Conserver impérativement le logo original de Vigil. Il ne doit être ni remplacé, ni redessiné, ni modifié.

Conserver l'identité Graphite/Cyan, avec une direction artistique inspirée des IDE modernes et des outils professionnels d'investigation numérique.

L'interface doit présenter les caractéristiques suivantes :

- Dark UI professionnelle.
- Forte cohérence visuelle.
- Hiérarchie claire des informations.
- Densité informationnelle maîtrisée.
- Iconographie riche mais sobre.
- Contrastes subtils entre les différentes surfaces.
- Composants compacts.
- Navigation persistante.
- Couleurs sémantiques.
- Absence d'animations décoratives inutiles.

Ne pas chercher à reproduire l'apparence d'un site internet ou d'une application web responsive.

## 3. Design System centralisé

Mettre en place ou consolider un Design System partagé par toutes les pages de Vigil.

Centraliser les Design Tokens :

- Couleurs.
- Typographie.
- Espacements.
- Bordures.
- Rayons.
- Dimensions des composants.
- États interactifs.
- Styles des boutons.
- Styles des tableaux.
- Styles des indicateurs.

Palette indicative :

| Élément | Couleur |
|---|---|
| Background principal | `#101419` |
| Surface secondaire | `#151B22` |
| Surface élevée | `#192129` |
| Surface interactive | `#24313D` |
| Bordures | `#34434E` |
| Texte principal | `#DCE3EA` |
| Texte secondaire | `#94A3B3` |
| Accent cyan | `#55C5D2` |
| Succès | `#79CDA0` |
| Avertissement | `#E4BC72` |
| Erreur | `#E06C75` |
| Accent violet | `#B59AF0` |

Adapter cette palette au thème existant si nécessaire.

Utiliser des différences de couleurs subtiles pour distinguer les catégories, les surfaces et les informations.

Réserver les couleurs sémantiques aux informations ayant une signification réelle.

Utiliser une grille d'espacement basée sur des multiples de 4 et 8 pixels.

Privilégier des bordures fines, des rayons modérés et des surfaces légèrement contrastées.

Éviter les dégradés, les ombres importantes et les effets visuels superflus.

## 4. Iconographie

Enrichir significativement l'interface avec de petites icônes vectorielles homogènes.

Privilégier les icônes Lucide déjà présentes dans le projet.

Utiliser des SVG locaux afin de garantir un fonctionnement hors ligne.

Prévoir des icônes pour :

- Accueil.
- Affaires.
- Preuves.
- Explorateur.
- Modules.
- Analyses.
- Rapports.
- Journal.
- Configuration.
- Actions rapides.
- Périphériques.
- Partitions.
- Stockage.
- Protection RO.
- Antivirus.
- Acquisition.
- Recherche.
- Filtres.
- Export.
- Avertissements.
- Informations.
- Actions contextuelles.

Utiliser une taille cohérente, généralement comprise entre 16 et 20 pixels logiques.

Prévoir des variations de couleur selon la catégorie ou l'état.

Ne pas utiliser les emojis comme remplacement des icônes de navigation.

Les icônes doivent compléter les intitulés et non rendre les actions ambiguës.

## 5. Application Shell

Organiser l'interface autour d'une structure permanente :

- Application Header.
- Navigation Sidebar.
- Main Workspace.
- Status Bar.

Ne pas reconstruire l'intégralité de la fenêtre lors d'un changement de page.

### Application Header

Réduire sa hauteur et améliorer son alignement.

Conserver :

- Logo original de Vigil.
- Nom et version.
- Affaire active.
- Opérateur actif.
- Sélecteur FR/EN.

Distinguer clairement l'identité de l'application du contexte d'investigation.

### Navigation Sidebar

Conserver les catégories actuelles :

**Espace de travail**
- Accueil.

**Investigation**
- Affaire en cours.
- Catalogue de modules.

**Système**
- Configuration de l'entité.
- Actions rapides.

Ajouter une icône à chaque entrée.

Utiliser des Section Headers compacts, des séparateurs discrets et des états de sélection cohérents.

Prévoir une largeur maîtrisée, une possibilité de repli et un défilement vertical.

L'entrée active doit être identifiable par un accent cyan et une surface légèrement contrastée.

### Status Bar

Ajouter une barre d'état inférieure compacte et persistante.

Afficher notamment :

- État de la protection des nouveaux disques.
- État de `/investigation`.
- État de `/stockage`.
- État de protection bloc des supports concernés.
- Version de Vigil si pertinent.

Distinguer explicitement les états RO, RW, non monté et inconnu.

Ne pas présenter la protection des nouveaux périphériques comme une confirmation de protection de tous les disques déjà présents.

## 6. Gestion des dimensions et du défilement

Ne pas utiliser une approche Responsive Layout de type application web.

Privilégier un Controlled Layout avec Scrollable Containers.

Les composants doivent conserver des proportions cohérentes lorsque la fenêtre est agrandie ou réduite.

Utiliser notamment :

- `QScrollArea`.
- `QSplitter`.
- `QSizePolicy`.
- `QStackedWidget`.
- `QTabBar`.
- Dimensions minimales et maximales.
- Stretch Factors maîtrisés.
- Scrollbars horizontales et verticales.
- `minimumSizeHint()`.

Éviter les cartes, boutons et formulaires qui s'étirent inutilement sur toute la largeur ou la hauteur disponible.

Privilégier le défilement plutôt que la compression excessive ou la réorganisation automatique des composants.

Les barres de navigation doivent rester accessibles indépendamment du défilement du contenu.

Les panneaux d'exploration doivent pouvoir être redimensionnés manuellement.

Ne pas imposer une taille fixe à l'ensemble de la fenêtre.

Respecter les paramètres DPI, les tailles de police et les différences de longueur entre les traductions françaises et anglaises.

Cette approche est particulièrement importante sous Hyprland et les autres Tiling Window Managers.

## 7. Refonte de la page Accueil

Transformer l'accueil en Operational Dashboard.

### Vue d'ensemble

Créer des KPI Cards compactes avec :

- Petite icône.
- Intitulé.
- Valeur principale.
- Information secondaire si nécessaire.

Afficher les statistiques réellement disponibles :

- Fichiers enregistrés.
- Preuves.
- Événements récents.
- Affaire active.

Supprimer le compteur de tâches locales actives associé au centre des tâches graphique.

Ne pas afficher de statistiques fictives lorsqu'aucune affaire n'est sélectionnée.

### Ressources système

Présenter de manière compacte :

- CPU.
- Mémoire.
- Charge système.
- Temps de fonctionnement.

Intégrer les Progress Bars directement dans les composants correspondants.

Éviter les cartes excessivement larges pour des informations simples.

### Périphériques et montages

Utiliser une Tree View ou un Tree Table structuré.

Ajouter des icônes distinctes pour les disques, partitions, volumes et points de montage.

Afficher, selon les informations disponibles :

- Nom du périphérique.
- Capacité.
- Système de fichiers.
- Type de connexion.
- État RO/RW.
- Point de montage.

Conserver les détails repliables.

Distinguer clairement les supports système, les preuves et les supports de travail.

### Activité récente

Présenter les événements sous forme de liste chronologique compacte.

Ajouter une icône et un horodatage pour chaque événement.

En l'absence de données, utiliser un Empty State explicite plutôt qu'un panneau vide.

### Session et outils

Remplacer la liste brute par une Data Table compacte :

- Outil.
- Disponibilité.
- Chemin.
- Version si disponible.

Prévoir un filtre permettant d'identifier rapidement les dépendances manquantes.

## 8. Refonte de la page Affaire en cours

Conserver toutes les fonctionnalités existantes.

Remplacer la navigation secondaire actuellement située à droite par une Horizontal Tab Bar sous l'en-tête de la page.

Onglets :

- Explorateur.
- Preuves.
- Analyses.
- Actions et journal.
- Rapports PDF.
- Export.

Ajouter des icônes à chaque onglet.

La barre d'onglets doit rester accessible lors du défilement.

Prévoir un mécanisme de navigation horizontale si la largeur disponible est insuffisante.

### Contextual Toolbar

Regrouper les actions :

- Choisir l'affaire.
- Monter un périphérique ou une image.
- Démonter un périphérique ou une image.

Afficher clairement le contexte de l'affaire et l'état du montage.

### Explorateur

Utiliser un Master-Detail Layout avec Split Panes.

Panneau gauche :

- Arborescence des fichiers.
- Icônes adaptées aux types de fichiers.
- Recherche et filtres.

Panneau droit :

- Inspecteur du fichier sélectionné.
- Métadonnées.
- Hexadécimal.
- Chaînes ASCII.

Utiliser un `QSplitter`.

Améliorer l'alignement et la lisibilité des données techniques.

Utiliser une police monospace pour les chemins, empreintes et données hexadécimales.

Conserver les limites de lecture existantes.

Ajouter des Empty States adaptés à chaque situation :

- Aucune affaire sélectionnée.
- Aucun support monté.
- Aucun fichier sélectionné.
- Aucun résultat disponible.

## 9. Refonte du catalogue de modules

Transformer la liste actuelle en Module Browser professionnel.

Utiliser une disposition Master-Detail :

- Tableau des modules.
- Inspecteur du module sélectionné.

Afficher les informations disponibles dans les manifestes :

- Nom.
- Identifiant.
- Version.
- Catégorie.
- Description.
- Disponibilité.
- Dépendances.
- Capacités.
- Provenance.
- Compatibilité.

Ajouter une Search Bar et des Filter Controls.

Utiliser des icônes par catégorie de modules.

Déplacer le bouton « Créer un module » dans la barre d'actions supérieure.

Supprimer le bouton pleine largeur actuellement situé en bas.

Ne pas coder en dur les modules dans la GUI.

Exploiter le registre et les manifestes existants.

Préparer l'interface pour le futur catalogue communautaire hébergé dans un dépôt GitHub officiel séparé.

Ne pas implémenter prématurément l'installation de modules distants dans ce chantier.

## 10. Configuration de l'entité

Transformer le formulaire actuel en Settings Page structurée.

Créer trois sections :

**Identité**
- Nom de l'entité.
- Établissement.

**Coordonnées**
- Adresse.
- Téléphone.
- Adresse e-mail.

**Identité visuelle**
- Aperçu du logo de l'entité.
- Sélection du logo.
- Suppression du logo.

Limiter la largeur maximale des champs.

Utiliser un alignement cohérent des labels et des champs.

Regrouper les boutons dans une Action Bar.

Afficher un retour explicite après l'enregistrement.

Ne jamais utiliser de données réelles d'une entité dans les tests, les fixtures, les captures de documentation ou les commits GitHub.

## 11. Actions rapides

Conserver les catégories :

- Antivirus.
- Stockage.
- Acquisition.

Remplacer les grandes cartes actuelles par des Compact Action Groups.

Chaque action doit présenter :

- Une icône.
- Un intitulé.
- Une courte description.
- Un état de disponibilité si nécessaire.

Utiliser une accentuation cyan pour les actions principales, verte pour le stockage et violette pour l'acquisition lorsque cela améliore la distinction des catégories.

Réserver les avertissements aux opérations sensibles.

Conserver les actions existantes :

- Scan antivirus.
- Mise à jour de l'antivirus.
- Rapports antivirus.
- Monter un stockage.
- Démonter un stockage.
- Cloner un disque.
- Créer une image RAW.

Ne pas imposer une hauteur identique excessive aux différents groupes.

Préserver toutes les confirmations et protections existantes.

## 12. Harmonisation globale des composants

Standardiser :

- Page Headers.
- Section Headers.
- Contextual Toolbars.
- Data Tables.
- Tree Views.
- Search Bars.
- Filter Controls.
- Status Indicators.
- Empty States.
- Primary Buttons.
- Secondary Buttons.
- Confirmation Dialogs.
- Error Dialogs.
- Tooltips.
- Scrollbars.
- Form Fields.

Limiter le nombre de boutons primaires cyan simultanément visibles.

Prévoir des états Hover, Focus, Selected et Disabled cohérents.

Conserver le support intégral FR/EN.

Garantir une utilisation complète à la souris et au clavier.

---

# PARTIE B — SUPPRESSION DU CENTRE DES TÂCHES

## 13. Suppression du composant graphique

Supprimer entièrement le centre des tâches de la GUI.

Supprimer :

- Le bouton « Afficher le centre des tâches ».
- Le panneau associé.
- Les widgets de terminal intégré.
- Les mécanismes d'émulation de terminal propres à la GUI devenus inutiles.
- Les références graphiques obsolètes.
- Le compteur de tâches locales associé.

Toutes les opérations actuellement exécutées dans le terminal intégré doivent désormais s'ouvrir dans de véritables terminaux système externes.

Les formulaires, consultations et opérations internes rapides restent intégrés à la GUI.

Ne pas supprimer les mécanismes métier de suivi d'exécution, de journalisation, d'audit et de traçabilité.

Préserver les composants réutilisables par Vigil Core, la CLI et la future TUI.

Ne pas introduire de daemon permanent ni de service système supplémentaire.

## 14. TerminalLauncher centralisé

Créer ou consolider un `TerminalLauncher` indépendant de PySide6.

Toutes les ouvertures de terminaux externes doivent passer par ce composant.

Prévoir une préférence utilisateur permettant de choisir le terminal.

Ordre de résolution proposé :

1. Terminal explicitement configuré.
2. `xdg-terminal-exec`.
3. Kitty.
4. Alacritty.
5. Foot.
6. Konsole.
7. GNOME Terminal.
8. XFCE Terminal.
9. XTerm.

Vérifier la disponibilité et la compatibilité réelle du terminal avec la session graphique.

Ne pas supposer que tous les terminaux utilisent les mêmes arguments.

Utiliser des listes d'arguments validées.

Éviter les concaténations de commandes shell et les problèmes d'échappement.

Préserver les chemins contenant des espaces ou des caractères spéciaux.

L'ouverture d'un terminal doit être non bloquante pour la GUI.

À la fin de l'opération, conserver un écran récapitulatif et permettre à l'opérateur de fermer le terminal après consultation du résultat.

Ne pas confondre le code de sortie de l'émulateur de terminal avec celui de l'opération exécutée.

Prévoir une remontée fiable du résultat réel.

Capturer avant chaque lancement un contexte d'exécution immuable contenant les informations nécessaires :

- `run_id`.
- Opérateur.
- Affaire, si nécessaire.
- Module ou opération.
- Paramètres validés.
- Destination des résultats.

Une action autonome ne doit pas nécessiter artificiellement une affaire active.

## 15. Compatibilité Hyprland et Linux

Garantir une architecture indépendante de l'environnement de bureau.

Ne pas rendre Konsole obligatoire.

Préserver la compatibilité avec :

- Debian.
- Ubuntu.
- Parrot OS.
- Fedora.
- Arch Linux.
- Omarchy.
- Hyprland.
- KDE Plasma.
- GNOME.
- XFCE.
- X11.
- Wayland.

Ne pas forcer globalement `QT_QPA_PLATFORM`.

Ne pas imposer aux terminaux externes :

- Une taille fixe.
- Une position absolue.
- Un mode flottant.
- Un workspace particulier.
- Un comportement de focus spécifique.

Laisser le Window Manager gérer leur disposition.

Ne jamais modifier automatiquement la configuration Hyprland de l'utilisateur.

Prévoir un message explicite si aucun terminal compatible n'est disponible.

## 16. Cycle de vie des opérations

La suppression du centre des tâches ne doit pas compromettre les opérations en cours.

Définir le comportement lors :

- De la fermeture d'un terminal.
- D'une interruption clavier.
- D'une erreur du processus.
- De la fermeture de Vigil.
- D'une déconnexion du support.

La fermeture de la GUI ne doit pas démonter prématurément une preuve ou un stockage utilisé par une opération active.

Ne pas restaurer prématurément les protections système.

Préserver les résultats partiels et les journaux conformément aux règles forensiques existantes.

---

# PARTIE C — AMÉLIORATION DES TERMINAUX ET DES SCRIPTS D'ACQUISITION

## 17. Constat issu d'un test réel

Une acquisition RAW de 4 026 531 840 octets, soit 3,75 Gio, a présenté les comportements suivants :

- Une nouvelle ligne à chaque actualisation du pourcentage de copie.
- Une phase de synchronisation des écritures dépassant 405 secondes.
- Des messages « en cours depuis XX s » toutes les 15 secondes.
- Une répétition de ces messages pendant la vérification SHA-256, alors qu'un pourcentage est déjà disponible.
- Une acquisition finalement vérifiée avec succès et un code de sortie 0.

Ces comportements doivent être améliorés.

Appliquer les modifications à la création d'images RAW et au clonage de disques.

Auditer les éventuels composants communs afin d'éviter la duplication de code.

## 18. Terminal Design System

Créer une identité visuelle cohérente pour les scripts interactifs de Vigil.

Conserver le logo ASCII actuel.

Standardiser :

- En-têtes.
- Titres de sections.
- Séparateurs.
- Couleurs ANSI.
- Indicateurs de succès.
- Avertissements.
- Erreurs.
- Progress Bars.
- Spinners.
- Résumés d'opération.

Utiliser une palette cohérente avec la GUI :

- Cyan : informations et progression.
- Vert : succès confirmé.
- Jaune : attente et avertissement.
- Rouge : erreur ou opération dangereuse.
- Violet : informations secondaires.
- Gris : informations complémentaires.

Prévoir des alternatives ASCII lorsque les caractères Unicode ne sont pas correctement supportés.

Respecter les préférences `NO_COLOR`, les terminaux limités et les sorties non interactives.

Ne pas transformer les scripts en applications TUI plein écran à ce stade.

## 19. Affichage dynamique de la progression

Remplacer l'accumulation de lignes de progression par un mécanisme d'In-place Progress Rendering.

En mode terminal interactif, actualiser la ligne actuelle à l'aide de :

- Carriage Return `\r`.
- Effacement de ligne ANSI lorsque supporté.
- Rafraîchissement contrôlé de la sortie.
- Détection TTY.

Exemple de rendu attendu :

```text
[1/4] Acquisition

[██████████████░░░░░░] 70.0 %
2.63 / 3.75 Gio | 12.5 Mio/s | ETA : 01:32
```

La progression doit évoluer sur place.

Ne pas générer une nouvelle ligne à chaque actualisation.

Afficher lorsque les données sont réellement disponibles :

- Pourcentage.
- Volume traité.
- Volume total.
- Débit instantané ou débit moyen lissé.
- Temps restant estimé.

Utiliser des unités lisibles : Kio, Mio, Gio, Mio/s.

Conserver les valeurs exactes en octets dans les journaux techniques.

Limiter la fréquence de rafraîchissement afin de ne pas générer de charge inutile.

Prévoir un rendu compact lorsque le terminal est étroit.

Lorsqu'une étape est terminée, figer sa dernière ligne et passer proprement à l'étape suivante.

## 20. Suppression des messages redondants

Supprimer les messages périodiques :

```text
Relecture de la destination et calcul du SHA-256 · en cours depuis 15 s
Relecture de la destination et calcul du SHA-256 · en cours depuis 30 s
```

Lorsque l'étape dispose déjà d'une progression mesurable, ne pas afficher de Heartbeat Messages supplémentaires.

Cette règle s'applique notamment :

- À la copie RAW.
- Au clonage.
- À la relecture.
- Au calcul SHA-256.
- Aux autres traitements disposant d'une progression mesurable.

Pour les étapes sans progression mesurable, utiliser un Indeterminate Progress Indicator ou un Spinner.

Actualiser le temps écoulé sur la même ligne si nécessaire.

Ne pas produire de faux pourcentage.

Les avertissements et erreurs doivent interrompre proprement la progression dynamique afin de rester visibles.

## 21. Gestion des sorties non interactives

Distinguer explicitement :

- Interactive Terminal Output.
- Non-interactive Output.
- Structured Logging.

Lorsque la sortie n'est pas un TTY :

- Ne pas utiliser de séquences ANSI de déplacement du curseur.
- Ne pas utiliser de Carriage Return pour écraser les lignes.
- Produire des messages textuels propres.
- Limiter la fréquence des messages de progression.
- Préserver les éventuels contrats JSON existants.

Ne pas introduire de caractères de contrôle dans les journaux d'audit.

Séparer le rendu visuel de la collecte des événements métier.

Préparer cette séparation pour la future CLI et la TUI Textual.

## 24. Message de synchronisation

Afficher au début de la synchronisation :

> La copie logique est terminée. Vigil procède maintenant à la synchronisation des écritures en attente vers le support de destination.
>
> Cette étape peut prendre plusieurs minutes selon le volume de données, les performances du support, son interface de connexion et son système de fichiers.
>
> Ne débranchez pas le périphérique avant la fin de l’opération.

En TTY, afficher un indicateur indéterminé et le temps écoulé sur une seule
ligne actualisée. En sortie non interactive, écrire le début de l’étape en
texte uni et reporter sa durée dans le résumé. La synchronisation ne
présente ni pourcentage ni temps restant.

Les appels de lecture, d’écriture, de synchronisation, de gestion du
cache et de vérification SHA-256 restent ceux de l’acquisition actuelle.
La protection RO et les vérifications d’identité sont conservées.

## 25. Présentation des phases d'acquisition

Structurer les opérations autour d'étapes clairement identifiées.

Exemple pour une acquisition RAW :

```text
[1/4] Acquisition de l'image RAW
[2/4] Synchronisation des écritures
[3/4] Relecture et vérification SHA-256
[4/4] Finalisation et démontage
```

Adapter les étapes à la réalité du traitement.

Ne pas masquer les contrôles préliminaires, la préparation du cache, la création du manifeste ou les opérations de nettoyage.

Utiliser des sous-étapes si nécessaire.

Pour la copie et la vérification SHA-256, utiliser une progression déterminée.

Pour la synchronisation et les opérations sans métrique fiable, utiliser une progression indéterminée.

Le passage de la copie à 100 % ne doit pas être présenté comme la fin de l'acquisition complète.

## 26. Vérification SHA-256

Conserver intégralement les garanties actuelles de vérification.

Ne pas remplacer la vérification indépendante de la destination par une simple empreinte calculée pendant la copie.

Auditer le mécanisme de préparation de la relecture afin de vérifier que la comparaison ne repose pas uniquement sur les données encore présentes dans le cache d'écriture.

Documenter les garanties et limites du mécanisme retenu.

Ne pas prétendre garantir une persistance physique absolue si le matériel ou son firmware ne fournit pas cette garantie.

Afficher la progression SHA-256 sur place :

```text
[3/4] Vérification SHA-256

[████████████████░░░░] 80.0 %
3.00 / 3.75 Gio | 18.4 Mio/s | ETA : 00:42
```

Supprimer les Heartbeat Messages redondants pendant cette phase.

Afficher explicitement le résultat de la comparaison.

En cas de divergence, ne jamais déclarer l'acquisition valide.

## 27. Résumé final d'acquisition

Créer un Acquisition Summary lisible.

Afficher, selon les informations disponibles :

- Statut final.
- Type d'acquisition.
- Source.
- Destination.
- Nom de l'image.
- Volume exact.
- Empreinte SHA-256 de référence.
- Empreinte SHA-256 de la destination.
- Résultat de la comparaison.
- Durée de copie.
- Durée de synchronisation.
- Durée de vérification.
- Durée totale.
- Débit moyen.
- État du démontage.
- Emplacement du manifeste.
- Emplacement du journal ou rapport.
- Code de sortie réel.

Exemple :

```text
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ACQUISITION TERMINÉE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[OK] Copie complète
[OK] Synchronisation terminée
[OK] Empreintes SHA-256 identiques
[OK] Destination démontée

Volume acquis        : 3.75 Gio
Durée de copie       : ...
Durée de sync        : ...
Durée de vérification: ...
Durée totale         : ...

Intégrité            : VÉRIFIÉE
Code de sortie       : 0

Appuyez sur Entrée pour fermer.
```

Ne jamais afficher un état de succès pour une étape qui n'a pas réellement réussi.

## 28. Application au clonage de disques

Appliquer les mêmes améliorations au script de clonage :

- In-place Progress Rendering.
- Débit.
- ETA lorsque fiable.
- Suppression des Heartbeat Messages redondants.
- Synchronisation explicite.
- Vérification SHA-256.
- Résumé final.
- Gestion des erreurs.
- Compatibilité TTY et non-TTY.

Tenir compte des différences entre une destination fichier et une destination périphérique bloc.

Conserver les protections spécifiques au clonage.

Vérifier notamment :

- L'identité de la source.
- L'identité de la destination.
- La capacité de la destination.
- L'absence de montage incompatible.
- La protection RO de la source.
- La confirmation explicite de l'opération destructive sur la destination.
- La portée exacte de la vérification si la destination est plus grande que la source.

Préserver la protection en écriture du disque source.

## 29. Mutualisation des composants terminal

Éviter de dupliquer les mécanismes de progression et de rendu dans chaque script.

Identifier ou créer des composants partagés pour :

- Affichage des en-têtes.
- Couleurs ANSI.
- Détection TTY.
- Progress Bars.
- Spinners.
- Affichage dynamique.
- Formatage des tailles.
- Formatage des durées.
- Calcul des débits.
- Estimation du temps restant.
- Résumés d'opération.
- Gestion des erreurs.

Respecter l'architecture et les langages déjà utilisés dans le dépôt.

Ne pas ajouter une dépendance lourde uniquement pour afficher une barre de progression.

Pour tout nouveau script Bash, utiliser le shebang `#!/usr/bin/bash`.

Préparer des composants réutilisables par les futurs modules Vigil.

---

# PARTIE D — CORRECTION DU BUG DE MONTAGE DU STOCKAGE

## 30. Description du bug

Depuis la GUI :

1. Ouvrir « Actions rapides ».
2. Sélectionner « Monter un stockage ».
3. L'opération échoue avec le message :

```text
L'opération a échoué : invalid storage context
```

Ce comportement doit être corrigé.

## 31. Analyse de la cause racine

Ne pas masquer l'erreur.

Ne pas désactiver les validations pour permettre le montage.

Identifier précisément l'origine de `invalid storage context`.

Rechercher cette chaîne dans l'ensemble du dépôt.

Tracer le parcours complet :

```text
GUI
  -> Action rapide
  -> Construction du contexte
  -> Service ou adaptateur
  -> Runner
  -> Validation du contexte
  -> Opération de montage
```

Vérifier notamment :

- Le contexte transmis par la GUI.
- Les paramètres attendus par le service.
- Le type d'opération.
- Les champs obligatoires.
- Les valeurs nulles.
- La présence éventuelle d'un contexte obsolète.
- Les différences entre actions autonomes et actions liées à une affaire.
- La sérialisation et la désérialisation.
- Les changements introduits lors de la migration vers Vigil 2.0.
- Les éventuelles incompatibilités avec les adaptateurs historiques.
- La validation de la destination `/stockage`.

Déterminer si le problème provient d'un contexte absent, incomplet, incorrectement typé ou incompatible avec le parcours d'action rapide.

Ne pas supposer la cause avant d'avoir effectué l'audit.

## 32. Comportement attendu

L'action rapide « Monter un stockage » doit fonctionner sans nécessiter la création ou la sélection d'une affaire.

Elle doit utiliser un contexte autonome valide, associé à l'opérateur et à l'opération.

Le support de travail doit pouvoir être monté sous `/stockage` conformément aux règles de sécurité existantes.

Préserver la séparation stricte entre :

- `/investigation` : zone d'investigation en lecture seule.
- `/stockage` : zone de travail autorisée en lecture-écriture.

Ne jamais autoriser l'écriture sur un support identifié comme preuve.

Ne jamais contourner les contrôles d'identité des périphériques.

Ne pas désactiver globalement la protection des nouveaux disques pour corriger le problème.

Vérifier également l'action « Démonter un stockage » et les autres actions rapides susceptibles d'utiliser le même mécanisme de contexte.

## 33. Amélioration des messages d'erreur

Remplacer les erreurs techniques brutes affichées seules par des messages explicites et traduits.

Exemple :

```text
Impossible de monter le stockage.

Le contexte de l'opération de montage est invalide.

Consultez les détails techniques ou le journal
pour identifier la cause de l'erreur.
```

Conserver le détail technique original dans les journaux.

Prévoir un accès aux détails de l'erreur lorsque pertinent.

Ne pas masquer la cause racine derrière un message générique.

## 34. Tests de non-régression du stockage

Ajouter des tests couvrant :

- Montage sans affaire active.
- Montage avec affaire active.
- Contexte valide.
- Contexte invalide.
- Opérateur absent.
- Annulation de l'opération.
- Aucun support compatible.
- Support déjà monté.
- Support identifié comme preuve.
- Échec du montage.
- Démontage du stockage.
- Contexte autonome transmis depuis un terminal externe.

Utiliser des mocks, fixtures et environnements isolés.

Ne pas effectuer de tests destructifs sur des périphériques réels.

---

# PARTIE E — ARCHITECTURE, SÉCURITÉ ET VALIDATION

## 35. Architecture

Préserver la convergence vers l'architecture cible :

```text
Vigil GUI — PySide6
Vigil CLI — Typer
Vigil TUI — Textual (future)
        |
    Vigil Core
        |
Services / Registry / Runner / Audit
        |
Scripts et modules
```

Ne pas dupliquer la logique métier dans les composants graphiques.

Le TerminalLauncher doit rester indépendant de Qt.

Le rendu de progression doit rester indépendant du traitement métier.

Les événements de progression doivent pouvoir être exploités ultérieurement par la TUI.

Préserver les contrats existants de Vigil Core.

Réduire progressivement la concentration du code dans les fichiers graphiques volumineux.

Ne pas engager une refonte générale du Core dans ce chantier.

## 36. Contraintes forensiques impératives

Ne supprimer aucun contrôle de sécurité existant.

Préserver :

- Protection en lecture seule.
- Protection des nouveaux disques.
- Identification des périphériques.
- Contrôles des sources et destinations.
- Confirmations explicites.
- Synchronisation des écritures.
- Vérification indépendante de la destination.
- Empreintes SHA-256.
- Chaîne de custody.
- Journalisation.
- Intégrité des résultats.
- Manifestes.
- Codes de retour.
- Gestion des interruptions.
- Nettoyage des ressources.

Ne pas réintroduire de règle sudoers générique.

Conserver toutes les protections existantes.

Ne jamais déclarer une opération réussie uniquement parce que la copie a atteint 100 %.

Ne pas modifier automatiquement les paramètres système globaux.

## 37. Ordre d'implémentation

Procéder par lots indépendants.

### Lot 1 — Audit et correction du stockage

- Reproduire le bug `invalid storage context`.
- Identifier sa cause racine.
- Corriger le parcours.
- Ajouter les tests de non-régression.

### Lot 2 — Acquisition RAW et clonage

- Vérifier que les mécanismes d’acquisition existants sont préservés.
- Afficher les durées écoulées pour l’opérateur.
- Mettre en place les composants communs de progression.
- Améliorer les messages de synchronisation.
- Supprimer les messages redondants.
- Ajouter les résumés finaux.
- Vérifier l'intégrité des acquisitions.

### Lot 3 — Terminaux externes

- Auditer les dépendances du centre des tâches.
- Créer ou consolider le TerminalLauncher.
- Migrer les opérations vers les terminaux système.
- Vérifier les codes de sortie et les contextes.
- Vérifier les comportements d'interruption et de fermeture.
- Supprimer le centre des tâches après validation des parcours de remplacement.

### Lot 4 — Design System

- Centraliser les Design Tokens.
- Harmoniser la palette.
- Harmoniser l'iconographie.
- Créer les composants réutilisables.
- Standardiser les états interactifs.

### Lot 5 — Application Shell

- Revoir le Header.
- Revoir la Sidebar.
- Ajouter la Status Bar.
- Mettre en place les Scrollable Containers.
- Maîtriser les dimensions.

### Lot 6 — Refonte des pages

- Accueil.
- Affaire en cours.
- Catalogue de modules.
- Configuration de l'entité.
- Actions rapides.

### Lot 7 — Validation générale

- Tests unitaires.
- Tests d'intégration.
- Tests de non-régression.
- Tests TTY et non-TTY.
- Tests des terminaux externes.
- Tests Wayland et X11.
- Tests Hyprland.
- Tests FR/EN.
- Tests de redimensionnement.
- Mise à jour de la documentation.

## 39. Critères d'acceptation

Le chantier sera considéré comme terminé lorsque :

- Le logo original de Vigil est préservé.
- L'identité Graphite/Cyan est conservée et améliorée.
- Les icônes sont nombreuses, cohérentes et utiles.
- Les composants graphiques sont harmonisés.
- Les pages présentent une hiérarchie visuelle claire.
- Les composants ne s'étirent plus inutilement.
- Les barres de navigation restent accessibles.
- Les zones défilantes fonctionnent correctement.
- Le catalogue de modules est structuré et extensible.
- Le centre des tâches graphique a disparu.
- Les opérations s'ouvrent dans des terminaux système externes.
- Konsole n'est plus obligatoire.
- Les progressions sont actualisées sur place en mode TTY.
- Les messages périodiques redondants ont disparu.
- En TTY, la synchronisation affiche son explication et un temps écoulé
  actualisé sur une seule ligne, sans pourcentage ni ETA.
- En non-TTY, la progression et les résultats restent lisibles sans
  séquences de contrôle. Le résumé distingue copie, synchronisation et
  vérification indépendante.
- Les acquisitions RAW et le clonage conservent leurs garanties d'intégrité.
- Le bug `invalid storage context` est corrigé.
- Le montage de stockage fonctionne sans affaire active.
- Aucun mécanisme de sécurité n'a été affaibli.
- La compatibilité Linux et Wayland est préservée.
- La future intégration de Vigil Core, CLI et TUI reste possible.

## 40. Instructions finales

Commencer par auditer la branche actuelle et lire les instructions permanentes du projet.

Identifier les fichiers concernés avant de les modifier.

Mettre à jour `todo.txt` à la racine du dépôt avec les différents lots de ce chantier, sans supprimer les autres objectifs de la roadmap.

Effectuer les modifications progressivement, avec des commits distincts.

Exécuter les tests pertinents après chaque lot.

Mettre à jour les tâches de `todo.txt` uniquement lorsque leurs critères d'acceptation sont satisfaits.

Ne pas déclarer un test réussi s'il n'a pas été exécuté.

Ne pas déclarer la compatibilité Hyprland validée sans test réel correspondant.

En cas de blocage, documenter précisément la cause et proposer une solution.

À la fin du chantier, fournir :

- Résumé des modifications.
- Liste des fichiers modifiés.
- Cause racine du bug de stockage.
- Résultats des tests.
- Limitations restantes.
- État actualisé de la roadmap.

Les choix esthétiques secondaires peuvent être réalisés de manière autonome, à condition de respecter l'identité visuelle, la cohérence ergonomique et les exigences de sécurité définies dans ce document.


## Recette de la branche Vigil 2.0

Le bouton Qt de montage du stockage transmettait `False`, valeur du
signal `clicked(bool)`, au paramètre `operation` du callback. Vigil
exige une opération explicite. L’action autonome transmet l’opérateur
et écrit ses journaux dans `storage-operations` sous le répertoire d’état.

La préférence de terminal se trouve dans la barre d’état. Les exécutions
externes conservent le contexte et le résultat réel sous `terminal-runs`.
Un terminal qui attend la touche Entrée après publication du résultat
n’empêche pas la fermeture de Vigil. Si le processus de suivi disparaît
sans résultat, Vigil indique un état inconnu.

Recette manuelle à compléter dans une VM avec bureau Linux. Vérifier les
parcours sur X11 et sous Hyprland/Wayland, puis suivre la checklist dans
`tests.txt`. Pour revenir à l’interface précédente, annuler les commits
du chantier dans l’ordre inverse. Le chantier ne requiert aucune
migration de la base d’affaires.
