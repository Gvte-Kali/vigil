#!/bin/sh
set -eu

script_directory=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
. "$script_directory/../lib/vigil-terminal.sh"

vigil_banner 'Vigil · Préparation de /stockage / Preparing /stockage'
printf '%s\n' 'FR — sudo prépare le dossier /stockage démonté avec les permissions root:root 0755.' \
    'EN — sudo prepares the unmounted /stockage directory with root:root 0755 permissions.' ''

target=/stockage
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
stat -c '%n : %U:%G, mode %a' -- "$target"
