#!/bin/sh
set -eu

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
