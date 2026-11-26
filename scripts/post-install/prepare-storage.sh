#!/bin/sh
set -eu

script_directory=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
. "$script_directory/../lib/vigil-terminal.sh"
. "$script_directory/../lib/vigil-storage-root.sh"

vigil_banner 'Vigil · Préparation de /stockage / Preparing /stockage'
printf '%s\n' 'FR — sudo prépare le dossier /stockage démonté avec les permissions root:root 0755.' \
    'EN — sudo prepares the unmounted /stockage directory with root:root 0755 permissions.' ''

target=/stockage
exec 9</run/lock
if ! flock -n -x 9; then
    vigil_text "Fermez l’opération Vigil en cours avant de préparer /stockage."                "Close the active Vigil operation before preparing /stockage." >&2
    exit 1
fi
if ! mounts=$(findmnt -rn -o TARGET); then
    echo "Impossible de vérifier les montages de /stockage." >&2
    exit 1
fi
if printf '%s\n' "$mounts" | awk '$0 ~ "^/stockage(/|$)" { mounted=1 } END { exit !mounted }'; then
    echo "Démontez /stockage et ses sous-montages avant de corriger les permissions." >&2
    exit 1
fi
if [ -L "$target" ] || { [ -e "$target" ] && [ ! -d "$target" ]; }; then
    echo "/stockage doit être un répertoire réel. Vérifiez ce chemin avant de continuer." >&2
    exit 1
fi

sudo install -d -o root -g root -m 0755 -- "$target"
vigil_storage_root_check "$target"
stat -c '%n : %U:%G, mode %a' -- "$target"
