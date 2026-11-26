#!/bin/bash
# Legacy online update entry point. Use the same profile as Vigil Core.
set -eu

source "$(dirname -- "${BASH_SOURCE[0]}")/../lib/vigil-terminal.sh"
vigil_banner "$(vigil_text "Mise à jour des signatures ClamAV" "Update ClamAV signatures")"
core="$(dirname -- "${BASH_SOURCE[0]}")/../../vigil/clamav.py"
exec python3 "$core" refresh
