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
