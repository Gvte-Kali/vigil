---
layout: default
parent: Configuration
title: Mise à jour ClamAV
nav_order: 14
---

# Mise à jour ClamAV

Depuis **Mettre à jour l’antivirus ClamAV**, choisir le mode de mise à jour.
Les opérations s’exécutent dans Konsole.


## Mise à jour depuis Qt et Textual sur Debian ou Parrot

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

Sur la cible installée sous `/opt/vigil`, le post-install confine les
signatures à `/opt/vigil/data/state/clamav` et enregistre une exception
AppArmor pour ce seul répertoire dans le fichier local du profil
FreshClam, en conservant les règles existantes.

Sur une installation existante sous `/opt/vigil`, lancer depuis le compte
opérateur `bash scripts/post-install/update-cli.sh`. Ce script remet en place
les règles limitées à `/opt/vigil/data/state/clamav` et recharge le profil
FreshClam si AppArmor est actif. Le test suivant lit la configuration sans
télécharger de signatures.

```bash
freshclam --config-file=/opt/vigil/data/state/clamav/vigil-freshclam.conf --version
```

Si le test échoue encore, vérifier les refus AppArmor dans le journal noyau
et les droits de passage et de lecture avec
`namei -l /opt/vigil/data/state/clamav/vigil-freshclam.conf`.

Pour un poste de développement hors de `/opt/vigil`, vérifier
l’inclusion du fichier local puis l’ouvrir avec `sudoedit`.

```bash
grep -n 'local/usr.bin.freshclam' /etc/apparmor.d/usr.bin.freshclam
sudoedit /etc/apparmor.d/local/usr.bin.freshclam
```

Si l’inclusion est présente, ajouter ces règles en remplaçant `clsi`
par l’opérateur concerné.

```text
owner /home/clsi/.local/state/vigil/clamav/ rw,
owner /home/clsi/.local/state/vigil/clamav/** rwk,
```

Recharger le profil puis tester sans sudo. L’option `--version` lit la
configuration sans télécharger de signatures.

```bash
sudo apparmor_parser -r /etc/apparmor.d/usr.bin.freshclam
cfg="$HOME/.local/state/vigil/clamav/vigil-freshclam.conf"
freshclam --config-file="$cfg" --version
```

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
