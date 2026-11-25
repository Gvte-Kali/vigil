# Supervision, restitution et consultation externe

## Diagnostic et architecture

Au commit `628aa0f`, l’entrée `vigil-gui` du paquet utilisait déjà un
superviseur indépendant. En revanche, `python -m vigil.desktop` lançait
Qt directement. Une installation avec un lanceur Python ancien
`vigil.desktop:main` contournait également le superviseur. Dans le parcours
supervisé, `external_terminal.launch_terminal()` choisissait le premier
exécutable du PATH et retournait dès le fork, sans détecter un échec
immédiat. Les journaux disponibles ne permettent pas d’attribuer l’absence
de terminal sur Parrot à l’une de ces causes en particulier.

Le lanceur supervise Qt, capture l’état initial et écrit un état de session
privé. Le processus gardien reçoit l’autorisation hotplug et conserve sa
durée de vie jusqu’à la fin des opérations externes attribuées à cette
session. Le suivi vérifie le PID et l’heure de démarrage du lanceur
d’opération et de son enfant immédiat. Vigil n’arrête pas ces opérations à
la sortie de Qt. Le terminal de bilan peut afficher l’attente puis lire
le rapport final. Sa fermeture ne stoppe pas le gardien. Le superviseur
teste le terminal préféré puis les candidats suivants si l’exécution
échoue immédiatement. Un terminal peut déléguer à un serveur existant.
Après une délégation réussie, Vigil ne peut pas certifier que la fenêtre
a été affichée.

## État et mutations

- L’instantané contient les montages et leurs options, les modes bloc et
  les identités disponibles, l’état observable d’UDisks et les
  empreintes ou destinations des fichiers de politique concernés.
- L’état d’exécution contient l’identifiant de session, les identités de
  processus, le lien de l’instantané, le contexte opérateur/affaire
  disponible et le rapport final. Il persiste dans `data/state/sessions`.
- Avant un changement de mode, le broker écrit une intention avec les
  identités des sessions, l’identité bloc, le mode initial et demandé,
  la propriété UDisks vue et une date. Il enregistre ensuite le mode
  observé et le résultat. Le registre root sous `/run/vigil-hotplug` est
  valide pour le démarrage Linux courant.
- La restitution sous verrou n’agit que sur ce registre. Elle vérifie
  l’identité et le mode, attend udev hors du verrou et constate que
  l’exclusion appartenant à Vigil a disparu. Les entrées en échec
  restent disponibles pour la tentative suivante. Aucun réglage
  administrateur, montage existant ou état de service n’est réappliqué
  depuis l’instantané.

## Matrice de sortie

| Situation | Prise en charge | Limite |
|---|---|---|
| Fermeture Qt, bouton ou gestionnaire de fenêtres | Bilan après sortie et contrôles habituels | Montage ou opération active bloque la fermeture normale |
| Erreur de lancement ou exception fatale | Code de sortie et bilan si le superviseur reste disponible | Le détail de Qt peut être visible uniquement sur stderr |
| SIGTERM, SIGINT, SIGHUP au superviseur | Signal transmis à Qt, gardien laissé en place | Dépend de la réponse de Qt |
| SIGABRT, SIGSEGV ou SIGKILL de Qt seul | Code du signal, bilan indépendant et attentes suivies | Un descendant non suivi ne peut être identifié avec certitude |
| Terminal fermé ou émulateur indisponible | Le nettoyage continue et le rapport reste sur disque | Un terminal ne peut apparaître hors session graphique |
| Superviseur arrêté seul | EOF détecté par le gardien, état persistant à examiner au prochain lancement | Le rapport final peut manquer |
| Fermeture de session, redémarrage ou coupure | État de session et instantané consultables au prochain lancement | Aucun terminal garanti et aucun rejeu d’un ancien nom de disque après redémarrage |
| Autre session Vigil active | Protection conservée jusqu’à sa fin | Pas de restitution forcée |
| Source montée, occupée ou introuvable | Contrôle et diagnostic, vérification d’identité et ouverture bloc exclusive | Pas de démontage ni d’interruption automatique |

Au prochain lancement, un état antérieur non résolu produit un diagnostic
avant la réactivation hotplug. Le terminal permet d’examiner le rapport
et de demander une nouvelle tentative via **R** avec sudo interactif.
Après une restitution confirmée, relancer Vigil pour réactiver la
protection sur la nouvelle session. Les rapports en JSON sont conservés
dans `data/state/shutdown-reports`. Le bilan terminal reste ouvert sur
Entrée et son affichage respecte `NO_COLOR`.

## Explorateur

Un clic programme un aperçu borné à 4 Kio. Un numéro de génération
empêche un résultat ancien de remplacer l’aperçu courant. Un double-clic
sur un répertoire développe l’arbre interne. Un double-clic sur un
document autorisé propose son ouverture dans l’application associée
par l’OS, depuis une copie privée en mode 0400. Les fichiers ouverts
proviennent d’un montage vérifié RO, d’une copie enregistrée ou des
résultats locaux. Les sources importées restent des références.

Les types exécutables et inconnus sont refusés par la politique de
consultation. Les documents susceptibles de contenir du contenu actif
demandent confirmation. La copie de consultation, limitée à 256 Mio,
n’isole pas l’application. Elle reste sous `data/state/viewing-copies`
pour laisser le lecteur accéder à son fichier. Les ouvertures de dossier
signalent le risque des miniatures. FileManager1 est facultatif. La
demande enregistrée dans le journal reflète l’acceptation par le
bureau, sans attester la lecture du fichier.

## Recette et retour arrière

Les scénarios avec périphériques ou un émulateur natif doivent être
vérifiés dans une VM. Aucun test automatisé ne lance une application
sur une preuve ni ne change le mode d’un périphérique réel. Les
procédures sont dans `tests.txt`. Pour revenir en arrière, vérifier
le bilan des sessions en cours, puis réinstaller le broker et le paquet
de la révision précédente. Les rapports exportés peuvent être conservés.

## Fichiers concernés

- Session et lancement. `vigil/session.py`, `vigil/shutdown_state.py`,
  `vigil/external_terminal.py`, `vigil/external_operation.py` et
  `scripts/privileged/vigil-hotplug`.
- Interface et consultation. `vigil/desktop.py`, `vigil/evidence_panel.py`,
  `vigil/desktop_integration.py`, `vigil/inspection.py`,
  `data/icons/folder-open.svg`, `data/icons/external-link.svg` et `pyproject.toml`.
- Vérification. `tests/test_session.py`, `tests/test_desktop_integration.py`,
  `tests/test_qt_workspace.py`, `tests.txt` et `todo.txt`.
