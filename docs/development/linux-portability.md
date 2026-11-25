# Vigil 2.0 sur Linux

Le socle CLI requiert Linux et Python 3.11+ et s'installe dans un
environnement utilisateur. Il utilise SQLite et ne charge ni Tk ni Qt.
Le paquet Python contient le socle et les manifestes. Les scripts historiques
et la GUI Tk restent dans la distribution du dépôt.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/vigil2 doctor
.venv/bin/vigil2 modules list
```

Cible de validation Debian/Kali/Parrot, Fedora, Arch, openSUSE et Alpine,
sur les architectures où Python et les dépendances sont disponibles.
Sur musl ou une architecture dépourvue de wheel, le runtime Python et ses
dépendances compilées doivent être fournis par la distribution ou construits
en environnement isolé. Le post-install historique reste spécifique à APT.
Les outils d'analyse et pilotes (ClamAV, libewf, libaff, FUSE, util-linux)
sont des capacités à vérifier individuellement.

La GUI Tk choisit `xdg-terminal-exec` s'il est installé, puis recherche
Konsole, GNOME Terminal, XFCE Terminal, kitty ou xterm. Installer Tk et un
terminal utilisable dans la session. Tk repose sur X11, donc XWayland est
nécessaire dans une session Wayland. Le workspace Qt utilise les plugins de plateforme Qt pour X11 ou Wayland
selon la session et ne dépend pas d'un gestionnaire de fenêtres précis.
Installer l'extra `desktop` et lancer `vigil2-gui` depuis le venv.
La [recette Parrot](../../tests.txt) détaille la bascule FR/EN persistante,
les parcours Qt disponibles et la coexistence avec Tk. Le transport PTY possède un terminal de contrôle, reçoit les frappes et
le redimensionnement. Son raccordement aux adaptateurs et au futur
émulateur du panneau Qt reste à réaliser.

## Recette des phases 02 et 03

Le registre local valide ses manifestes et liste neuf analyses existantes.
Les descripteurs actuels documentent des chemins historiques et des
dépendances minimales. Le diagnostic inspecte le PATH et la session,
sans exécuter les outils. Les commandes produisent du JSON.

```bash
vigil2 cases create 'Affaire exemple' --operator Alice
vigil2 cases list
vigil2 cases import /chemin/vers/copie-projet --operator Alice
vigil2 evidence add ID_AFFAIRE /chemin/vers/fixture.raw --operator Alice
vigil2 evidence verify ID_PREUVE --operator Alice
vigil2 evidence inspect-raw /chemin/vers/fixture.raw
```

La base v1 est initialisée transactionnellement dans
`$XDG_STATE_HOME/vigil/cases.sqlite` ou `~/.local/state/vigil/cases.sqlite`.
`--db` permet de placer la base sur un volume de travail dédié ; réserver
ce chemin aux métadonnées Vigil. Codes 0 pour succès, 1 pour erreur
applicative et 2 pour écart d'intégrité ou erreur d'usage. L'import est
idempotent pour un même chemin canonique et conserve le JSON brut.
Les rapports et la custody restent référencés à leur emplacement historique.
L'enregistrement calcule SHA-256 sur un fichier régulier ouvert en lecture
seule et contrôle ses métadonnées pendant le calcul.

L'inspection RAW vérifie SHA-256 et décrit les partitions MBR primaires
sur un fichier régulier en lecture seule. Elle signale les formats et
tables qui nécessitent un lecteur dédié.

Restent ouverts en phase 02 l'intégration du runner et son contrat événements/résultats,
les adaptateurs d'exécution et la recette des presets, multi-scans et chasse
autonome. Restent ouverts en phase 03 la migration complète des livrables,
l'historique des runs, et l'ouverture de partitions RAW/E01/AFF avec
contrôle RO et nettoyage. Aucun parcours privilégié n'est exposé par la
nouvelle CLI. Sa recette dépend des protections de phase 01.

La recette automatisée utilise `python -m unittest discover -s tests -v`
avec les dépendances du paquet installées. Recette graphique et multi-distribution
à effectuer sur X11, Wayland/XWayland et XWayland absent, avec différents
gestionnaires de fenêtres. Pour revenir à la version précédente, révoquer
le commit correspondant ou désinstaller le paquet de l'environnement
virtuel. Conserver la base et les projets sources pour reprise.

La CLI peut aussi vérifier et restaurer un transfert d’affaire.

```sh
vigil2 cases verify-archive /chemin/affaire.tar.gz
vigil2 cases import-archive /chemin/affaire.tar.gz --operator Alice
```

Le chemin peut désigner le dossier d’export. La commande retourne du JSON
sur stdout. Le code 0 signale un succès, y compris une archive valide
partielle. Le code 1 signale un échec et le diagnostic paraît sur stderr.
Typer retourne 2 en cas d’erreur d’usage.
