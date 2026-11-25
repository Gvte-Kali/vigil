#!/bin/sh
set -eu
script_directory=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
. "$script_directory/../lib/vigil-terminal.sh"

vigil_banner 'Vigil · Protection des nouveaux disques / New disk protection'
printf '%s\n' \
    'FR — Autorisez sudo pour protéger en lecture seule les disques branchés pendant cette session et empêcher leur montage automatique par UDisks.' \
    'Au départ, les disques déjà connectés gardent leur état. À la fermeture de la dernière session, Vigil rétablit les modes qu’il a modifiés lorsque le support est toujours présent et disponible.' \
    '' \
    'EN — Authorise sudo to make disks connected during this session read-only and prevent UDisks from mounting them automatically.' \
    'Disks already connected keep their state. When the last session closes, Vigil restores the modes it changed on devices that are still connected and available.' \
    ''
vigil_style '1;93' 'Saisissez votre mot de passe sudo, ou Ctrl+C pour laisser la protection inactive. / Enter your sudo password, or press Ctrl+C to leave protection inactive.'
if /usr/bin/sudo -- /usr/local/sbin/vigil-hotplug activate "$1"; then
    vigil_style 92 'Protection activée. / Protection enabled.'
else
    vigil_style 91 'Protection inactive. / Protection is inactive.'
    if [ -t 0 ]; then
        printf '%s' 'Entrée pour fermer / Press Enter to close: '
        read -r ignored || true
    fi
    exit 1
fi
