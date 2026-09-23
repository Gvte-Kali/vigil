#!/bin/bash
set -euo pipefail

# --- 1. Installer les dépendances si manquantes ---
if ! command -v convert &> /dev/null; then
    echo "Installation de ImageMagick..."
    sudo apt install -y imagemagick
fi
if ! command -v feh &> /dev/null; then
    echo "Installation de feh..."
    sudo apt install -y feh
fi

# --- 2. Tuer les instances existantes de feh ---
pkill feh 2>/dev/null || true

# --- 3. Fonction pour générer l'image ---
generate_wallpaper() {
    # Supprimer l'ancienne image
    rm -f /tmp/lsblk_wallpaper.png

    # Récupérer la sortie de lsblk (nettoyée)
    LSBLK_OUTPUT=$(lsblk -d -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,LABEL,MODEL -e 7 -e 1 | column -t -s $'\t')

    # Créer une image avec le texte
    convert -background '#000000' -fill '#00FF00' -font 'Courier' -pointsize 14 -size 1920x1080 caption:"$LSBLK_OUTPUT" /tmp/lsblk_wallpaper.png
}

# --- 4. Boucle de mise à jour ---
while true; do
    generate_wallpaper
    feh --bg-scale --no-fehbg /tmp/lsblk_wallpaper.png
    sleep 2
done