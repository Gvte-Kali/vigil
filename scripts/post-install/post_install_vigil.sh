#!/bin/bash
set -euo pipefail

# Les installations existantes doivent retirer la règle héritée manuellement.
sudo -v
if sudo test -e /etc/sudoers.d/vigil; then
    echo "Règle sudoers Vigil existante : faites-la examiner et retirer par l'administrateur."
    echo "Voir docs/development/phase-01-transition.md."
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

if [ "$EUID" -eq 0 ]; then
    echo "Démarrez le post-install depuis la session de l'opérateur, avec sudo interactif."
    exit 1
fi
if [ ! -w /opt/vigil ] || [ ! -w /opt/vigil/data ] || [ ! -w /opt/vigil/logs ] || [ ! -w /opt/vigil/rapports ]; then
    echo "Faites préparer les répertoires de données par l'administrateur."
    echo "Voir docs/development/phase-01-transition.md."
    exit 1
fi

# --- 1. Verifier et creer les repertoires necessaires ---
echo "Création des répertoires..."
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
sudo mkdir -p /stockage /opt/vigil/{data,scripts,logs,rapports}
echo "✅ Répertoires de base présents."

# --- 2. Installer les dependances depuis requirements.txt ---
# Les paquets y sont documentes (un commentaire par paquet).
# La liste ci-dessous reste synchronisee avec ce fichier : elle sert de
# secours si requirements.txt est introuvable.
REQUIREMENTS_FILE="/opt/vigil/scripts/post-install/requirements.txt"
FALLBACK_PKGS="util-linux coreutils jq eject cryptsetup clamav clamav-daemon clamav-freshclam xrdp xorgxrdp udisks2 ufw konsole kdialog zenity jmtpfs ntfs-3g exfat-fuse dc3dd ewf-tools afflib-tools sleuthkit autopsy yara guymager gnupg ldmtool exiftool ffmpeg p7zip-full zstd binwalk pv file gdisk cloud-guest-utils parted imagemagick feh python3 python3-venv python3-tk python3-pil python3-pip python3-reportlab python3-cairosvg libcairo2 facedetect python3-opencv"
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

# --- 6. Initialiser les logs et données ---
mkdir -p /opt/vigil/data/{config/logo,projects,users,scans,usb}
mkdir -p /opt/vigil/logs
mkdir -p /opt/vigil/rapports
touch /opt/vigil/data/active_user
touch /opt/vigil/data/active_project
touch /opt/vigil/data/usb/whitelist.txt /opt/vigil/data/usb/blacklist.txt

# --- 6.1. Installer Qt dans /opt/vigil ---
python3 -m venv /opt/vigil/.venv
/opt/vigil/.venv/bin/python -m pip install -e '/opt/vigil[desktop]'
signature_dir=/opt/vigil/data/state/clamav
if [ "$(realpath -m -- "$signature_dir")" != "$signature_dir" ]; then
    echo "Le répertoire des signatures traverse un lien symbolique : $signature_dir" >&2
    exit 1
fi
install -d -m 0700 /opt/vigil/data/state "$signature_dir"

# --- 6.2. Autoriser seulement le répertoire de signatures dans AppArmor ---
profile=/etc/apparmor.d/usr.bin.freshclam
local_profile=/etc/apparmor.d/local/usr.bin.freshclam
if [ -f "$profile" ] && command -v apparmor_parser >/dev/null; then
    if ! grep -Eq '^[[:space:]]*#?include([[:space:]]+if exists)?[[:space:]]+<local/usr.bin.freshclam>' "$profile"; then
        echo "Le profil FreshClam n’inclut pas $local_profile. Consultez docs/configuration/clamav.md." >&2
        exit 1
    fi
    sudo install -d -m 0755 /etc/apparmor.d/local
    sudo touch "$local_profile"
    for rule in "owner $signature_dir/ rw," "owner $signature_dir/** rwk,"; do
        if ! sudo grep -Fxq -- "$rule" "$local_profile"; then
            printf '\n%s\n' "$rule" | sudo tee -a "$local_profile" >/dev/null
        fi
    done
    if [ "$(cat /sys/module/apparmor/parameters/enabled 2>/dev/null || true)" = Y ]; then
        sudo apparmor_parser -r "$profile"
    fi
elif [ -f "$profile" ]; then
    echo "apparmor_parser indisponible : configuration FreshClam à valider par l’administrateur." >&2
fi

sudo ln -sf /opt/vigil/scripts/post-install/vigil-qt /usr/local/bin/vigil

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

# Les signatures du profil Vigil sont téléchargées sur demande depuis Qt.
echo "Pour initialiser les signatures locales, ouvrez Vigil puis Actions rapides > Mettre à jour l’antivirus."

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