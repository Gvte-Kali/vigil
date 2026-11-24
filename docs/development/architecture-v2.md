# Architecture cible Vigil 2.0

Proposition issue de SPECIFICATIONS.md joint (§2–9) et de l'[audit de référence](phase-00-audit.md). La phase 00 s'arrête à la conception.

## Contrats

| Composant | Interface et invariants |
|---|---|
| Registre | `discover(sources) -> manifests, errors`, `get(id, version)`, `list(filters)`. IDs namespacés, doublons signalés, provenance observable ; l'interface affiche les manifestes découverts. Remplace à terme `gui/vigil_tools_gui.py:87–180`. |
| Manifeste | YAML safe_load sous quota et modèle Pydantic strict, champs supplémentaires et clés dupliquées rejetés. Schéma versionné, identifiant, nom et description FR/EN, version, API, catégorie, tags, auteur/licence, entrypoint relatif, types source, paramètres typés, capacités, dépendances et versions, sorties et reprise. |
| Capabilities | `probe(requirements, evidence) -> checks` avec disponible, manquant, dégradé, interdit et explication. Distinguer dépendance, permission, isolation, format et protection effective. Une déclaration donne une demande à la politique d'exécution ; le contrôle relève du broker et de l'isolation OS. |
| Contexte | `RunContext` sérialisé une fois au lancement, ID affaire ou session autonome, opérateur, ID preuve, identité physique/logique et état protection, module/version/digest, outils et paramètres, UTC. Les adaptateurs reçoivent ce contexte par arguments/env autorisés, sans relire la sélection UI globale (`gui/vigil_data.py:33–34`). |
| Runner | `submit(context)`, `cancel(run_id)`, `retry(run_id)`, `events(run_id, since)`. Adaptateurs argv, aucun shell arbitraire, cwd propre, env filtré, stdout/stderr bornés, sorties et codes validés. Un run lourd par défaut et verrou d'identité source/destination. |
| Stockage | SQLite migrations numérotées avec sauvegarde vérifiée, transactions courtes, FK, IDs stables, verrous d'écrivain. Tables affaires, opérateurs, preuves/acquisitions, modules, runs/tentatives, événements, fichiers, artefacts, relations, annotations, collections et rapports. FTS5 pour métadonnées autorisées ; fichiers volumineux hors SQLite dans run/<id>/ avec index et empreintes. |
| Événements | JSON versionné `schema_version, run_id, seq, timestamp_utc, type, severity, payload` ; validation aux frontières. États queued/running/succeeded/partial/failed/cancelled/skipped/interrupted ; transitions contrôlées et événement terminal durable. Progression numérique seulement si mesurable. Custody historique préservée et liée à l'audit structuré. |
| CLI/GUI | Core Python 3.11+ sans Qt. Typer pour doctor/modules/cases/evidence/run/jobs/search/reports avec aide, JSON sur stdout et diagnostics sur stderr ; conventions de code stabilisées en 02. Qt Widgets/PySide6 pour pages, modèles paginés, FR/EN, Graphite/Cyan et logo existant. Services partagés et CLI autonome. |
| Rapports | Adaptateur JSON/log → `scripts/pdf/vigil_pdf.py:2277–2307`. Métadonnées, provenance, couverture, statistiques et limites, empreintes. Publier le lot après contrôle de cohérence et validation du manifeste sur l'ensemble figé. |

### Cycle de vie sans daemon

Au lancement, GUI et CLI ouvrent l'état local et initialisent leur gestionnaire. GUI démarre les enfants à la demande, conserve leur propriété entre pages, journalise PID et identité de démarrage. Chaque tâche possède son groupe ; arrêt coopératif, délai borné, arrêt forcé du groupe détenu si nécessaire puis nettoyage vérifié. Un verrou du magasin empêche deux interfaces de prendre la même réservation. À la fermeture GUI, attendre ou annuler. Au redémarrage, réconcilier les runs orphelins en interrupted, conserver leurs fichiers ; aucun redémarrage automatique. Le retry crée une tentative distincte ou reprend un checkpoint validé par module et identité. Les statuts et locks prennent en compte le recyclage de PID. Les parseurs et modules non fiables sont soumis à leurs protections même lorsqu'ils sont lancés par un adaptateur.

## Migration et coexistence

1. Phase 01 sécurise explicitement les parcours historiques. Conserver Tkinter, les chemins de lecture et le PDF.
2. Phase 02 ajoute le Core et les adaptateurs derrière entrées distinctes pendant la coexistence. Le nom installé `vigil` appartient actuellement à Tk (`post_install_vigil.sh:96–100`). Basculer l'alias après recette avec accès documenté aux anciennes entrées. Presets convertis via une table chemin → ID/version et erreurs en cas d'élément non reconnu.
3. Phase 03 importe depuis une copie des données historiques. Sauvegarder sources, base et empreintes, produire un rapport d'import, conserver originaux, identifiants, provenance et champs non interprétés, garantir idempotence et transactions. Export PDF et dossiers existants restent lisibles.
4. Phases 04–08 migrent par parcours et gardent Tk tant que la matrice, les cas négatifs et l'installation n'ont pas été acceptés. Chaque parcours activé a une procédure de retour et un mapping d'entrées/sorties.

Versions indépendantes pour Core (SemVer), API des modules, schémas manifestes/événements/résultats et migrations SQLite. Un Core refuse les versions inconnues avec diagnostic. Rollback applicatif via version installée précédente et alias préservés. Pour une migration incompatible, ouvrir la sauvegarde vérifiée sur un emplacement distinct et exporter les nouveaux runs avant retour. Garder versions utilisées, hashes et fichiers de résultat disponibles en lecture.

## Catalogue GitHub séparé

Proposition `Gvte-Kali/vigil-modules`. L'index JSON contient `schema_version, sequence, generated_at, expires_at, modules[]`. Chaque entrée contient `id, version, author, licence, category, description{fr,en}, core_range, api_range, dependencies, release_url, size, sha256, key_id, signature, review_status`. Séparer built-in, officiel revu et import local. Publier le schéma et les octets signés, fixer une canonicalisation JSON, épingler les clés de confiance, vérifier signature index et release et le SHA-256 de l'archive. Rotation et révocation par métadonnées signées avec clés hors CI. Contrôler anti-retour (séquence/version) et expiration pour empêcher réutilisation silencieuse d'un ancien catalogue. Cache authentifié pour consultation et usages locaux hors ligne.

PR testées sur fixtures, validation schéma et archive, build CI isolé sans secrets et revue humaine des diffs, dépendances, licences et capacités. Publier un asset référencé par digest. Installation après consentement, HTTPS avec destinations autorisées et redirections revalidées, quota, extraction staging sans chemins absolus, traversée, liens ou entrées spéciales, puis activation atomique. Maintenir la version précédente, interdire activation ou retrait pendant un run, conserver résultats historiques. Aucun apt/pip/sudo ou hook automatique.

| Menace | Contrôle proposé |
|---|---|
| Publication compromise, archive substituée, gel/retour de version | Signatures, clés épinglées et révocables, anti-retour, limite temporelle, contrôle taille/digest. |
| Module, dépendance ou preuve hostile | OS sandbox non privilégiée, preuve montée RO en vue minimale, seul dossier de résultats RW, réseau refusé, limites CPU/RAM/disque/processus, env nettoyé. Défaillance de l'isolation entraîne refus. |
| Fuite de preuves, secrets ou fichiers utilisateur | Pas de remontée de données d'affaire, FD hérités fermés, aucun accès aux volumes ou HOME hors mises à disposition, logs filtrés. |
| Sortie non conforme ou épuisement des ressources | Valider le schéma, quotas stdout/stderr et fichiers, budget de temps, isoler le lot partiel. |
| Escalade | Communauté sans capacité privilégiée, aucun accès au broker ; UID distinct selon disponibilité de l'isolation. |

## Phase 01 proposée et recette

1. Dresser la table des opérations privilégiées existantes et migrer chacune vers une API de verbes fermés. Provisionner sous contrôle root le binaire/config et groupe `vigil-operators`. Vérifier sur VM synthétique que les utilisateurs hors groupe, arguments inattendus et chemins substitués sont refusés et que l'installation ne laisse aucune règle NOPASSWD générique.
2. Désactiver la désérialisation pickle externe et remplacer par SQLite/TSV validé. Recette nom/hash, données limites et invalides, fichier absent, compatibilité sémantique avec fixtures structurées de confiance.
3. Vérifier identité parent/partition, RO bloc et montage séparément avant analyses. Tester montage et parent divergents, alias/symlink/bind, changement d'identité entre validation et action, liens vers la source et MTP simulé. Refuser strictement sur état indéterminé ; en triage tracer limites et décision opérateur.
4. Capturer le contexte avant lancement et attribuer une destination unique. Tester deux runs, changement de sélection, interruption, espace insuffisant et export concurrent. Recette custody début/fin/échec/annulation, intégrité sur lot figé, résultats antérieurs accessibles.
5. Valider sur VM jetable avec images synthétiques, vérifier différences de manifests et hashes source avant/après ; retenir les anciennes entrées le temps de comparer les sorties. Toute politique permissive historique doit rester désactivée si une régression impose un retour.

Rollback de phase 01 à tester en VM via snapshot d'installation et sauvegarde vérifiée des données/configurations, restauration de la version applicative et accès en lecture aux résultats nouveaux. Désactiver les parcours privilégiés dont le retour réintroduirait les risques identifiés ; restaurer les mécanismes autorisés uniquement après nouvelle recette et accord. Validation humaine avant mise en service.


## Sauvegarde à la fermeture de Qt

La fermeture ordinaire demande une confirmation en FR ou EN. Les opérations
en cours doivent aboutir et terminer leurs transactions avant la fermeture.
Les mutations des affaires et preuves sont déjà enregistrées dans SQLite
au moment de l’action. La fermeture vérifie l’affaire active et synchronise
les préférences locales. Une erreur conserve le workspace ouvert.
L’affaire active appartient à la session. À chaque lancement, une confirmation
explicite est requise pour rattacher les opérations à une affaire.

Tout futur éditeur ou module Qt qui garde des données modifiées en mémoire
doit les enregistrer via la frontière `Workspace.save_before_close`,
en les liant aux identifiants d’affaire capturés au début de l’édition
ou du run. Les résultats et brouillons doivent être enregistrés dans les
emplacements de travail et avec les transactions prévues, en respectant
la custody. Un échec doit remonter à la fenêtre et permettre de réessayer.
Ne jamais transférer les données d’une autre affaire vers celle affichée.


### État système de la session Qt

Au lancement, Vigil conserve un instantané JSON dans `system-snapshots`
à côté de la base SQLite. Il contient les états RO/RW visibles dans sysfs,
les identités bloc et les montages des deux zones. À la fermeture, les
zones /investigation et /stockage doivent être démontées, sous-montages
compris, y compris en présence d’un montage qui précédait Vigil. Un écart RO/RW sous un même nom de périphérique est détaillé et doit
être confirmé pour fermer. Une différence d’identité seule ne déclenche
plus d’invite. Une erreur de lecture empêche la fermeture.
La vérification est répétée après la sauvegarde.

Cette vérification observe l’espace de montage de la GUI et les modes
du noyau. La réconciliation se fait hors GUI sous la responsabilité de
l’administrateur. Vigil ne remet jamais un périphérique en écriture pour
quitter.
