#!/bin/bash
set -euo pipefail

# --- 1. Verifier et creer les repertoires necessaires ---
echo "Création des répertoires..."
sudo mkdir -p /investigation /stockage /opt/vigil/{data,scripts,logs,rapports}
sudo chown -R "$USER:$USER" /investigation /stockage /opt/vigil
sudo chmod -R 755 /investigation /stockage /opt/vigil
echo "✅ Répertoires créés avec les droits pour $USER."

# --- 2. Installer les dependances depuis requirements.txt ---
# Les paquets y sont documentes (un commentaire par paquet).
# La liste ci-dessous reste synchronisee avec ce fichier : elle sert de
# secours si requirements.txt est introuvable.
REQUIREMENTS_FILE="/opt/vigil/scripts/post-install/requirements.txt"
FALLBACK_PKGS="util-linux coreutils jq eject cryptsetup clamav clamav-daemon clamav-freshclam xrdp xorgxrdp udisks2 ufw konsole kdialog zenity jmtpfs ntfs-3g exfat-fuse dc3dd ewf-tools afflib-tools sleuthkit autopsy yara guymager gnupg ldmtool exiftool ffmpeg p7zip-full zstd binwalk pv file gdisk cloud-guest-utils parted imagemagick feh python3 python3-tk python3-pil python3-pip python3-reportlab python3-cairosvg libcairo2 facedetect python3-opencv"
if [ -f "$REQUIREMENTS_FILE" ]; then
    echo "Installation des dépendances depuis $REQUIREMENTS_FILE..."
    sudo apt update
    # Filtrer les commentaires (#) et lignes vides avant de passer a apt
    PKGS=$(grep -v '^[[:space:]]*#' "$REQUIREMENTS_FILE" | grep -v '^[[:space:]]*$' | tr '\n' ' ')
    if [ -n "$PKGS" ]; then
        sudo apt install -y $PKGS
    fi
    echo "✅ Dépendances installées."
else
    echo "❌ Fichier $REQUIREMENTS_FILE introuvable. Installation des dépendances de base..."
    sudo apt update
    sudo apt install -y $FALLBACK_PKGS
fi

# --- 3. Configurer le service RDP (optionnel) ---
# L'accès RDP n'est pertinent que pour un usage à distance (serveur forensique
# accédé depuis un autre poste). Sur une station de travail dédiée ou un live USB,
# on n'en a pas besoin et on évite d'ouvrir un port inutile.
echo ""
echo "Souhaitez-vous activer l'accès RDP (xrdp) sur cette machine ?"
echo "  [o] Oui — accès distant via RDP (ouverture du port 3389/tcp)"
echo "  [n] Non  — station de travail locale, pas d'accès distant"
echo -ne "Votre choix (o/n) [n] : "
read -r ENABLE_RDP || ENABLE_RDP=""
ENABLE_RDP="${ENABLE_RDP:-n}"
case "$ENABLE_RDP" in
    o|O|y|Y)
        echo "Configuration du service RDP..."
        sudo systemctl enable --now xrdp
        sudo ufw allow 3389/tcp
        echo "✅ Service RDP configuré."
        ;;
    *)
        echo "RDP non activé."
        ;;
esac

# --- 4. Désactiver udisks2 pour éviter le montage automatique ---
echo "Configuration de udisks2..."
sudo systemctl mask udisks2.service
sudo systemctl stop udisks2.service
sudo tee /etc/udisks2/udisks2.conf << 'EOF'
[udisks2]
auto_mount=false
EOF
sudo systemctl daemon-reload
echo "✅ udisks2 configuré pour ne pas monter automatiquement les périphériques."

# --- 5.1. Purger usbguard s'il est présent (bloque les nouveaux USB) ---
# usbguard force authorized=0 sur les peripheriques non whitelistes via une
# regle udev persistante. Masquer le service ne suffit pas : il faut purger
# le paquet (retire la regle udev) puis recharger udev, sinon les nouveaux USB
# restent bloques au niveau noyau (dmesg : "Device is not authorized").
if command -v usbguard-daemon >/dev/null 2>&1 || dpkg -l usbguard >/dev/null 2>&1; then
    echo "Purge de usbguard (interfère avec la détection USB)..."
    sudo systemctl disable --now usbguard 2>/dev/null || true
    sudo apt-get -y purge usbguard 2>/dev/null || true
    sudo rm -f /etc/udev/rules.d/*usbguard* /lib/udev/rules.d/*usbguard* /usr/lib/udev/rules.d/*usbguard* 2>/dev/null || true
    sudo udevadm control --reload-rules 2>/dev/null || true
    sudo udevadm trigger 2>/dev/null || true
    for dev in /sys/bus/usb/devices/*/authorized; do
        echo 1 | sudo tee "$dev" >/dev/null 2>&1 || true
    done
    echo "✅ usbguard purgé. Les nouveaux périphériques USB seront détectés normalement."
fi

# --- 5. Configurer les permissions pour /investigation ---
sudo chmod 755 /investigation
sudo chown $USER:$USER /investigation

# --- 6. Initialiser les logs et données ---
mkdir -p /opt/vigil/data/{config/logo,projects,users,scans,usb}
mkdir -p /opt/vigil/logs
mkdir -p /opt/vigil/rapports
touch /opt/vigil/data/active_user
touch /opt/vigil/data/active_project
touch /opt/vigil/data/usb/whitelist.txt /opt/vigil/data/usb/blacklist.txt

# --- 6.1. Lien symbolique vigil -> vigil_main_gui.py ---
echo "Création du lien symbolique /usr/local/bin/vigil..."
sudo ln -sf /opt/vigil/gui/vigil_main_gui.py /usr/local/bin/vigil
sudo chmod +x /opt/vigil/gui/vigil_main_gui.py
echo "✅ Lien symbolique /usr/local/bin/vigil créé (pointe vers /opt/vigil/gui/vigil_main_gui.py)."

# --- 7. Configurer sudoers NOPASSWD pour Vigil ---
echo "Configuration de sudoers (sans mot de passe pour Vigil)..."
SUDOERS_FILE="/etc/sudoers.d/vigil"
cat > /tmp/vigil-sudoers << 'SUDOERS_EOF'
# Vigil : permet aux scripts de monter/demonter des peripheriques USB et de
# lancer clamscan/freshclam sans mot de passe. Limite aux commandes utilisees
# par /opt/vigil/scripts/.
Cmnd_Alias VIGIL_MOUNT = /bin/mount, /bin/umount, /sbin/blkid, /sbin/blockdev, /sbin/findmnt, /usr/bin/eject
Cmnd_Alias VIGIL_FS = /bin/mkdir, /bin/rmdir, /bin/rm, /bin/chmod, /bin/chown, /usr/bin/install
Cmnd_Alias VIGIL_CLAM = /usr/bin/clamscan, /usr/bin/freshclam, /usr/bin/clamconf
Cmnd_Alias VIGIL_SYSTEMCTL = /bin/systemctl stop clamav-freshclam, /bin/systemctl start clamav-freshclam, /usr/bin/systemctl stop clamav-freshclam, /usr/bin/systemctl start clamav-freshclam
Cmnd_Alias VIGIL_LOG = /usr/bin/tee
Cmnd_Alias VIGIL_UDEV = /usr/bin/udevadm, /bin/udevadm
Cmnd_Alias VIGIL_MTP = /usr/bin/jmtpfs, /usr/bin/ldmtool
Cmnd_Alias VIGIL_ALL = VIGIL_MOUNT, VIGIL_FS, VIGIL_CLAM, VIGIL_SYSTEMCTL, VIGIL_LOG, VIGIL_UDEV, VIGIL_MTP
ALL ALL=(root) NOPASSWD: VIGIL_ALL
SUDOERS_EOF
sudo install -m 0440 /tmp/vigil-sudoers "$SUDOERS_FILE" && rm -f /tmp/vigil-sudoers
if sudo visudo -c -f "$SUDOERS_FILE" >/dev/null 2>&1; then
    echo "✅ sudoers Vigil configure (NOPASSWD pour les commandes Vigil)."
else
    echo "❌ Erreur de syntaxe sudoers, fichier $SUDOERS_FILE supprime."
    sudo rm -f "$SUDOERS_FILE"
fi

# --- 8. Créer le raccourci bureau (item 6 du checklist) ---
echo "Création du raccourci Vigil..."
# Installer l'icône SVG de l'application dans le chemin système des icônes.
# Le nom 'vigil' est référencé par Icon= dans le fichier .desktop ; KDE/Qt
# résolvent le nom vers /usr/share/icons/hicolor/scalable/apps/vigil.svg.
if [ -f /opt/vigil/data/icons/vigil.svg ]; then
    sudo mkdir -p /usr/share/icons/hicolor/scalable/apps
    sudo install -m 0644 /opt/vigil/data/icons/vigil.svg /usr/share/icons/hicolor/scalable/apps/vigil.svg
    sudo gtk-update-icon-cache -f /usr/share/icons/hicolor 2>/dev/null || true
    VIGIL_ICON="vigil"
else
    VIGIL_ICON="utilities-terminal"
fi
sudo tee /usr/share/applications/vigil.desktop >/dev/null <<DESKTOP_EOF
[Desktop Entry]
Name=Vigil
Comment=Outil d'analyse forensique pour périphériques USB
Exec=python3 /opt/vigil/gui/vigil_main_gui.py
Icon=$VIGIL_ICON
Terminal=false
Type=Application
Categories=Utility;Forensics;
DESKTOP_EOF
sudo update-desktop-database 2>/dev/null || true
echo "✅ Raccourci créé : /usr/share/applications/vigil.desktop"

# --- 9. Ajouter les emplacements Dolphin (item 4 du checklist) ---
# Dolphin (KDE) stocke les emplacements dans ~/.local/share/user-places.xbel
# (format XBEL). On ajoute /investigation, /stockage, /rapports de façon
# idempotente : on ne réécrit pas un emplacement déjà présent.
echo "Ajout des emplacements Dolphin..."
PLACES_FILE="$HOME/.local/share/user-places.xbel"
mkdir -p "$(dirname "$PLACES_FILE")"
# Créer le fichier s'il n'existe pas avec l'en-tête XBEL minimal
if [ ! -f "$PLACES_FILE" ]; then
    cat > "$PLACES_FILE" <<'XBEL_EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE xbel>
<xbel xmlns:kde="http:// kde.org/xbel-ns/1.0/" xmlns:mime="http://www.freedesktop.org/standards/shared-mime-info" xmlns:bookmark="http://www.freedesktop.org/standards/xesam/1.0#">
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
    ' "$PLACES_FILE" > "$tmpfile" && mv "$tmpfile" "$PLACES_FILE"
}
_add_dolphin_place "/investigation" "Investigation"
_add_dolphin_place "/stockage" "Stockage"
_add_dolphin_place "/rapports" "Rapports"
echo "✅ Emplacements ajoutés à Dolphin : /investigation /stockage /rapports"

# --- 10. Mettre a jour les bases de donnees ClamAV ---
echo "Mise à jour des bases de données ClamAV..."
sudo freshclam
echo "✅ Bases de données ClamAV mises à jour."

echo "Script de post-installation terminé."

echo ""
echo "=== Étapes manuelles restantes ==="
echo "Consultez post-install-checked.txt pour le détail :"
echo "  - Bords d'écran : désactiver les actions (Paramètres > Souris & pavé tactile)"
echo "  - Pop-up USB KDE : désactiver \"Disques et Périphériques\" (icônes cachées > Entrées)"
echo "  - Barre des tâches : déplacer en bas (clic droit > Configurer le panneau)"
echo ""
echo "Ces éléments cosmétiques KDE sont figés dans l'image disque préconfigurée,"
echo "ils ne sont pas automatisés (dépendent du layout Plasma de la cible)."