# Vigil 2.0

## Branche et ordre de travail

- Travailler exclusivement sur `vigil-2.0`. Utiliser `vigil` comme commande publique.
- Suivre la roadmap active de `todo.txt`. Conserver les acquis et le backlog historique. Livrer par lots cohérents avec tests de non-régression et validation humaine entre phases.
- Priorité à l’installation Linux native, aux services Core et à la parité Textual. Migrer les parcours au fil de la disponibilité de leurs services. Garder la GUI Qt fonctionnelle et limiter ses évolutions aux corrections et à la compatibilité pendant la transition.

## Core, interfaces et forensique

- La TUI Textual, la CLI Typer et la GUI consomment les mêmes services Core. Préserver les fonctions existantes et valider leur remplaçant avant retrait.
- Faire de Textual l’interface principale, au clavier et à la souris. Conserver le logo, Graphite/Cyan, les couleurs sémantiques et FR/EN. Intégrer le suivi des opérations en TUI, y compris en SSH et headless.
- Après validation de la TUI, `vigil` et `vigil tui` la lancent, `vigil gui` ouvre la GUI. Préserver `vigil --help`, `vigil --version` et les sorties JSON automatisables.
- Utiliser le triage d’« Affaire en cours » comme référence. Transmettre un contexte structuré aux opérations et revérifier identité et protections avant les opérations sensibles. Préserver `/investigation` RO, `/stockage` RW, l’accès bloc direct lorsque nécessaire, la chaîne de custody et la restauration système. Conserver les mécanismes de copie, de synchronisation et de vérification SHA-256.
- Privilégier XDG, la détection des dépendances et les adaptateurs système. Cibler Debian, Ubuntu, Kali, Parrot, Fedora, Arch et openSUSE. Limiter les privilèges aux opérations qui en ont besoin et éviter tout daemon permanent.

## Docker et Podman

- Reporter intégralement Docker et Podman à la dernière phase de `todo.txt`, après validation de la parité TUI, des protections forensiques et de la release native multi-Linux.
- Jusqu’à cette phase, exclure Dockerfile, Containerfile, images, intégration CI et travaux d’empaquetage ou de tests conteneurisés. Garder les contrats d’exécution découplés du système de lancement et développer les adaptateurs natifs requis.
- En dernière phase, traiter Docker et Podman comme une couche facultative de portabilité, de reproductibilité et d’isolation supplémentaire. L’installation, le développement, les tests et l’usage natifs restent possibles sans ces moteurs.
