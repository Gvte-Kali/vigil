# Vigil

Application Linux d’analyse de supports numériques : montage en lecture seule,
analyses de fichiers, recherche de menaces et rapports PDF.
Pensée pour un poste dédié sous ParrotOS / Debian, avec une interface Python / Tkinter.

[Lire la documentation](https://gvte-kali.github.io/vigil/) · [Documentation dans le dépôt](docs/index.md)

## Vigil 2.0 sur Linux

La [CLI en développement](docs/development/linux-portability.md) s'installe
dans un environnement Python utilisateur et fonctionne sans session graphique.
Pour lancer l'espace de travail Qt sur un clone de la branche `vigil-2.0` :

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[desktop]'
.venv/bin/vigil2-gui
```

La [recette Parrot](tests.txt) couvre le sélecteur FR/EN, les affaires,
les preuves et les parcours historiques encore disponibles dans Tkinter.

## Installer la version historique

Placer le dépôt dans `/opt/vigil`, puis lancer :

```bash
cd /opt/vigil
bash scripts/post-install/post_install_vigil.sh
vigil
```

L'administrateur doit préparer les répertoires de travail et, sur un poste
existant, traiter la règle sudoers héritée avant le post-install. Voir la
[procédure de transition](docs/development/phase-01-transition.md).
Le script installe les dépendances et configure les raccourcis et ClamAV.
Le RDP est facultatif.
Voir [Installation](docs/installation/README.md) et `post-install-checked.txt`.

## Première analyse

1. Configurer l’entité et créer un utilisateur et un projet.
2. Dans **Analyser un périphérique**, sélectionner l’utilisateur et le projet.
3. Monter le support en lecture seule, puis lancer les analyses utiles.
4. Consulter les PDF dans `/opt/vigil/rapports/`.
5. Démonter le support et exporter le projet.

## Fonctions principales

| Fonction | Résultat |
|---|---|
| Analyse | Inventaire SQLite/TSV, métadonnées, doublons, fichiers chiffrés ou volumineux |
| Recherche de menaces | Triage USB, audit de format et ClamAV, sans projet |
| Imagerie | Images RAW/E01/AFF ou clonage vers un autre disque |
| Traçabilité | Opérateur, journal des actions et empreintes SHA-256 |
| Stockage | Montage en lecture/écriture pour les fichiers de travail |

La lecture seule repose sur des protections logicielles adaptées au support.
Un hash permet de vérifier un contenu ; une absence de détection antivirus ne garantit pas son innocuité.

## Développer

```bash
VIGIL_BASE="$PWD" VIGIL_DATA_DIR="$PWD/data" python3 gui/vigil_main_gui.py
```

| Dossier | Contenu |
|---|---|
| `gui/` | Interface et accès aux données |
| `scripts/` | Analyses, antivirus, imagerie, exports et génération PDF |
| `config/` | Correspondances de formats et signatures locales |
| `data/` | Configuration, profils, projets et icônes |
| `docs/` | Documentation Jekyll / Just the Docs, thème Graphite |

Les wrappers de `scripts/Vigil-CLI/` sont en cours de développement.
Le fonctionnement de l’application et les modules partagés sont décrits dans
[Interface graphique](docs/interface-graphique/README.md).
Pour construire le site localement, voir [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

## Licence

[GNU GPL v3](LICENSE).
