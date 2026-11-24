# Shared read-only input discovery for the Vigil 2 analysis adapters.
case_analysis_prepare() {
    if ! python3 -I "$VIGIL_BASE/scripts/analyse/vigil_census_mount_guard.py" > "$WORK_DIR/mounts"; then
        fail "Les montages de l’affaire ne sont pas vérifiables en lecture seule."
    fi
    local -a roots=()
    mapfile -d '' -t roots < "$WORK_DIR/mounts"
    MOUNTED_DIRS=${#roots[@]}
    if ! find "${roots[@]}" -xdev -type f -print0 > "$WORK_DIR/files"; then
        fail "Parcours incomplet : consultez les erreurs de lecture ci-dessus."
    fi
}
