#!/bin/bash
set -euo pipefail

INSTALL_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if [[ "$INSTALL_DIR" != /opt/vigil/scripts/post-install ]]; then
    echo "Placez Vigil dans /opt/vigil avant de lancer ce script." >&2
    exit 1
fi
VIGIL_OPERATOR=${SUDO_USER:-$(id -un)}
if [[ "$VIGIL_OPERATOR" == root || ! "$VIGIL_OPERATOR" =~ ^[a-zA-Z_][a-zA-Z0-9_.-]*$ ]]; then
    echo "Lancez ce script depuis le compte opérateur de Vigil." >&2
    exit 1
fi
VIGIL_GROUP=$(id -gn "$VIGIL_OPERATOR")
VIGIL_HOME=$(getent passwd "$VIGIL_OPERATOR" | cut -d: -f6)

# ID et ID_LIKE évitent de choisir apt sur une distribution qui utilise dnf.
. /etc/os-release
case " ${ID:-} ${ID_LIKE:-} " in
    *" debian "*|*" ubuntu "*|*" kali "*|*" parrot "*) manager=apt ;;
    *" fedora "*|*" rhel "*|*" centos "*) manager=dnf ;;
    *" arch "*) manager=pacman ;;
    *)
        for manager in apt dnf pacman; do
            command -v "$manager" >/dev/null 2>&1 && break
        done ;;
esac
if ! command -v "$manager" >/dev/null; then
    echo "Gestionnaire de paquets introuvable : $manager" >&2
    exit 1
fi

case "$manager" in
    apt) sudo apt-get update; install_command=(apt-get install -y) ;;
    dnf) install_command=(dnf install -y) ;;
    pacman) install_command=(pacman -S --needed --noconfirm) ;;
esac
package_available() {
    case "$manager" in
        apt) apt-cache show --no-all-versions "$1" >/dev/null 2>&1 ;;
        dnf) rpm -q "$1" >/dev/null 2>&1 || dnf -q list --available "$1" >/dev/null 2>&1 ;;
        pacman) pacman -Q "$1" >/dev/null 2>&1 || pacman -Si "$1" >/dev/null 2>&1 ;;
    esac
}

declare -A selected=()
required=() optional=() missing=()
while read -r kind apt_pkg dnf_pkg pacman_pkg; do
    [[ -z "$kind" || "$kind" == \#* ]] && continue
    case "$manager" in
        apt) names=$apt_pkg ;;
        dnf) names=$dnf_pkg ;;
        pacman) names=$pacman_pkg ;;
    esac
    IFS='|' read -ra candidates <<< "$names"
    package=
    for candidate in "${candidates[@]}"; do
        if package_available "$candidate"; then
            package=$candidate
            break
        fi
    done
    if [[ -z "$package" ]]; then
        if [[ "$kind" == base ]]; then
            missing+=("$names")
        else
            echo "Dépendance facultative absente des dépôts actifs ($manager) : $names"
        fi
    elif [[ ! ${selected[$package]+x} ]]; then
        selected[$package]=1
        if [[ "$kind" == base ]]; then
            required+=("$package")
        else
            optional+=("$package")
        fi
    fi
done < "$INSTALL_DIR/requirements.txt"
if (( ${#missing[@]} )); then
    echo "Paquets requis absents des dépôts actifs ($manager) : ${missing[*]}" >&2
    exit 1
fi
sudo "${install_command[@]}" "${required[@]}"
if (( ${#optional[@]} )) && ! sudo "${install_command[@]}" "${optional[@]}"; then
    for package in "${optional[@]}"; do
        sudo "${install_command[@]}" "$package" ||
            echo "Installation facultative échouée : $package" >&2
    done
fi

# L'ancien installateur masquait UDisks. Un masque existant peut aussi relever
# d'une politique administrateur, donc le signaler sans modifier son choix.
if [[ $(systemctl is-enabled udisks2.service 2>/dev/null || true) == masked* ]]; then
    echo "UDisks est masqué. Voir la procédure de migration dans la documentation."
fi
sudo install -D -m 0755 -o root -g root "$INSTALL_DIR/vigil-usb-add" /usr/local/libexec/vigil-usb-add
sudo install -D -m 0644 -o root -g root "$INSTALL_DIR/99-vigil-usb.rules" /etc/udev/rules.d/99-vigil-usb.rules
printf 'f %s 0600 %s root -\n' /run/vigil-usb.lock "$VIGIL_OPERATOR" \
    /run/vigil-storage.lock "$VIGIL_OPERATOR" |
    sudo tee /etc/tmpfiles.d/vigil-usb.conf >/dev/null
sudo systemd-tmpfiles --create /etc/tmpfiles.d/vigil-usb.conf
if command -v restorecon >/dev/null; then
    sudo restorecon /usr/local/libexec/vigil-usb-add /etc/udev/rules.d/99-vigil-usb.rules /run/vigil-usb.lock /run/vigil-storage.lock
fi
sudo udevadm control --reload-rules

sudo install -d /usr/local/bin /usr/share/applications
for directory in /investigation /stockage /opt/vigil/data /opt/vigil/logs /opt/vigil/rapports; do
    sudo install -d -m 0755 -o "$VIGIL_OPERATOR" -g "$VIGIL_GROUP" "$directory"
done
# Une installation historique lancée avec sudo pouvait laisser ces données à root.
sudo chown -R "$VIGIL_OPERATOR:$VIGIL_GROUP" /opt/vigil/{data,logs,rapports}
sudo -u "$VIGIL_OPERATOR" mkdir -p /opt/vigil/data/{config/logo,projects,users,scans,usb}
sudo -u "$VIGIL_OPERATOR" touch /opt/vigil/data/{active_user,active_project,usb/whitelist.txt,usb/blacklist.txt}

if [[ "$manager" == apt && -t 0 ]]; then
    read -rp "Activer l'accès RDP via xrdp et UFW ? [o/N] " ENABLE_RDP || ENABLE_RDP=
    case "$ENABLE_RDP" in
        o|O|y|Y)
            sudo "${install_command[@]}" xrdp xorgxrdp ufw
            sudo systemctl enable --now xrdp
            sudo ufw allow 3389/tcp ;;
    esac
fi

# --- 6.1. Lien symbolique vigil -> vigil_main_gui.py ---
echo "Création du lien symbolique /usr/local/bin/vigil..."
sudo ln -sf /opt/vigil/gui/vigil_main_gui.py /usr/local/bin/vigil
sudo chmod +x /opt/vigil/gui/vigil_main_gui.py
echo "✅ Lien symbolique /usr/local/bin/vigil créé (pointe vers /opt/vigil/gui/vigil_main_gui.py)."

# --- 7. Configurer sudoers NOPASSWD pour Vigil ---
echo "Configuration de sudoers (sans mot de passe pour Vigil)..."
SUDOERS_FILE="/etc/sudoers.d/vigil"
tmp_sudoers=$(mktemp)
trap 'rm -f -- "$tmp_sudoers"' EXIT
cat > "$tmp_sudoers" << 'SUDOERS_EOF'
# Commandes privilégiées requises par Vigil pour le compte opérateur.
# Plusieurs acceptent des arguments libres : réserver ce compte à un administrateur.
Cmnd_Alias VIGIL_MOUNT = /bin/mount, /bin/umount, /sbin/blkid, /sbin/blockdev, /sbin/findmnt, /usr/bin/eject, /usr/bin/mount, /usr/bin/umount, /usr/sbin/blkid, /usr/sbin/blockdev, /usr/sbin/findmnt, /usr/bin/blockdev, /usr/bin/blkid, /usr/bin/findmnt
Cmnd_Alias VIGIL_FS = /bin/mkdir, /bin/rmdir, /bin/rm, /bin/chmod, /bin/chown, /usr/bin/install, /usr/bin/mkdir, /usr/bin/rmdir, /usr/bin/rm, /usr/bin/chmod, /usr/bin/chown
Cmnd_Alias VIGIL_CLAM = /usr/bin/clamscan, /usr/bin/freshclam, /usr/bin/clamconf
Cmnd_Alias VIGIL_SYSTEMCTL = /bin/systemctl stop clamav-freshclam, /bin/systemctl stop clamav-freshclam.service, /bin/systemctl stop freshclam.service, /bin/systemctl start clamav-freshclam, /bin/systemctl start clamav-freshclam.service, /bin/systemctl start freshclam.service, /usr/bin/systemctl stop clamav-freshclam, /usr/bin/systemctl stop clamav-freshclam.service, /usr/bin/systemctl stop freshclam.service, /usr/bin/systemctl start clamav-freshclam, /usr/bin/systemctl start clamav-freshclam.service, /usr/bin/systemctl start freshclam.service
Cmnd_Alias VIGIL_LOG = /usr/bin/tee
Cmnd_Alias VIGIL_UDEV = /usr/bin/udevadm, /bin/udevadm
Cmnd_Alias VIGIL_MTP = /usr/bin/jmtpfs, /usr/bin/ldmtool
Cmnd_Alias VIGIL_ALL = VIGIL_MOUNT, VIGIL_FS, VIGIL_CLAM, VIGIL_SYSTEMCTL, VIGIL_LOG, VIGIL_UDEV, VIGIL_MTP
SUDOERS_EOF
printf '%s ALL=(root) NOPASSWD: VIGIL_ALL\n' "$VIGIL_OPERATOR" >> "$tmp_sudoers"
sudo visudo -c -f "$tmp_sudoers"
sudo install -o root -g root -m 0440 "$tmp_sudoers" "$SUDOERS_FILE"

# --- 8. Créer le raccourci bureau (item 6 du checklist) ---
echo "Création du raccourci Vigil..."
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
Exec=/usr/local/bin/vigil
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
echo "✅ Raccourci créé : /usr/share/applications/vigil.desktop (icône : $VIGIL_ICON)"

if [[ "${XDG_CURRENT_DESKTOP:-}" == *KDE* || -f "$VIGIL_HOME/.local/share/user-places.xbel" ]]; then
# --- 9. Ajouter les emplacements Dolphin (item 4 du checklist) ---
# Dolphin (KDE) stocke les emplacements dans ~/.local/share/user-places.xbel
# (format XBEL). On ajoute /investigation, /stockage, /rapports de façon
# idempotente : on ne réécrit pas un emplacement déjà présent.
echo "Ajout des emplacements Dolphin..."
PLACES_FILE="$VIGIL_HOME/.local/share/user-places.xbel"
sudo -u "$VIGIL_OPERATOR" mkdir -p "$(dirname "$PLACES_FILE")"
# Créer le fichier s'il n'existe pas avec l'en-tête XBEL minimal
if [ ! -f "$PLACES_FILE" ]; then
    sudo -u "$VIGIL_OPERATOR" tee "$PLACES_FILE" >/dev/null <<'XBEL_EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE xbel>
<xbel xmlns:kde="http://www.kde.org/xbel-ns/1.0/" xmlns:mime="http://www.freedesktop.org/standards/shared-mime-info" xmlns:bookmark="http://www.freedesktop.org/standards/xesam/1.0#">
</xbel>
XBEL_EOF
fi

_add_dolphin_place() {
    local target="$1"
    local label="$2"
    # Idempotence : on saute si l'emplacement est déjà référencé (par son href)
    if grep -q "href=\"file://${target}\"" "$PLACES_FILE" 2>/dev/null; then
        return
    fi
    local tmpfile
    tmpfile=$(mktemp)
    awk -v target="$target" -v label="$label" '
        /<\/xbel>/ {
            print "  <bookmark href=\"file://" target "\">"
            print "    <title>" label "</title>"
            print "    <info>"
            print "      <metadata owner=\"http://kde.org\">"
            print "        <kde:icon name=\"folder\"/>"
            print "      </metadata>"
            print "    </info>"
            print "  </bookmark>"
        }
        { print }
    ' "$PLACES_FILE" > "$tmpfile" && sudo -u "$VIGIL_OPERATOR" tee "$PLACES_FILE" < "$tmpfile" >/dev/null
    rm -f "$tmpfile"
}
_add_dolphin_place "/investigation" "Investigation"
_add_dolphin_place "/stockage" "Stockage"
_add_dolphin_place "/rapports" "Rapports"
echo "✅ Emplacements ajoutés à Dolphin : /investigation /stockage /rapports"

fi

if command -v freshclam >/dev/null &&
    ! systemctl is-active --quiet clamav-freshclam.service &&
    ! systemctl is-active --quiet freshclam.service; then
    sudo freshclam || echo "Signatures ClamAV à mettre à jour depuis Vigil." >&2
fi

echo "Installation terminée. Lancez vigil depuis le compte $VIGIL_OPERATOR."
