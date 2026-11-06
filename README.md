# Vigil

Application Linux d’analyse de supports numériques : montage en lecture seule,
analyses de fichiers, recherche de menaces et rapports PDF.
Pensée pour un poste dédié sous ParrotOS / Debian, avec une interface Python / Tkinter.

[Lire la documentation](https://gvte-kali.github.io/vigil/) · [Documentation dans le dépôt](docs/index.md)

## Installer

Placer le dépôt dans `/opt/vigil`, puis lancer :

```bash
cd /opt/vigil
sudo bash scripts/post-install/post_install_vigil.sh
vigil
```

Le script installe les dépendances et configure le poste : montage automatique,
règles sudo, raccourcis et ClamAV. Le RDP est facultatif.
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
