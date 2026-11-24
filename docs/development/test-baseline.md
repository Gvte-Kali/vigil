# Baseline de tests — phase 00

Référence `a2553ba`, Debian 13 trixie x86_64, Git 2.56.1, Bash 5.2.37, Python 3.12.14, SQLite 3.53.1. Aucun montage, accès à une preuve, sudo ou installation. Les essais exécutables utilisent uniquement une base SQLite synthétique temporaire.

| Commande ou observation | Résultat |
|---|---|
| `git ls-files '*.sh' scripts/Vigil-CLI/vigil \| while IFS= read -r f; do bash -n "$f" \|\| exit; done` | 30 fichiers, succès de syntaxe. |
| `PYTHONPYCACHEPREFIX=/workspace/work/vigil-pycache python3 -m py_compile $(git ls-files '*.py')` | 14 fichiers suivis au départ, succès de compilation. |
| `python3`, SQLite `:memory:`, `CREATE VIRTUAL TABLE probe USING fts5(value)` | Succès sur ce runtime. |
| `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v` | 2 tests réussis. Filtrage MIME/extension et projection TSV, codes pour filtre/base manquants, absence de création de la base manquante. |
| `git ls-files '*test*' '.github/*'` avant ajout | Seul todo_tests.txt, plan manuel et traces de tests historiques. |
| `shutil.which`, `importlib.util.find_spec` | file, jq, Tkinter, Pillow, ReportLab, Pydantic, PyYAML et psutil détectés. ClamAV, binwalk, Konsole, ewfacquire, affcat, dc3dd, ShellCheck, CairoSVG, pytest, PySide6 et Typer absents du runtime/du PATH inspecté. |
| Recherche auxiliaire avec `egrep` | Option ambiguë pour un motif commençant par des tirets ; remplacée par `rg` sur todo.txt. Aucun test concerné. |

Le check syntaxique et la caractérisation ne valident pas les parcours interactifs ni les installations. Les extraits de tests historiques dans todo_tests.txt ne sont pas des résultats de cette session. Aucun test d'interface, montage/démontage, acquisition/clonage, scan antivirus/ClamAV, mise à jour de signatures, export complet, post-install ou driver HID/MTP n'a été exécuté. Compatibilité Python 3.11 et distributions Kali/Parrot à confirmer. L'outil de requête a été choisi pour la caractérisation car il travaille sur le chemin SQLite passé en argument, sans lancer de collecte.

## Plan de référence et recette

| Périmètre | Fixture et assertions futures |
|---|---|
| Quatre livrables phase 00 | `git diff --check`, comparer liste des fichiers au tableau des livrables et les F01 à F27, contrôler SHA-256 du SVG et favicon, comparer section historique du todo à la référence. |
| Sécurité phase 01 | Unités pures et VM éphémère avec images synthétiques pour signatures RO et identités, refus de chemins aliasés, changement d'identité, contrôles de permissions, MTP simulé et lecture de bases checksafe structurées. Assertions dans [le plan](architecture-v2.md#phase-01-proposée-et-recette). |
| Parité fichiers | Fixture immuable avec noms Unicode et caractères de contrôle, doublons SHA-256, corpus bureaux/médias/archives, sparse, formats corrompus, MIME trompeurs et inconnus. Comparer SQLite, TSV, JSON, PDF normalisé, chemins et limites. |
| Imagerie et custody | En VM, images RAW/E01 synthétiques, AFF selon capacité vérifiée. Vérifier hashes, sélection partition, RO effectif, dossiers de run séparés et cleanup sur échec. |
| Processus et stockage | Simuler délai, annulation, crash, verrou et espace insuffisant, DB corrompue, export concurrent ; vérifier cohérence des états, logs et aucun écrasement. |
| GUI/CLI | CLI aide, JSON, codes, non-root ; Qt/Tk avec fixtures, filtres/presets et jobs entre pages, aucune régression logo, tests manuels de navigation. |
| Packaging et catalogue | Installation/migration sur Debian, Kali, Parrot séparés, dépendances absentes et offline ; intégrité archive, signatures invalides, rollback/rotation, traversée et isolation de modules. |
| Performances | Chronométrer et mesurer mémoire sur large corpus synthétique versionné ; mesurer seule et ensemble la collecte puis la lecture d'index. Fixer budgets après mesures. |

Recette manuelle phase 00 sur la branche dédiée. Relire les preuves et écarts de chaque ligne, reproduire les commandes sûres, confirmer l'accord avant la phase suivante. Retour documentaire par revert du commit phase 00 sur la branche, avec état initial `a2553ba` disponible pour comparaison.
