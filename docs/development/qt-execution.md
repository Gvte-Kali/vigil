# Parcours d’exécution dans le workspace Qt

L’opérateur est une fiche SQLite identifiée, créée avec **Opérateurs…**
puis sélectionnée en haut de la fenêtre. La préférence Qt enregistre
l’identifiant, et la création d’affaires, l’ajout de fichiers et les
vérifications réutilisent ce choix. Les identités historiques restent
disponibles dans SQLite pour préserver l’attribution de l’audit.
La création du même nom sélectionne la fiche présente.

| Parcours et code | Logique observée | Intégration |
|---|---|---|
| Création, import, preuves (`vigil/storage.py`, `vigil/desktop.py`) | Le champ de saisie libre créait une identité à chaque nouveau nom. | Fiche créée explicitement, sélection persistante et contexte lu avant le travail de fond. |
| Lecture d’index (`scripts/analyse/vigil_census_query.py`) | Connexion SQLite générique. Les arguments et données doivent rester distincts du lancement. | Modules → Consulter un index de recensement. Utilise une liste d’arguments, SQLite ouvert en lecture seule, budget de 100 lignes et délai, audit lié à l’affaire et à l’opérateur. |
| Recensement et analyses (`scripts/analyse/vigil_*.sh`, `scripts/vigil_scan_all.sh`) | Plusieurs scripts lisent des fichiers de sélection globale et attendent des confirmations. Répertoires de travail et de dépôt varient selon l’option. | Adapter argument par argument, figer le contexte et attribuer un dossier unique à chaque run. Vérifier destinations, formats et provenance de l’index avant l’activation. |
| Chasse, antivirus et signatures (`scripts/clamav/`) | Une chasse combine montage, audit, scan et publication. Les mises à jour peuvent modifier les signatures système. | Préserver le mode autonome. Raccorder les étapes après validation des sessions, protections et résultats partiels. |
| Montage, stockage et imagerie (`scripts/analyse/vigil_usb_*.sh`, `scripts/stockage/`, `scripts/imager/`, `scripts/Vigil-CLI/`) | Les scripts peuvent actionner le noyau et sélectionner des cibles en dialogue. | Exposer les actions après recette du broker, validation de l’identité et du RO, et contrôle des destinations. |
| Export et rapports (`scripts/export/`, `scripts/pdf/`) | L’export lit un projet vivant, le PDF reçoit du JSON et des logs. | Publier un lot figé et vérifié. Conserver les lecteurs des résultats historiques. |

Les parcours Qt actuels utilisent la base du Core. Les anciens profils,
presets et dossiers historiques ne sont pas synchronisés automatiquement.
Les commandes historiques conservent leurs points d’entrée. Le transport
PTY reste à raccorder à l’interface pour les scripts interactifs.

Recette sur profils et index synthétiques dans `tests.txt`. Retour par
revert du commit sur la branche dédiée. Les fiches et événements ajoutés
utilisent le schéma SQLite existant et restent lisibles par le Core.
