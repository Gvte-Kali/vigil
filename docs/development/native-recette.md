# Recette native de Vigil 2.0

Utiliser un compte ordinaire et un dépôt sur `vigil-2.0`. Prévoir deux VM avec instantané initial. La première peut être Parrot ou Debian. La seconde doit démarrer Arch Linux, idéalement dans une session Hyprland avec la configuration Omarchy à vérifier. Noter le commit, l’OS, le noyau, le compositeur et les versions Python et Qt avec les résultats.

## Préparation

    git switch vigil-2.0
    git pull --ff-only
    git rev-parse --short HEAD
    python3 scripts/post-install/install_native.py --profile complet --dry-run
    dev=$(mktemp -d)
    python3 scripts/dev/workspace.py --workspace "$dev" setup
    python3 scripts/dev/workspace.py --workspace "$dev" doctor
    python3 scripts/dev/workspace.py --workspace "$dev" test

Sur ton poste Omarchy, omettre `--workspace "$dev"` pour réutiliser `~/.local/share/vigil-dev`. Le dossier doit être privé et appartenir à l’opérateur. Le venv, les fixtures, la base, la custody, les journaux et les dossiers XDG du processus sont isolés dans ce dossier. Le mode recette bloque les opérations système et les modules externes, dont protection USB, montage, clonage et FreshClam. Le diagnostic peut lire l’inventaire du poste. La suite automatisée exerce aussi les chemins de production à l’aide de fixtures temporaires.

L’installateur détecte la distribution via `/etc/os-release`. Le profil `minimal` installe la CLI et Textual. `forensic` ajoute les paquets d’analyse au plan. `complet` ajoute PySide6 au venv et les dépendances du bureau au plan. Par défaut, seul le venv utilisateur est installé. `--dry-run` affiche le plan sans exécution. `--system-packages` autorise explicitement APT, Pacman, DNF ou Zypper à installer les paquets. Vérifier leur disponibilité et les hooks éventuels de la distribution avant d’utiliser cette option. La configuration des montages, d’UDisks2, de systemd et du bureau est distincte.

## Essais sans privilèges

    python3 scripts/dev/workspace.py --workspace "$dev" gui
    python3 scripts/dev/workspace.py --workspace "$dev" gui-legacy
    python3 scripts/dev/workspace.py --workspace "$dev" tui

Exécuter les deux lanceurs Qt séparément. Selon la session, répéter avec `QT_QPA_PLATFORM=xcb` sous X11 ou XWayland et avec `QT_QPA_PLATFORM=wayland` sous Wayland. Sous Hyprland, vérifier le focus des dialogues, la bascule de fenêtre et le retour de focus depuis le sélecteur. Lancer `doctor` dans chaque session pour connaître le backend Qt réellement initialisé. Compléter les tests hors écran par un essai interactif.

- Dans la GUI, choisir un opérateur, parcourir Accueil, Affaire en cours et ses onglets, Catalogue, Entité et Actions rapides. Vérifier FR/EN, clavier, souris, thème, actions contextuelles et dialogues sur une grande et une petite fenêtre.
- Créer une affaire, la sélectionner explicitement, importer `fixtures/legacy-case`, exporter l’affaire créée dans un sous-dossier vide de la recette et réimporter son archive Vigil 2.0. Vérifier le journal et l’annulation.
- Ajouter `fixtures/specimen.txt` comme preuve, ouvrir son aperçu et vérifier la copie SHA-256. Contrôler la configuration d’entité, les préférences au redémarrage et l’export du journal.
- Inspecter `fixtures/disk.raw` depuis la TUI ou avec `"$dev/venv/bin/vigil" evidence inspect-raw "$dev/fixtures/disk.raw"`. Attendre une table MBR et une partition à 512 octets. Cette image ne contient aucun système de fichiers à monter.
- Essayer une action système depuis chaque interface. Le mode recette doit l’arrêter sans ouvrir de terminal d’administration. Fermer normalement les deux interfaces, puis vérifier la persistance au redémarrage.
- Rejouer la checklist de [tests.txt](../../tests.txt). Consigner pour chaque contrôle le backend, le résultat attendu et le résultat observé.

## Essais privilégiés en VM

Utiliser une VM distincte, une installation Vigil supervisée, deux disques externes virtuels jetables identifiés de façon persistante et une autorisation explicite avant toute configuration privilégiée. Préparer une image de référence et son SHA-256. Relever les règles, services et montages initiaux sans les modifier.

1. Lancer la GUI supervisée puis répéter le scénario avec la TUI. Brancher la source synthétique et vérifier le blocage de l’automontage et son état RO. Monter via Vigil, puis vérifier l’identité, le RO sous `/investigation`, le recensement et le refus de fermer avec un montage actif.
2. Sélectionner le disque jetable. Vérifier le RW sous `/stockage`, le refus d’une destination trop petite et l’interdiction de sélectionner la source comme destination. Effectuer une acquisition RAW, puis un clonage sur la destination jetable. Vérifier les SHA-256 sur les mêmes plages de données.
3. Rejouer annulation, débranchement et opérations concurrentes. Démonter via Vigil, fermer et vérifier le rapport de restauration et l’état des périphériques. Comparer services et fichiers système à l’état initial.

Sur Arch, l’installateur natif ne met pas en place l’assistant privilégié Debian. Sans configuration privilégiée validée pour la VM, marquer ces essais en attente. Ne pas appliquer le post-install historique Debian sur Arch. Docker et Podman restent en dernière phase.
