#!/bin/sh
set -eu
script_directory=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
. "$script_directory/../lib/vigil-terminal.sh"

if [ "${VIGIL_EMBEDDED_TERMINAL:-}" = 1 ]; then
    vigil_style '1;96' "$(vigil_text 'Protection USB' 'USB protection')"
    printf '%s\n' "$(vigil_text \
        'Autorisez sudo pour protéger les nouveaux disques en RO et bloquer leur automontage. La dernière fermeture restaure leur état.' \
        'Authorise sudo to protect new disks read-only and block automount. Closing the last session restores their state.')"
else
    vigil_banner 'Vigil · Protection des nouveaux disques / New disk protection'
    printf '%s\n' \
        'FR — Autorisez sudo pour protéger en lecture seule les disques branchés pendant cette session et empêcher leur montage automatique par UDisks.' \
        'Au départ, les disques déjà connectés gardent leur état. À la fermeture de la dernière session, Vigil rétablit les modes qu’il a modifiés lorsque le support est toujours présent et disponible.' \
        '' \
        'EN — Authorise sudo to make disks connected during this session read-only and prevent UDisks from mounting them automatically.' \
        'Disks already connected keep their state. When the last session closes, Vigil restores the modes it changed on devices that are still connected and available.' \
        ''
    vigil_style '1;93' 'Saisissez votre mot de passe sudo, ou Ctrl+C pour laisser la protection inactive. / Enter your sudo password, or press Ctrl+C to leave protection inactive.'
fi
action=activate
[ "${2:-}" != "--reconcile-required" ] || action=activate-reconciled
if /usr/bin/sudo -- /usr/local/sbin/vigil-hotplug "$action" "$1"; then
    vigil_style 92 'Protection activée. / Protection enabled.'
else
    vigil_style 91 'Protection inactive. / Protection is inactive.'
    if [ "$action" = activate-reconciled ]; then
        printf '%s\n' "$(vigil_text "Si l’assistant installé est ancien, relancez scripts/post-install/install-hotplug.sh." \
            "If the installed helper is outdated, rerun scripts/post-install/install-hotplug.sh.")"
    fi
    if [ -t 0 ] && [ "${VIGIL_EMBEDDED_TERMINAL:-}" != 1 ]; then
        printf '%s' 'Entrée pour fermer / Press Enter to close: '
        read -r ignored || true
    fi
    exit 1
fi
