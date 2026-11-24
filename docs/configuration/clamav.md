---
layout: default
parent: Configuration
title: Mise à jour ClamAV
nav_order: 14
---

# Mise à jour ClamAV

Depuis **Mettre à jour l’antivirus ClamAV**, choisir le mode de mise à jour.
Les opérations s’exécutent dans Konsole.


## Mise à jour depuis Qt sur Debian ou Parrot

Vigil lance FreshClam avec une configuration et un répertoire de signatures
propres au profil utilisateur. Si FreshClam renvoie `Can't open/parse the
config file` pour la configuration Vigil alors que la configuration
système fonctionne, vérifier les refus AppArmor depuis un compte autorisé
à lire le journal noyau.

```bash
sudo journalctl -k -b --no-pager | grep -Ei 'apparmor.*DENIED.*freshclam' | tail -15
```

Le profil Debian `/etc/apparmor.d/usr.bin.freshclam` autorise la
configuration et les signatures système. Il ne contient pas par défaut
de règle pour le profil Vigil. Si un refus confirme ce diagnostic,
l’administrateur peut conserver les mises à jour via le service
`clamav-freshclam`. Pour contrôler le service et la version utilisée
par le scanner système, utiliser `systemctl status clamav-freshclam`
et `clamscan --version`. Vigil utilise les bases système en l’absence
de bases personnalisées dans son profil.

Pour permettre la mise à jour dans Qt, l’administrateur peut ajouter au
fichier local inclus par le profil FreshClam une règle limitée au
répertoire de signatures Vigil de l’opérateur, puis recharger le profil.
Conserver AppArmor actif et les permissions utilisateur existantes.
Tester d’abord la configuration avec `freshclam --config-file=CHEMIN --version`,
qui ne télécharge pas de signatures.

Les procédures En ligne et Par clé USB ci-dessous décrivent Vigil 1.0.

## Poste connecté

Lancer le mode **En ligne**. Le script `scripts/clamav/vigil_clamav_update.sh`
arrête temporairement `clamav-freshclam`, exécute `freshclam`, redémarre le service
et affiche les versions des bases installées.

## Poste isolé

1. Préparer les bases `.cvd` sur un poste connecté.
2. Choisir **Par clé USB** et suivre le triage USB.
3. Sélectionner le support contenant les bases.
4. Laisser le script monter le support en lecture seule, copier les bases dans le répertoire ClamAV et démonter le support.
5. Vérifier les versions affichées.

Script : `scripts/clamav/vigil_clamav_update_usb.sh`.

La mise à jour des signatures est distincte du [scan antivirus](../actions/antivirus.md).
