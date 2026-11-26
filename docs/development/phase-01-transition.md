# Transition des privilèges Vigil

Sur un poste existant, l'administrateur examine `/etc/sudoers.d/vigil`
et les éventuelles copies de la règle Vigil, conserve une sauvegarde
hors des répertoires inclus par sudoers, retire la règle générique,
puis valide la configuration complète avec `visudo -c`. Vérifier
aussi les permissions effectives d'un compte opérateur. Le post-install
s'arrête si le fichier historique est toujours présent.

## Préparer uniquement la zone de stockage

Fermer Vigil et démonter les volumes sous `/stockage`. Depuis la
session de l’opérateur, lancer :

```sh
sh /opt/vigil/scripts/post-install/prepare-storage.sh
```

La commande prépare le répertoire `/stockage` en `root:root`, mode
`0755`. Elle refuse un montage direct ou imbriqué et les liens
symboliques. L’opération ne touche ni au contenu du répertoire ni à la règle sudoers.
Le contrôle de la règle historique s’applique au post-install complet.

Avant le post-install, l'administrateur prépare /opt/vigil et attribue
à l'opérateur les seuls dossiers de données, journaux, rapports et
travail nécessaires à son poste. Les zones /investigation et /stockage
doivent être démontées pour la maintenance. Démarrer le script depuis
la session de l'opérateur avec sudo interactif. Le script ne change plus
récursivement les propriétaires ni les modes des zones et ne purge plus
USBGuard. Vérifier les politiques locales d'automontage et d'autorisation
USB sur une image de test du poste.

Jusqu'à la recette du broker, les opérations qui exigent des privilèges
restent à effectuer manuellement par un administrateur depuis une
session d'administration. L'administrateur sélectionne et vérifie
l'identité du support et de ses parents, vérifie séparément bloc et
montage RO, valide la destination et enregistre son intervention dans
la custody. En cas d'incertitude, s'arrêter. Pour MTP, établir un parcours
de copie distinct. Une indication RO de montage ne prouve pas une
protection du protocole. Les parcours historiques qui reposaient sur
NOPASSWD peuvent échouer ou demander une authentification.

Validation de ce lot sur fixtures avec `bash -n`, tests unitaires et
comparaison des sources. La recette avec installation, permissions
effectives, montage et nettoyage reste à effectuer en VM dédiée
sur supports synthétiques. Pour revenir en arrière sur le code, utiliser
le revert du lot sur la branche dédiée. Conserver la politique
d'administration et les données du poste pendant ce retour.

## Délégation expérimentale du montage ext4

Le candidat `scripts/privileged/vigil-mount` est autonome. Le post-install
général ne le déploie pas. Recetter d’abord dans une VM sur un dispositif
synthétique ; ne pas activer ce parcours sur un poste de production avant
validation.

L’administrateur copie le fichier revu vers `/usr/local/sbin/vigil-mount`
sous propriétaire root, mode 0755. Il prépare un point `/investigation`
vide, root-owned et non modifiable par l’opérateur. Le helper détecte
les partitions USB via leurs liens by-id et l’ascendance sysfs.
Le fichier `/etc/vigil/approved-partition` des versions précédentes
n’est plus utilisé.

Si le poste délègue ces opérations à un groupe local `vigil-operators`,
l’administrateur peut valider une règle limitée avec `visudo`, puis contrôler
les autorisations effectives. Les seules commandes déléguées sont les deux
invocations ci-dessous, avec authentification.

```sudoers
%vigil-operators ALL=(root) PASSWD: /usr/local/sbin/vigil-mount mount, /usr/local/sbin/vigil-mount unmount
```

Depuis Qt, l’opérateur confirme une affaire, choisit son identité et confirme
l’action. Après sudo, le terminal intégré affiche une liste numérotée
et propose `r` pour actualiser. Sélectionner la partition identifiée,
puis saisir `OUI` pour demander le verrouillage bloc et le montage. Les événements Qt restent
rattachés à l’affaire sélectionnée au lancement ; le helper consigne son
résultat et l’UID appelant dans syslog. L’administrateur peut aussi lancer le
helper depuis sa session d’administration.

Le helper demande l’ouverture exclusive du disque parent avant de
positionner les blocs du disque et de la partition en lecture seule.
Il contrôle les deux verrous et revalide la source avant de monter.
Le verrou reste appliqué après démontage ou échec du montage.
Il monte uniquement ext4 en `ro,noload,nosuid,nodev,noexec` sous
`/investigation`. Le démontage vérifie le reçu du montage et refuse un
montage étranger ou des sous-montages. Il ne lève aucun verrouillage RO.
En cas de divergence ou de reçu orphelin, l’administrateur doit réconcilier
l’état avant de réessayer. L’ouverture d’images, les autres formats, MTP et le triage HID de Vigil 1.0
restent hors de ce lot.

Recette VM : détection et rafraîchissement, refus d’un disque interne,
annulation, support déjà utilisé, contrôle des verrous bloc, cible occupée,
montage étranger, sous-montage, succès sur ext4 synthétique, vérification
des flags, des empreintes avant/après et du journal, puis démontage.
Rollback : retirer la délégation et le helper après réconciliation
des montages, conserver les journaux et les preuves.


### Dev : reproduire depuis un terminal

Le parcours historique peut être reproduit dans une VM dédiée, après avoir
vérifié que seules les fixtures synthétiques sont visibles. Le script
historique pilote aussi le triage USB et certains chemins continuent après
un échec de verrouillage bloc. Ne pas utiliser ce parcours pour une preuve.

```bash
cd /opt/vigil
sudo -v && bash scripts/analyse/vigil_usb_mount.sh
```

Le helper Qt affiche séparément les erreurs d’ioctl bloc et du montage
ext4. En cas d’EINVAL au montage, comparer le système de fichiers avec
`lsblk -o NAME,PATH,TYPE,FSTYPE,RO,MOUNTPOINTS` et consulter le journal
noyau. Une erreur de montage peut laisser le verrouillage bloc appliqué.


### Parcours de développement Qt actuel

Les boutons de montage/démontage ouvrent provisoirement les scripts
historiques dans le terminal du bureau. Le lancement utilise sudo interactif
et transmet l’affaire et l’opérateur choisis sans écrire les sélections
globales de la 1.0. Les livrables et journaux produits par ces scripts
restent dans `legacy-custody/<id-affaire>` à côté de la base SQLite.
Le journal Qt enregistre la demande, et le terminal externe affiche le
résultat du script. Le helper expérimental reste disponible pour sa
recette séparée. Les limites du parcours historique s’appliquent.

## Bilan de fermeture de la session Qt

`vigil-gui` supervise le processus Qt le temps de la session. À la sortie
ordinaire, sur erreur de démarrage ou sur signal du processus Qt, il
présente le code de sortie, l’état des montages et le reçu hotplug dans
le terminal système. Appuyer sur Entrée pour fermer ce terminal. Le
rapport JSON est enregistré dans `data/state/shutdown-reports` pour
une installation dans `/opt/vigil`. Si l’émulateur ne peut pas être
lancé, le rapport est également imprimé dans le terminal appelant
lorsqu’il y en a un.

Le reçu indique quels modes bloc ont été vérifiés, quels supports ne
sont plus présents et quelles exclusions udev de Vigil ont été levées.
Il signale une autre session encore active. Le journal protégé de Vigil
conserve les changements dont la restitution n’a pas pu être confirmée.
La touche R propose de réessayer cette restitution ciblée, avec sudo
interactif, lorsque le bilan indique un échec ou un reçu indisponible
après un arrêt anormal. Elle ne démonte aucun volume et le broker refuse
la restitution si une autre session Vigil est active. Les réglages
administrateur d’UDisks et les modes des autres périphériques restent
sous la responsabilité de l’OS.

Après mise à jour, fermer toutes les sessions Vigil puis réinstaller
le lanceur Python et actualiser le broker et la règle udev existants.

```sh
cd /opt/vigil
bash scripts/post-install/update-cli.sh
sh scripts/post-install/install-hotplug.sh
```

Un arrêt brutal de l’ensemble de la machine ou du superviseur peut
empêcher l’affichage du terminal. Le watcher privilégié agit sur la
sortie du processus Qt tant qu’il reste en vie. Avant de revenir à une
révision antérieure, terminer la session et vérifier le bilan, puis
réinstaller le lanceur et le broker de cette révision.
