# Gestion des périphériques dans Vigil Core

Le Device Manager utilise l’inventaire Linux et les montages du noyau. Les commandes de montage s’appuient sur le menu d’« Affaire en cours », également utilisé par le stockage. Les opérations Qt de montage, démontage, antivirus et analyse utilisent le même verrou que la CLI. Le RAW et le clonage prennent ce verrou dans leur espace de montage privé. Les analyses reçoivent un instantané des montages RO vérifiés et le recensement revérifie leur identité.

## Commandes

- `vigil devices list` affiche l’inventaire bloc en JSON.
- `vigil devices triage` utilise le menu. Ajouter `--device /dev/sdb1` pour valider directement un périphérique.
- `vigil devices mount` monte dans `/investigation` par défaut. Avec `--device /dev/sdb1`, la sélection est directe et sudo doit déjà être autorisé.
- `vigil devices mount --zone stockage --device /dev/sdb1 --confirm-write` monte un support de travail en RW après validation.
- `vigil devices unmount --target /investigation/sdb1` démonte ce point précis. Sans cible, le terminal propose les montages démontables. Utiliser `--zone stockage` pour le stockage.
- `vigil devices status` affiche les montages et les protections constatées. `vigil devices verify` signale un montage ambigu ou une protection non vérifiable. `--target` limite la vérification à un point.

Les diagnostics des outils de montage sont envoyés sur stderr en mode direct. stdout contient le résultat JSON. En mode interactif, les outils conservent le terminal et les messages de confirmation.

## Protections et migration

Le verrou du Core est partagé entre les processus natifs, sans daemon. Les analyses vérifiées peuvent coexister. Une opération de montage, démontage, acquisition ou restauration est exclusive. Un montage existant doit être démonté explicitement. Le démontage utilise les contrôles du noyau et refuse le démontage forcé. Les scripts n’enlèvent plus le RO d’une source après démontage sur le seul constat que son point de montage a disparu.

L’intégration du verrou à la restauration automatique nécessite de mettre à jour le helper installé par `scripts/post-install/install-hotplug.sh` avec l’administrateur. Le helper continue à n’altérer que les périphériques qu’il a enregistrés et dont il a revérifié l’identité.

La migration couvre les parcours actifs de Vigil 2.0. Le helper expérimental ext4, les anciens lanceurs sous `scripts/Vigil-CLI/`, le script historique de mise à jour ClamAV par USB et les parcours Tk d’imagerie E01/AFF et de clonage conservent des implémentations spécifiques. Les scripts historiques d’imagerie et de clonage participent déjà au verrou commun. Leur remplacement exige une recette dédiée de parité. Le recensement bloc exige un périphérique identifié et ne s’applique pas aux montages MTP.

## Contrat de lancement GUI et TUI

La recette se fait d’abord depuis la GUI et les commandes Core. Le lanceur
d’opérations suivies reçoit `--interface=gui` ou `--interface=tui`. En GUI,
il exécute la commande dans un terminal externe avec la progression
classique. En TUI, il transmet le mode embarqué aux scripts. Les opérations
lancées via sudo, comme l’acquisition RAW, reçoivent aussi l’argument
`--interface` explicitement. Les formats structurés de progression sont
déjà utilisés par le triage USB, l’acquisition RAW et le scan ClamAV.

Le montage RO de l’investigation et le montage RW du stockage partagent
le triage, l’inventaire bloc, le verrou, la validation d’identité et la
vérification du montage. Les scripts de montage conservent les options
propres à leur zone. Ils échangent l’identité sélectionnée avec le Core
via `VIGIL_DEVICE_IDENTITY`. Le lancement d’une analyse sur une zone
d’investigation déjà montée transmet les ressources RO vérifiées via
`VIGIL_DEVICE_CONTEXT`. Le garde du recensement recoupe ces ressources
avec les montages du noyau quand le contexte est fourni. Le RAW partage
le menu et le verrou et ouvre la source bloc directement.
