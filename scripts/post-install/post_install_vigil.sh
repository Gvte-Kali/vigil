#!/usr/bin/bash
set -euo pipefail

script_directory=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
. "$script_directory/../lib/vigil-terminal.sh"
. "$script_directory/../lib/vigil-launchers.sh"
requirements="$script_directory/requirements.txt"
mapfile -t packages < <(awk 'NF && $1 !~ /^#/ { print $1 }' "$requirements")
if [ "${#packages[@]}" -eq 0 ]; then
    echo "Liste APT absente ou vide : $requirements" >&2
    exit 1
fi
skip_update=0
case "${1:-}" in
    --dry-run)
        printf 'APT :'
        printf ' %s' "${packages[@]}"
        printf '\nLe post-install prépare /opt/vigil/.venv, les zones, les lanceurs, udev et AppArmor si présent.\n'
        exit 0 ;;
    --skip-apt-update) skip_update=1 ;;
    '') ;;
    *) echo "Usage: $0 [--dry-run|--skip-apt-update]" >&2; exit 2 ;;
esac
if [ "$EUID" -eq 0 ]; then
    echo "Démarrez le post-install depuis la session de l'opérateur, avec sudo interactif."
    exit 1
fi
if [ "$script_directory" != /opt/vigil/scripts/post-install ]; then
    echo "Installez le dépôt dans /opt/vigil avant le post-install." >&2
    exit 1
fi
case "$(python3 -c 'import sys; print(int(sys.version_info >= (3, 11)))')" in
    1) ;;
    *) echo "Python 3.11 minimum est requis." >&2; exit 1 ;;
esac
vigil_launchers_preflight /opt/vigil /usr/local/bin /usr/bin /usr/share/applications/vigil.desktop
sudo -v
vigil_maintenance_start install 7 'Vigil · Installation'
trap 'vigil_maintenance_exit "$?"' EXIT
vigil_maintenance_step 'Contrôles système / System checks'
if sudo test -e /etc/sudoers.d/vigil; then
    echo "Règle sudoers Vigil existante : faites-la examiner et retirer par l'administrateur."
    echo "Voir docs/installation/README.md#reprendre-le-post-install."
    exit 1
fi
check_vigil_zones_unmounted() {
    local targets
    if ! targets=$(findmnt -rn -o TARGET); then
        echo "Impossible de vérifier les montages avant maintenance." >&2
        return 1
    fi
    if awk '$0 ~ "^/(investigation|stockage)(/|$)" { found=1 } END { exit !found }' <<< "$targets"; then
        echo "Démontez les supports des zones Vigil avant la maintenance." >&2
        return 1
    fi
}
check_vigil_zones_unmounted

if [ ! -w /opt/vigil ] || [ ! -w /opt/vigil/data ] || [ ! -w /opt/vigil/logs ] || [ ! -w /opt/vigil/rapports ]; then
    echo "Faites préparer les répertoires de données par l'administrateur."
    echo "Voir docs/development/phase-01-transition.md."
    exit 1
fi

# Keep a record of packages newly installed during the APT transaction.
manifest=/opt/vigil/data/apt-installed-by-vigil.txt
apt_snapshot() {
    dpkg-query -W -f='${db:Status-Abbrev} ${binary:Package}\n' |
        awk '$1 == "ii" { print $2 }' | LC_ALL=C sort -u
}
apt_work=$(mktemp -d)
trap 'status=$?; rm -rf -- "$apt_work"; vigil_maintenance_exit "$status"' EXIT
vigil_maintenance_step 'Dépôts et dépendances / Repositories and dependencies'
if (( ! skip_update )); then vigil_maintenance_run sudo apt-get update; fi
missing=()
for pkg in "${packages[@]}"; do
    if [[ $(dpkg-query -W -f='${db:Status-Abbrev}' "$pkg" 2>/dev/null || :) != ii* ]]; then missing+=("$pkg"); fi
done
if ((${#missing[@]})); then vigil_maintenance_run sudo apt-get -s install -- "${missing[@]}"; fi
apt_snapshot > "$apt_work/before"
apt_status=0
if ((${#missing[@]})); then vigil_maintenance_run sudo apt-get install -y -- "${missing[@]}" || apt_status=$?; fi
apt_snapshot > "$apt_work/after"
LC_ALL=C comm -13 "$apt_work/before" "$apt_work/after" > "$apt_work/new"
if [ -f "$manifest" ]; then
    cat "$manifest" >> "$apt_work/new"
fi
LC_ALL=C sort -u "$apt_work/new" > "$apt_work/manifest"
install -m 0600 "$apt_work/manifest" "$manifest"
[ "$apt_status" -eq 0 ] || exit "$apt_status"

# --- 1. Verifier et creer les repertoires necessaires ---
vigil_maintenance_step 'Répertoires et zones / Directories and zones'
if [ -L /investigation ] || { [ -e /investigation ] && [ ! -d /investigation ]; }; then
    echo "/investigation doit être un vrai répertoire." >&2
    exit 1
fi
if [ -d /investigation ]; then
    investigation_entries=$(sudo find /investigation -mindepth 1 -maxdepth 1 -print -quit)
    if [ -n "$investigation_entries" ]; then
        echo "/investigation doit être vide avant de corriger ses permissions." >&2
        exit 1
    fi
fi
check_vigil_zones_unmounted
sudo install -d -o root -g root -m 0755 /investigation
vigil_maintenance_run sh /opt/vigil/scripts/post-install/prepare-storage.sh
sudo mkdir -p /opt/vigil/{data,scripts,logs,rapports}


# --- 6. Initialiser les logs et données ---
mkdir -p /opt/vigil/data/{config/logo,projects,users,scans,usb}
mkdir -p /opt/vigil/logs
mkdir -p /opt/vigil/rapports
touch /opt/vigil/data/active_user
touch /opt/vigil/data/active_project
touch /opt/vigil/data/usb/whitelist.txt /opt/vigil/data/usb/blacklist.txt

# --- 6.1. Installer Qt dans /opt/vigil ---
vigil_maintenance_step 'Environnement Python et Vigil / Python environment and Vigil'
vigil_install_cli /opt/vigil /usr/local/bin /usr/bin /usr/share/applications/vigil.desktop >>"$VIGIL_LOG" 2>&1
. "$script_directory/../lib/vigil-freshclam.sh"
vigil_maintenance_step 'ClamAV et AppArmor'
vigil_prepare_freshclam /opt/vigil/data/state/clamav >>"$VIGIL_LOG" 2>&1

# --- 8. Créer le raccourci bureau (item 6 du checklist) ---
vigil_maintenance_step 'Raccourcis / Shortcuts'
# Installer l'icône SVG de l'application dans le chemin système des icônes.
# Le nom 'vigil' est référencé par Icon= dans le fichier .desktop ; KDE/Qt
# résolvent le nom vers /usr/share/icons/hicolor/scalable/apps/vigil.svg.
if [ -f /opt/vigil/data/icons/vigil.svg ]; then
    sudo mkdir -p /usr/share/icons/hicolor/scalable/apps
    sudo install -m 0644 /opt/vigil/data/icons/vigil.svg /usr/share/icons/hicolor/scalable/apps/vigil.svg
    sudo gtk-update-icon-cache -f /usr/share/icons/hicolor 2>/dev/null || true
    # Forcer le cache d'icônes GTK au cas ou la commande est absente (KDE).
    sudo touch /usr/share/icons/hicolor
    VIGIL_ICON="vigil"
else
    echo "⚠️  /opt/vigil/data/icons/vigil.svg introuvable — icône générique utilisée."
    VIGIL_ICON="utilities-terminal"
fi
sudo tee /usr/share/applications/vigil.desktop >/dev/null <<DESKTOP_EOF
[Desktop Entry]
Name=Vigil
Comment=Outil d'analyse forensique pour périphériques USB
Exec=/usr/local/bin/vigil-gui
Icon=$VIGIL_ICON
Terminal=false
Type=Application
Categories=Utility;System;
Keywords=forensique;USB;analyse;investigation;
DESKTOP_EOF
sudo update-desktop-database 2>/dev/null || true
# Rafraîchir le menu KDE : sans kbuildsycoca, la nouvelle entrée (et son icône)
# n'apparaît dans le lanceur qu'après la prochaine reconnexion.
if command -v kbuildsycoca6 >/dev/null 2>&1; then
    kbuildsycoca6 --noincremental 2>/dev/null || true
elif command -v kbuildsycoca5 >/dev/null 2>&1; then
    kbuildsycoca5 --noincremental 2>/dev/null || true
fi


# Install the hotplug rule without replaying events for devices already connected.
vigil_maintenance_step 'Protection USB et vérification / USB protection and checks'
vigil_maintenance_run sh /opt/vigil/scripts/post-install/install-hotplug.sh
vigil_maintenance_run /opt/vigil/.venv/bin/vigil --version
vigil_maintenance_finish

echo "Installation terminée. Pour initialiser les signatures, ouvrez Vigil puis Actions rapides > Mettre à jour l’antivirus."
echo "Inventaire des paquets nouvellement installés : $manifest"
