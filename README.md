# Vigil

[English](#english) · [Français](#français)

## English

Vigil is a Linux application for examining digital media. It supports read-only
mounting, file analysis, threat scanning, and PDF reports. It is designed for
a dedicated Parrot or Debian workstation and offers a Qt GUI and a Textual TUI.

[Read the documentation](https://gvte-kali.github.io/vigil/en/)

### Use Vigil on Linux

The CLI runs in a user-owned Python environment and works without a graphical
session. To open the Qt workspace from a repository clone, run:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[desktop]'
.venv/bin/vigil-gui
```

For an installation under `/opt/vigil`, follow the [launcher update instructions](https://gvte-kali.github.io/vigil/en/installation.html#update-an-existing-installation).
The [Parrot test guide (French)](https://gvte-kali.github.io/vigil/development/native-recette.md)
covers language switching, cases, evidence, and legacy Tkinter workflows.

### Install Vigil on Parrot or Debian

Follow the [fresh installation guide](https://gvte-kali.github.io/vigil/en/installation.html)
to set up `/opt/vigil`, its dependencies and launchers, and the ClamAV signature
profile. The [reset guide](https://gvte-kali.github.io/vigil/en/reset.html)
also covers APT packages.

### Run your first analysis

1. Configure the organization and select an operator.
2. Create and select a case in **Current case**.
3. Mount the source read-only from Vigil and run the relevant analyses.
4. Review the reports and unmount the source before quitting.
5. Export the case and verify its SHA-256 checksum.

### Key features

| Feature | Result |
|---|---|
| Analysis | SQLite/TSV inventory, metadata, duplicates, encrypted or large files |
| Threat scanning | USB triage, format auditing, and ClamAV scanning without a case |
| Imaging | RAW, E01, and AFF images or cloning to another drive |
| Traceability | Operator tracking, audit logs, and SHA-256 checksums |
| Storage | Read/write mounts for working files |

Read-only access relies on software protections suited to the source device.
Checksums verify content integrity. Antivirus results reflect what the scanner detected.

### Develop

```bash
python3 scripts/dev/workspace.py setup
python3 scripts/dev/workspace.py gui
```

| Directory | Contents |
|---|---|
| `gui/` | Legacy graphical interface and data access |
| `scripts/` | Analysis, antivirus, imaging, exports, and PDF generation |
| `config/` | File format mappings and local signatures |
| `data/` | Configuration, profiles, cases, and icons |
| `docs/` | Jekyll documentation using Just the Docs and the Graphite theme |

The wrappers in `scripts/Vigil-CLI/` are under development. See the
[graphical interface guide (French)](https://gvte-kali.github.io/vigil/interface-graphique/README.html)
for application workflows and shared modules.

### License

[GNU GPL v3](LICENSE).

## Français

Application Linux d’analyse de supports numériques : montage en lecture seule,
analyses de fichiers, recherche de menaces et rapports PDF.
Pensée pour un poste dédié sous Parrot ou Debian, avec une GUI Qt et une TUI Textual.

[Lire la documentation](https://gvte-kali.github.io/vigil/)

### Utiliser Vigil sur Linux

La [CLI](https://gvte-kali.github.io/vigil/development/linux-portability.md) s’installe
dans un environnement Python utilisateur et fonctionne sans session graphique.
Pour lancer l'espace de travail Qt depuis un clone du dépôt :

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[desktop]'
.venv/bin/vigil-gui
```

Pour une installation existante dans `/opt/vigil`, suivre [la mise à jour des lanceurs](https://gvte-kali.github.io/vigil/installation/README.html#mettre-à-jour-les-lanceurs-dune-installation-existante).

La [recette Parrot](https://gvte-kali.github.io/vigil/development/native-recette.md) couvre le sélecteur FR/EN, les affaires,
les preuves et les parcours historiques encore disponibles dans Tkinter.

### Installer Vigil sur un poste Parrot ou Debian

Sur Parrot ou Debian, suivre la [procédure d’installation depuis zéro](https://gvte-kali.github.io/vigil/installation/README.html#installer-et-lancer).
Elle prépare le site dans `/opt/vigil`, les dépendances, les lanceurs et le
profil de signatures ClamAV. Pour un poste déjà installé, la
[remise à zéro](https://gvte-kali.github.io/vigil/installation/desinstallation.html) couvre aussi les paquets APT.

### Première analyse

1. Configurer l’entité et choisir un opérateur.
2. Créer et sélectionner une affaire dans **Affaire en cours**.
3. Monter le support en lecture seule depuis Vigil, puis lancer les analyses utiles.
4. Consulter les rapports et démonter le support avant de quitter.
5. Exporter l’affaire et vérifier son empreinte SHA-256.

### Fonctions principales

| Fonction | Résultat |
|---|---|
| Analyse | Inventaire SQLite/TSV, métadonnées, doublons, fichiers chiffrés ou volumineux |
| Recherche de menaces | Triage USB, audit de format et ClamAV, sans projet |
| Imagerie | Images RAW/E01/AFF ou clonage vers un autre disque |
| Traçabilité | Opérateur, journal des actions et empreintes SHA-256 |
| Stockage | Montage en lecture/écriture pour les fichiers de travail |

La lecture seule repose sur des protections logicielles adaptées au support.
Un hash permet de vérifier un contenu ; une absence de détection antivirus ne garantit pas son innocuité.

### Développer

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
[Interface graphique](https://gvte-kali.github.io/vigil/interface-graphique/README.html).

### Licence

[GNU GPL v3](LICENSE).
