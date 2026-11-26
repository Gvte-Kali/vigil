# Vigil

Application Linux d’analyse de supports numériques : montage en lecture seule,
analyses de fichiers, recherche de menaces et rapports PDF.
Pensée pour un poste dédié sous Parrot ou Debian, avec une GUI Qt et une TUI Textual.

[Lire la documentation](https://gvte-kali.github.io/vigil/) · [Documentation dans le dépôt](docs/index.md)

## Vigil 2.0 sur Linux

La [CLI](docs/development/linux-portability.md) s’installe
dans un environnement Python utilisateur et fonctionne sans session graphique.
Pour lancer l'espace de travail Qt sur un clone de la branche `vigil-2.0` :

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[desktop]'
.venv/bin/vigil-gui
```

Pour une installation existante dans `/opt/vigil`, suivre [la mise à jour des lanceurs](docs/installation/README.md#mettre-à-jour-les-lanceurs-dune-installation-existante).

La [recette Parrot](tests.txt) couvre le sélecteur FR/EN, les affaires,
les preuves et les parcours historiques encore disponibles dans Tkinter.

## Installer Vigil sur un poste Parrot ou Debian

Sur Parrot ou Debian, suivre la [procédure d’installation depuis zéro](docs/installation/README.md#installer-et-lancer).
Elle prépare le site dans `/opt/vigil`, les dépendances, les lanceurs et le
profil de signatures ClamAV. Pour un poste déjà installé, la
[remise à zéro](docs/installation/desinstallation.md) couvre aussi les paquets APT.

Voir [Installation](docs/installation/README.md) et `post-install-checked.txt`.

## Première analyse

1. Configurer l’entité et choisir un opérateur.
2. Créer et sélectionner une affaire dans **Affaire en cours**.
3. Monter le support en lecture seule depuis Vigil, puis lancer les analyses utiles.
4. Consulter les rapports et démonter le support avant de quitter.
5. Exporter l’affaire et vérifier son empreinte SHA-256.

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
python3 scripts/dev/workspace.py setup
python3 scripts/dev/workspace.py gui
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
