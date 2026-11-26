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


## Actions rapides et contrôle au démarrage

La branche main associe le scan ClamAV aux archives et alertes de chiffrement,
la mise à jour à un service système et le stockage à des opérations privilégiées
(montage et passage RW). Qt exécute ClamAV sur un fichier choisi et FreshClam
dans le profil utilisateur après confirmation réseau, dans un terminal PTY
intégré. Les limites et codes de sortie restent ceux des outils. L’action
stockage inventorie les périphériques ; l’administrateur reste responsable
du montage pendant la transition du broker. Le tableau de bord lit le RO
bloc via lsblk au démarrage et conserve l’état des montages séparément.
Un état déclaré RO ne garantit pas la protection physique d’une preuve.

## Rapports antivirus

Actions rapides demande le nom du PDF avant le triage. Entrée propose
`rapport_antivirus_AAAA-MM-JJ_HH-MM-SS.pdf`. Le parcours complet enregistre le
PDF dans le dossier dédié à l’exécution, avec le nom saisi. Un même nom peut
donc servir à deux scans distincts. Le PDF et son index de résultat sont
publiés sans écrasement.

Le PDF réunit le contexte, le relevé USB, ClamAV, les limites et la conclusion.
Les journaux individuels et le relevé JSON sont conservés. Un résumé absent,
une sortie scanner en erreur, un écart de couverture ou un triage incomplet
sont traités comme un résultat incomplet ou un échec. Une menace détectée
avec un scan complet reste un résultat valide. Le catalogue utilise les
métadonnées enregistrées pour les nouveaux rapports. Les anciens PDF sans
résultat documenté affichent « Résultat inconnu ». Leur date reste vide si
elle ne peut pas être lue dans le nom historique.

### Base de signatures ClamAV

FreshClam et ClamScan utilisent le répertoire `clamav` à côté de la base
SQLite de Vigil. Tous les scripts de scan passent ce chemin explicitement à
ClamScan. Une base `main` ou `daily` absente, illisible, ambiguë ou que le
moteur ne peut pas charger arrête le scan. La base système n’est jamais un
repli automatique. Le scan rapide s’exécute avec les droits de l’opérateur
lorsque l’arborescence est lisible. L’analyse d’une affaire reste sans sudo.

Le terminal et le PDF indiquent la version du moteur ainsi que la révision,
la date et l’âge de `daily`. Au-delà de sept jours, le terminal propose
une mise à jour, une poursuite hors ligne explicite ou l’annulation.
FreshClam et ClamScan sont vérifiés après mise à jour dans le même
répertoire, et la révision annoncée par FreshClam doit correspondre au
relevé de `daily`. Un avertissement FreshClam sur le moteur est enregistré
séparément de la fraîcheur des signatures. Sans avis connu pour cette
version du moteur, l’état du moteur reste « non vérifié ».

    vigil antivirus status
    vigil antivirus update
    vigil antivirus scan /chemin/vers/un/fichier
    vigil antivirus scan /chemin/vers/un/fichier --offline

`--db` sélectionne un profil particulier. En mode non interactif, un scan
avec des signatures obsolètes exige `--offline`.
