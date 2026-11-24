# Transition des privilèges Vigil

Sur un poste existant, l'administrateur examine `/etc/sudoers.d/vigil`
et les éventuelles copies de la règle Vigil, conserve une sauvegarde
hors des répertoires inclus par sudoers, retire la règle générique,
puis valide la configuration complète avec `visudo -c`. Vérifier
aussi les permissions effectives d'un compte opérateur. Le post-install
s'arrête si le fichier historique est toujours présent.

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
vide, root-owned et non modifiable par l’opérateur, et un fichier régulier
`/etc/vigil/approved-partition` root-owned, non modifiable par l’opérateur,
qui contient uniquement le nom de partition confirmé sous `/dev/disk/by-id`
(sans le chemin). Le répertoire de configuration et ses parents doivent
être sous contrôle administrateur.

Si le poste délègue ces opérations à un groupe local `vigil-operators`,
l’administrateur peut valider une règle limitée avec `visudo`, puis contrôler
les autorisations effectives. Les seules commandes déléguées sont les deux
invocations ci-dessous, avec authentification.

```sudoers
%vigil-operators ALL=(root) PASSWD: /usr/local/sbin/vigil-mount mount, /usr/local/sbin/vigil-mount unmount
```

Depuis Qt, l’opérateur confirme une affaire, choisit son identité et confirme
l’action. Sudo s’exécute dans le terminal intégré. Les événements Qt restent
rattachés à l’affaire sélectionnée au lancement ; le helper consigne son
résultat et l’UID appelant dans syslog. L’administrateur peut aussi lancer le
helper depuis sa session d’administration.

Le helper exige que le bloc et son parent soient déjà en lecture seule.
Il monte uniquement ext4 en `ro,noload,nosuid,nodev,noexec` sous
`/investigation`. Le démontage vérifie le reçu du montage et refuse un
montage étranger ou des sous-montages. Il ne lève aucun verrouillage RO.
En cas de divergence ou de reçu orphelin, l’administrateur doit réconcilier
l’état avant de réessayer. L’ouverture d’images et les autres formats restent
hors de ce lot.

Recette VM : bon et mauvais by-id, support RW, parent RW, cible occupée,
montage étranger, sous-montage, succès sur ext4 synthétique, vérification
des flags, des empreintes avant/après et du journal, puis démontage.
Rollback : retirer la délégation et le helper après réconciliation
des montages, conserver les journaux et les preuves.
