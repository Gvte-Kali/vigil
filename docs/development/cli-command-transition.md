# Transition de la commande Vigil

## Inventaire initial

À `d52c902`, la recherche `git grep -ni vigil2 HEAD` trouvait 26 lignes
suivies, dont une clé de préférences Qt.

| Fichier | Occurrences | Rôle |
|---|---:|---|
| `pyproject.toml` | 2 | Points d’entrée Python CLI et graphique |
| `scripts/post-install/vigil-qt` | 1 | Appel du lanceur graphique dans le venv |
| `vigil/desktop.py` | 1 | Nom de l’ancien magasin QSettings `Vigil2` |
| `README.md` | 1 | Démarrage Qt |
| `docs/actions/export.md` | 3 | Exemples CLI d’export et d’import |
| `docs/development/linux-portability.md` | 11 | Exemples CLI et démarrage Qt |
| `tests.txt` | 7 | Chemins du venv et commandes de recette |

Les fichiers cachés suivis et les appels construits n’introduisaient
aucun autre point d’entrée. Le conflit indirect venait de
`scripts/post-install/post_install_vigil.sh`, qui liait
`/usr/local/bin/vigil` au lanceur graphique et utilisait ce même nom dans
le fichier desktop. La branche `main` liait historiquement cette commande
au GUI Tkinter. `scripts/Vigil-CLI/vigil` est un brouillon historique
conservé avec les adaptateurs. Le packaging ne publie pas ce brouillon
dans le PATH. Aucun workflow, service ou fichier de complétion suivi ne
déclarait l’ancienne commande.

## Installation et migration

Le paquet installe `vigil` pour Typer et `vigil-gui` pour Qt. Sur un poste
installé dans `/opt/vigil`, `vigil` pointe vers le venv du site. Le fichier
desktop appelle le lanceur stable `/opt/vigil/scripts/post-install/vigil-qt`.

Depuis la session opérateur, après mise à jour de la branche, lancer
`bash /opt/vigil/scripts/post-install/update-cli.sh`. Le script vérifie les
emplacements gérés avant de réinstaller le paquet dans le venv. Il teste le
nouveau point d’entrée, remplace le lien connu dans `/usr/local/bin`,
retire les lanceurs hérités reconnus dans `/usr/bin`, `/usr/local/bin`,
le venv et `~/.local/bin`, puis met à jour le raccourci système reconnu.
Il vérifie aussi la résolution par le PATH. Le script ne lit ni ne migre
les données d’enquête et ne relance aucune configuration système.

L’identification s’appuie sur les cibles exactes des liens connus, les
lanceurs générés par le packaging du venv du site ou le brouillon
historique identique au fichier du dépôt. Un conflit avec une autre
commande `vigil` stoppe la migration et indique le chemin à examiner.
Un ancien nom dont le propriétaire ne peut pas être prouvé est conservé.
Pour un autre venv, réinstaller le paquet depuis cet environnement. Pour
une installation dans un préfixe géré par la distribution, demander
l’intervention de son gestionnaire. Un alias shell ou un raccourci
personnalisé doit être vérifié dans sa propre configuration. Les raccourcis
personnalisés peuvent utiliser `Exec=/opt/vigil/scripts/post-install/vigil-qt`.

La complétion Typer utilise `_VIGIL_COMPLETE`. Dans une session interactive,
`vigil --show-completion` affiche le script et `vigil --install-completion`
l’installe pour le shell détecté. Les réglages de shell antérieurs sont
laissés à l’opérateur. Pour le retour arrière, réinstaller le paquet de
la révision précédente et restaurer les liens ou raccourcis de cette
révision. Les données n’ont pas à être restaurées pour ce renommage.

## Occurrences conservées

- `scripts/lib/vigil-launchers.sh` reconnaît et retire les anciens
  lanceurs `vigil2` et `vigil2-gui` du site.
- `tests/test_cli_launchers.py` recrée ces noms pour vérifier la migration
  et la protection des lanceurs tiers.
- `vigil/desktop.py` conserve la clé QSettings `Vigil2` pour relire les
  préférences historiques.
- Ce document conserve les noms précédents pour décrire la transition.

## Vérification

Deux wheels construits hors ligne, l’un depuis `d52c902` et l’autre depuis
le code modifié, ont été installés dans des venv temporaires. Les cas
d’installation neuve et de remplacement dans le même venv ont confirmé
les deux nouveaux points d’entrée et l’absence des anciens scripts.
L’aide, la version, la liste JSON des modules et la génération et
l’installation de la complétion Bash ont été vérifiées. La recette
utilise un HOME temporaire pour la complétion.

La suite `QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests`
passe avec 100 tests. Les tests de migration de liens et de conflits
utilisent un faux poste et un substitut de sudo. La recette système
sur Parrot reste à faire.
