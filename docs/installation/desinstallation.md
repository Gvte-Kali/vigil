---
layout: default
parent: Installation
title: Remise à zéro
---

# Remettre à zéro un poste Parrot ou Debian

Fermer la GUI, la TUI et les terminaux d’opérations. Démonter les volumes
depuis Vigil. Débrancher les supports de recette lorsque Vigil a confirmé la
restitution. Ces commandes sont à exécuter dans Bash depuis le compte opérateur.
Elles gardent une sauvegarde du site, des affaires, des preuves, des signatures,
des journaux et du venv hors du chemin actif. Si des affaires sont référencées
hors de /opt/vigil, sauvegarder aussi ces emplacements avant la recette.

## Retirer le site et les composants installés

Exécuter ce bloc depuis le compte opérateur. Tout échec arrête le bloc.

```bash
(
  set -euo pipefail
  cd "$HOME"
  sudo -v
  mounts=$(findmnt -rn -o TARGET)
  if grep -Eq '^/(investigation|stockage|opt/vigil)(/|$)' <<< "$mounts"; then
    echo 'Un montage occupe encore une zone Vigil ou le site.' >&2
    exit 1
  fi
  backup=$(mktemp -d "$HOME/vigil-sauvegarde.XXXXXX")
  printf 'Sauvegarde %s\n' "$backup"
  . /opt/vigil/scripts/lib/vigil-launchers.sh

  if sudo test -x /usr/local/sbin/vigil-hotplug; then
    sudo /usr/local/sbin/vigil-hotplug recover | python3 -c '
import json, sys
r = json.load(sys.stdin)
print(json.dumps(r, indent=2))
sys.exit(not (r["status"] == "complete" and
              all(d["state"] in {"restored", "absent"} for d in r["devices"])))
'
  fi

  for directory in /usr/local/bin /usr/bin "$HOME/.local/bin"; do
    for name in vigil vigil-gui vigil-tui vigil2 vigil2-gui; do
      file="$directory/$name"
      if vigil_owned_launcher "$file" /opt/vigil; then
        if [[ $directory == "$HOME/.local/bin" ]]; then
          rm -- "$file"
        else
          sudo rm -- "$file"
        fi
      fi
    done
  done
  desktop=/usr/share/applications/vigil.desktop
  if vigil_managed_desktop "$desktop" /opt/vigil /usr/local/bin; then
    sudo rm -- "$desktop"
  fi
  sudo rm -f -- /etc/udev/rules.d/99-vigil-hotplug.rules
  sudo udevadm control --reload-rules
  sudo rm -f -- /usr/local/sbin/vigil-hotplug
  if sudo test -d /run/vigil-hotplug; then
    sudo mv -T -- /run/vigil-hotplug "$backup/hotplug-runtime"
  fi
  if sudo cmp -s /usr/local/sbin/vigil-mount /opt/vigil/scripts/privileged/vigil-mount; then
    sudo rm -- /usr/local/sbin/vigil-mount
    if sudo test -d /run/vigil-mount; then
      sudo mv -T -- /run/vigil-mount "$backup/mount-runtime"
    fi
  fi
  icon=/usr/share/icons/hicolor/scalable/apps/vigil.svg
  if sudo cmp -s "$icon" /opt/vigil/data/icons/vigil.svg; then
    sudo rm -- "$icon"
  fi
  profile=/etc/apparmor.d/usr.bin.freshclam
  local_profile=/etc/apparmor.d/local/usr.bin.freshclam
  if sudo test -f "$local_profile"; then
    sudo cp -a -- "$local_profile" "$backup/freshclam-local"
    sudo sed -i '\|^owner /opt/vigil/data/state/clamav/ rw,$|d;\|^owner /opt/vigil/data/state/clamav/\*\* rwk,$|d' "$local_profile"
    if [[ -f $profile && $(cat /sys/module/apparmor/parameters/enabled 2>/dev/null || :) == Y ]]; then
      sudo apparmor_parser -r "$profile"
    fi
  fi
  # rmdir préserve tout répertoire non vide.
  for zone in /investigation /stockage; do
    if [[ -d $zone && ! -L $zone ]]; then sudo rmdir -- "$zone"; fi
  done
  sudo mv -T -- /opt/vigil "$backup/site"
)
hash -r
```

Pour une installation historique, restaurer la configuration d’UDisks2
d’avant Vigil si elle est sauvegardée. Vérifier `systemctl is-enabled udisks2`
et `sudo cat /etc/udisks2/udisks2.conf`. Si tu confirmes que le masque
provenait de Vigil, `sudo systemctl unmask udisks2.service` le retire.
Restaurer le contenu d’origine du fichier ou, s’il était absent à l’origine,
supprimer uniquement le fichier généré contenant `[udisks2]` et
`auto_mount=false`. Rejouer ensuite l’état initial du service plutôt que
l’activer systématiquement. Retirer de Dolphin les favoris hérités créés par
Vigil si présents. Si RDP avait été activé uniquement pour Vigil, retirer ses
réglages conformément à l’état initial du poste. Faire examiner et retirer
une éventuelle règle sudoers héritée avec `visudo` avant la réinstallation.

## Purger les paquets APT introduits pour Vigil

Pour un site installé avec le post-install actuel, utiliser son inventaire,
puis revoir la simulation. Remplacer le chemin par celui affiché à l’étape
précédente. L’inventaire contient les ajouts de la transaction, y compris leurs
dépendances. Retirer de la liste tout paquet désormais utile à une autre
application.

```bash
backup="$HOME/vigil-sauvegarde.REMPLACER"
cp -- "$backup/site/data/apt-installed-by-vigil.txt" "$backup/apt-a-purger.txt"
"${EDITOR:-nano}" "$backup/apt-a-purger.txt"
mapfile -t vigil_packages < <(awk '/^[a-z0-9][a-z0-9+.-]*(:[a-z0-9-]+)?$/ {print}' "$backup/apt-a-purger.txt")
if (("${#vigil_packages[@]}")); then
  sudo apt-get -s purge -- "${vigil_packages[@]}"
fi
```

S’il n’existe aucun inventaire, retrouver la transaction d’installation
dans les journaux historiques et créer `$backup/apt-a-purger.txt` avec les
noms issus de son champ `Install:`, un par ligne. Les paquets du champ
`Upgrade:` étaient déjà installés. Si les historiques sont incomplets,
laisser les paquets d’origine incertaine en place ou utiliser une VM vierge.

```bash
sudo zcat -f /var/log/apt/history.log* | less
```

Après lecture de la simulation, si la liste ne contient que des paquets
attribués à Vigil et si APT ne prévoit aucune suppression hors périmètre,
exécuter la purge. Conserver `git`, `sudo` et le Python système nécessaires
au démarrage de l’installateur. Une simulation d’autoremove permet de voir
les autres paquets orphelins, qui peuvent provenir d’autres logiciels.

```bash
if (("${#vigil_packages[@]}")); then
  sudo apt-get purge -- "${vigil_packages[@]}"
fi
sudo apt-get -s autoremove --purge
```

`type -a vigil vigil-gui vigil-tui` permet de repérer une installation
indépendante, par exemple pipx, un venv de développement ou un autre site.
La retirer depuis son gestionnaire uniquement si elle fait partie de la
recette. Pour repartir avec un profil neuf, ouvrir la nouvelle installation
sans les variables `VIGIL_STATE_DIR` ou `VIGIL_DATA_DIR` d’une autre instance.
La [procédure d’installation](README.md#installer-et-lancer) recrée le site.
Effectuer la recette avant de restaurer les données. Une fois la migration
validée, gérer la suppression de la sauvegarde selon la politique de conservation
du poste.
