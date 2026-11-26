#!/bin/bash
set -euo pipefail

# Update launchers, the package and the scoped FreshClam access. Run from the operator session.
if [ "$EUID" -eq 0 ]; then
    printf '%s\n' 'Lancez ce script en tant qu’opérateur / Run this script as the operator.' >&2
    exit 1
fi
. /opt/vigil/scripts/lib/vigil-launchers.sh
. /opt/vigil/scripts/lib/vigil-freshclam.sh
printf '%s\n'     'FR — sudo met à jour les lanceurs système de Vigil. Les données d’enquête restent en place.'     'EN — sudo updates the Vigil system launchers. Investigation data stays in place.'
vigil_install_cli /opt/vigil /usr/local/bin /usr/bin /usr/share/applications/vigil.desktop
vigil_prepare_freshclam /opt/vigil/data/state/clamav
