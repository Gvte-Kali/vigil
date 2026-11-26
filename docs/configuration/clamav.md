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

Vigil lance FreshClam et ClamScan avec la même base de signatures du profil.
Au premier démarrage, utiliser **Actions rapides → Mettre à jour l’antivirus**.
Vigil signale une base absente ou illisible et bloque le scan jusqu’à la
disponibilité des signatures. La sortie de `clamscan --version` sans
`--database` décrit le contexte système.

Si FreshClam signale `Can't open/parse the config file`, vérifier que
la configuration a été créée par une tentative de mise à jour et rechercher
les refus AppArmor dans le journal du noyau.

```bash
sudo journalctl -k -b --no-pager | grep -Ei 'apparmor.*DENIED.*freshclam' | tail -15
```

Sur la cible installée sous `/opt/vigil`, le post-install confine les
signatures à `/opt/vigil/data/state/clamav` et enregistre une exception
AppArmor pour ce seul répertoire dans le fichier local du profil
FreshClam, en conservant les règles existantes.

Sur une installation existante sous `/opt/vigil`, lancer depuis le compte
opérateur `bash scripts/post-install/update-cli.sh`. Ce script remet en place
les règles limitées à `/opt/vigil/data/state/clamav` et recharge le profil
FreshClam si AppArmor est actif. La commande suivante vérifie l’invocation. Relancer ensuite la mise à jour
depuis Vigil pour confirmer l’accès à la configuration et à la base.

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

Recharger le profil puis vérifier l’invocation sans sudo. Confirmer ensuite
l’accès effectif avec une mise à jour depuis Vigil.

```bash
sudo apparmor_parser -r /etc/apparmor.d/usr.bin.freshclam
cfg="$HOME/.local/state/vigil/clamav/vigil-freshclam.conf"
freshclam --config-file="$cfg" --version
```

## Poste connecté

Choisir la mise à jour des signatures en ligne. Vérifier le chemin affiché,
la version du moteur et la version de la base daily. Le profil de signatures
du service FreshClam de la distribution reste distinct.

## Poste isolé

1. Préparer les bases signées `main.cvd` et `daily.cvd` sur un poste connecté. Ajouter `bytecode.cvd` si disponible.
2. Choisir la mise à jour antivirus par USB et suivre le triage.
3. Vérifier les chemins affichés, puis confirmer l’import des signatures vérifiées.
4. Contrôler le récapitulatif des révisions installées et le démontage du support.

La mise à jour des signatures est distincte du [scan antivirus](../actions/antivirus.md).
