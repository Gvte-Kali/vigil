# Portabilité des affaires Vigil

## Audit du format précédent

Au commit `7645c5b`, `desktop.py:1260` appelait `export_case` pour compresser
les preuves et fichiers d’affaire. `case_export.py:132` produisait le manifeste
v2. Les entrées d’import dans `desktop.py:1456` et `cli.py:71` traitaient
uniquement les dossiers avec `info.json`. La base SQLite et les fichiers
n’étaient donc pas reconstructibles par ce parcours. Les rapports JSON produits
par `reporting.py` étaient rangés hors du dossier d’affaire et omis de l’archive.

## Matrice de couverture

| Élément | Stockage source | Export v3 | Restauration | Vérification |
|---|---|---|---|---|
| Nom, référence, description, dates et ID | SQLite | `affaire.json` | SQLite | Schéma et SHA-256 |
| Opérateurs et provenance | SQLite, audit | Identifiants et noms de l’audit | Identités archivées distinctes | Schéma, FK et mapping |
| Preuves, tailles et SHA-256 | SQLite | Métadonnées de chaque preuve | SQLite | Schéma et correspondance avec la copie |
| Copies enregistrées | `preuves/<id>/contenu` | `preuves/` si présentes | Copies locales en mode 0400 | Taille, SHA-256 et contrôle en staging |
| Sources originales | Chemins dans SQLite | Références historiques | Métadonnées uniquement | Cohérence du manifeste |
| Résultats, journaux d’exécution, et custody fichiers | Dossier local | `resultats/` | Dossier d’affaire | SHA-256 et taille |
| Audit SQLite | Tables d’audit | Événements jusqu’au point de coupure | Audit avec provenance | Séquences, FK et SHA-256 |
| PDF locaux | Dossiers d’analyse et `rapports/` | `resultats/` | Structure reconnue par l’onglet PDF | SHA-256 et taille |
| Rapports JSON | `data/state/reports`, identifiés par l’ID | `resultats/rapports-json/` | Dossier d’affaire | SHA-256 et taille |
| Recensements et annexes | SQLite et fichiers d’affaire | `resultats/` | Chemins internes locaux | SHA-256 et taille |
| Projet historique | Dossier Vigil 1.0 importé | `projet-v1/` | Sous-dossier local | SHA-256 et taille |
| Images disque et ressources externes | Emplacement choisi par l’opérateur | Seulement si fichier régulier réellement présent dans le périmètre local | Aucune ouverture d’un chemin original | SHA-256 si inclus |
| Préférences, secrets et autres affaires | Emplacements globaux | Hors périmètre | Hors périmètre | Sans objet |

## Format v3

Le conteneur est un TAR compressé gzip. L’export publie ensemble
`affaire.tar.gz` et `affaire.tar.gz.sha256`. Le lecteur accepte les manifestes
v2 et v3. Chaque nom de fichier est relatif au TAR. `SHA256SUMS` recense
exactement tous les fichiers réguliers sauf lui-même. Les échappements GNU
pour les noms Linux sont conservés. Un unique marqueur de répertoire
`preuves/` est permis. Les champs du manifeste sont les suivants.

| Champ | Format et sens |
|---|---|
| `schema_version` | Entier 3. Le lecteur accepte aussi 2 |
| `vigil_version` | Version du paquet exportateur |
| `exported_at`, `operator` | Date ISO 8601 avec fuseau et nom de l’exportateur |
| `case` | `id`, `name`, `created_at`, références historiques et champs facultatifs `reference` et `description` |
| `coverage` | `complete` si la copie de chaque preuve répertoriée est embarquée, sinon `partial` |
| `missing_evidence_count` | Nombre exact de copies absentes |
| `evidence[]` | `id`, `case_id`, `path` historique, `size`, `sha256`, `copy_status` et `archive_path` |
| `audit[]` | Séquence, timestamp, action, opérateur et détails d’origine, avec identifiant d’opérateur et provenance lorsqu’ils existent |
| `audit_cutoff` | Dernière séquence incluse, ou null |
| `members` | Dictionnaire chemin vers taille pour toutes les données archivées, hors manifestes |
| `source_archive` | Reçu de provenance si l’affaire a été importée, ou null |

`archive_path` vaut `preuves/<id>/contenu` pour une copie incluse et null pour
une copie manquante. Le schéma v2 utilise les mêmes champs de preuve. Il
ne fournit pas nécessairement la version de Vigil, les tailles des résultats,
le point de coupure explicite ni l’identifiant de l’opérateur.

## Cohérence et publication

L’export fige les métadonnées, la liste de preuves et le dernier événement
dans une transaction courte. Il synchronise les PDF puis fige la liste
des fichiers et les identités stat. La compression et la vérification du
lot s’exécutent hors verrou SQLite. Avant publication, Vigil compare de
nouveau les références aux preuves et les fichiers sélectionnés. La GUI
attend la fin des opérations qu’elle a lancées. En CLI, attendre la fin
des producteurs externes avant l’export. Le statut « complet » décrit les
copies de preuves incluses. La création d’une archive n’inclut ni un
inventaire de tous les supports ni une garantie de fraîcheur. L’événement
`case.export.success`, écrit à la publication, est postérieur à la coupure.

L’import vérifie le gzip, les entrées TAR, les empreintes, les tailles,
le manifeste et le checksum externe s’il existe. Un SHA-256 permet de
comparer des octets. L’authenticité de l’émetteur dépend d’un canal de
confiance indépendant. Le parcours Qt confirme le SHA-256 prévisualisé
avant publication. Les quotas par défaut sont de 200 000 entrées,
32 Mio par manifeste, 128 Gio de données décompressées, 1 024 octets
par chemin et 255 octets par composant. Le service vérifie aussi l’espace
disponible. Les valeurs sont configurables via `ArchiveLimits` dans l’API.
Les protections excluent les membres spéciaux, les liens, le sparse TAR,
les chemins absolus, les traversées et les collisions.

L’import écrit d’abord dans un staging privé au sein de `legacy-custody`.
Il vérifie les copies sur disque, inscrit les données SQLite dans une
transaction, écrit un marqueur de publication, renomme le staging et
synchronise le répertoire parent avant le commit. Une exception normale
annule SQLite et déclenche le nettoyage. Après un arrêt brutal, fermer
Vigil, lire le fichier `.vigil-import` et comparer `case_id` et `sha256`
à la table `case_archives`. S’il n’existe aucun reçu concordant, conserver
le dossier marqué hors du stockage actif pour inspection, puis retenter
l’import depuis l’archive originale. Si le reçu correspond, le dossier
est publié et son marqueur résiduel peut être retiré. Un staging
`.vigil-import-*` résiduel ne figure pas dans la liste des affaires.

## Identités, audit et limites

Vigil garde les ID libres et attribue des ID distincts en cas de conflit.
Deux archives de SHA-256 différents donnent deux affaires distinctes
en cas de conflit, même si l’une est une version plus complète. Les
homonymes ont des dossiers distincts. Un SHA-256 déjà importé désigne la
même affaire locale. Si elle a été retirée de la liste, l’import refuse
de la recréer silencieusement. Les reçus et mappings sont enregistrés
dans la base. Une vérification répétée porte sur l’archive, et la
vérification de l’affaire locale reste une opération indépendante.

Les événements historiques gardent timestamp, action, détails, ordre et
opérateur d’origine. Leur séquence locale est distincte. Une provenance
conserve le numéro source, l’archive et l’affaire d’origine, et reste
présente après réexport. Les noms d’opérateurs homonymes ne suffisent pas
à fusionner les identités. Les anciens manifestes sans identifiant
d’opérateur permettent uniquement une correspondance par nom dans
l’archive source. Le journal signale les événements importés et ajoute
séparément `case.archive.import`.

Les résultats archivés restent historiques. Les chemins absolus qu’ils
contiennent gardent leur sens d’origine. La consultation des preuves
restaurées utilise la copie locale. Pour une preuve référencée sans
contenu, la vérification est bloquée jusqu’au rattachement explicite
d’une source dont la taille et le SHA-256 correspondent. Les chemins
internes d’exécution et les index sont restaurés sans relancer d’analyse.
Les résultats externes, fichiers spéciaux et liens ne sont pas embarqués.

Schéma SQLite 5. Sauvegarder `data/state` avant la mise à jour. Pour
revenir à une version antérieure, restaurer la sauvegarde et conserver
séparément les archives créées depuis. Le lecteur antérieur ne connaît
pas le schéma v3.
