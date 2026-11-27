#!/usr/bin/bash
# Native Debian/Parrot site uninstall. Run as the operator, not root.
set -euo pipefail
site=/opt/vigil
dry=0
mode=keep
deps=0
legacy=0
usage() {
    echo 'Usage: bash uninstall.sh [--dry-run] [--keep-data|--purge] [--purge-dependencies] [--legacy]'
    echo 'FR: fermer Vigil et débrancher les supports après restitution.'
    echo 'EN: close Vigil and disconnect media after verified restoration.'
}
die() { printf 'STOP: %s\n' "$*" >&2; exit 1; }
for arg in "$@"; do
    case "$arg" in
        --dry-run) dry=1 ;;
        --keep-data) mode=keep ;;
        --purge) mode=purge ;;
        --purge-dependencies) deps=1 ;;
        --legacy) legacy=1 ;;
        --help|-h) usage; exit 0 ;;
        *) usage; exit 2 ;;
    esac
done
[[ $EUID != 0 ]] || die 'Exécuter comme opérateur / Run as operator.'
[[ -d $site && ! -L $site ]] || die 'Site absent ou invalide / Site missing or invalid.'
. "$site/scripts/lib/vigil-launchers.sh"
. "$site/scripts/lib/vigil-terminal.sh"
vigil_maintenance_choose_language
check_mounts() {
    local targets
    targets=$(findmnt -rn -o TARGET) || die "$(vigil_text 'Échec de findmnt' 'findmnt failed')"
    if grep -Eq '^/(investigation|stockage|opt/vigil)(/|$)' <<< "$targets"; then
        die "$(vigil_text 'Montages actifs' 'Active mounts')"
    fi
}
check_mounts
sudo -v
launchers=()
for dir in /usr/local/bin /usr/bin "$HOME/.local/bin"; do
    for name in vigil vigil-gui vigil-tui vigil2 vigil2-gui; do
        file="$dir/$name"
        if [[ -e $file || -L $file ]]; then
            vigil_owned_launcher "$file" "$site" || die "$(vigil_text "Lanceur non reconnu : $file" "Unrecognized launcher: $file")"
            launchers+=("$file")
        fi
    done
done
files=()
for file in /usr/local/sbin/vigil-hotplug /usr/local/sbin/vigil-mount /etc/udev/rules.d/99-vigil-hotplug.rules /usr/share/icons/hicolor/scalable/apps/vigil.svg; do
    if sudo test -e "$file"; then
        case "$file" in
            */vigil.svg) source="$site/data/icons/vigil.svg" ;;
            *) source="$site/scripts/privileged/${file##*/}" ;;
        esac
        sudo cmp -s "$file" "$source" || die "$(vigil_text "Composant non reconnu : $file" "Unrecognized component: $file")"
        files+=("$file")
    fi
done
if desktop_directory=$(vigil_desktop_directory); then
    file="$desktop_directory/Vigil.desktop"
    if vigil_managed_desktop "$file" "$site" /usr/local/bin; then
        files+=("$file")
    fi
fi
for file in /usr/share/applications/vigil.desktop "$HOME/.local/share/applications/vigil.desktop"; do
    if [[ -e $file || -L $file ]]; then
        vigil_managed_desktop "$file" "$site" /usr/local/bin || die "$(vigil_text "Raccourci non reconnu : $file" "Unrecognized shortcut: $file")"
        files+=("$file")
    fi
done
packages=()
if ((deps)); then
    manifest="$site/data/apt-installed-by-vigil.txt"
    [[ -f $manifest && ! -L $manifest ]] || die "$(vigil_text 'Inventaire APT introuvable' 'Missing APT inventory')"
    while IFS= read -r pkg; do
        [[ $pkg =~ ^[a-z0-9][a-z0-9+.-]*(:[a-z0-9-]+)?$ ]] || die "$(vigil_text "Paquet invalide : $pkg" "Invalid package: $pkg")"
        case "${pkg%%:*}" in sudo|git|python3|python3-minimal|apt|dpkg|udisks2|clamav*) continue ;; esac
        packages+=("$pkg")
    done < "$manifest"
    if (("${#packages[@]}")); then
        plan=$(LC_ALL=C apt-get -s purge -- "${packages[@]}") || die "$(vigil_text 'Échec de la simulation APT' 'APT simulation failed')"
        printf '%s\n' "$plan"
        if grep -Eq '^(Inst|Conf) ' <<< "$plan"; then die "$(vigil_text 'APT modifierait aussi d’autres paquets ; vérifiez manuellement' 'APT would install/configure other packages; review manually')"; fi
        while read -r action pkg rest; do
            [[ $action == Purg || $action == Remv ]] || continue
            found=0
            for allowed in "${packages[@]}"; do
                [[ $pkg == "$allowed" ]] && found=1
            done
            ((found)) || die "$(vigil_text "Suppression APT inattendue : $pkg" "Unexpected APT removal: $pkg")"
        done <<< "$plan"
    fi
fi
printf '%s: %s\n%s: %s\n' "$(vigil_text 'Mode' 'Mode')" "$mode" "$(vigil_text 'Site' 'Site')" "$site"
printf '%s: %s\n' "$(vigil_text 'Composant' 'Component')" "${launchers[@]}" "${files[@]}"
echo "$(vigil_text 'AppArmor : retirer uniquement les règles FreshClam de Vigil. Ne supprimer que les zones de montage vides.' 'AppArmor: remove only Vigil FreshClam rules. Empty mount zones only.')"
echo "$(vigil_text 'UDisks2 : les anciens réglages nécessitent un contrôle manuel ; ne pas réinitialiser sans vérification.' 'UDisks2: historical settings require manual review; never reset blindly.')"
if ((legacy)); then
    echo "$(vigil_text 'Archives historiques :' 'Legacy archives:')"
    find /opt -maxdepth 1 -type d \( -name 'vigil-1.0-backup.*' -o -name 'vigil-ancien.*' \) -print
fi
check_sessions() {
    local sessions
    sessions=$(ps -eo pid=,args= | awk '$2 ~ /^\/opt\/vigil\/\.venv\/bin\// || $0 ~ /[v]igil-hotplug activate [0-9]+$/') || die "$(vigil_text 'Échec de ps' 'ps failed')"
    if [[ -n "$sessions" ]]; then
        vigil_style 33 "[ WARN ] $(vigil_text 'Fermez Vigil avant de continuer.' 'Close Vigil before continuing.')"
        printf '%s\n' "$sessions"
        return 1
    fi
}
if ((dry)); then check_sessions || exit 1; exit 0; fi
while ! check_sessions; do
    [[ -t 0 ]] || exit 1
    read -r -p "$(vigil_text 'Entrée pour revérifier, Ctrl+C pour annuler : ' 'Enter to retry, Ctrl+C to cancel: ')" answer || exit 1
done
check_mounts
read -r -p "$(vigil_text 'Saisir UNINSTALL pour continuer : ' 'Type UNINSTALL to continue: ')" answer
[[ $answer == UNINSTALL ]] || die "$(vigil_text 'Annulé' 'Cancelled')"
if [[ $mode == purge ]]; then
    read -r -p "$(vigil_text 'Suppression définitive des données. Saisir PURGE : ' 'Permanent data loss. Type PURGE: ')" answer
    [[ $answer == PURGE ]] || die "$(vigil_text 'Annulé' 'Cancelled')"
fi
check_sessions || exit 1
vigil_maintenance_start uninstall 5 "$(vigil_text 'Vigil · Désinstallation' 'Vigil · Uninstall')"
trap 'vigil_maintenance_exit "$?"' EXIT
vigil_maintenance_step "$(vigil_text 'Restitution USB' 'USB recovery')"
if sudo test -x /usr/local/sbin/vigil-hotplug; then
    sudo /usr/local/sbin/vigil-hotplug recover 2>>"$VIGIL_LOG" | python3 -c 'import json,sys
r=json.load(sys.stdin)
print(json.dumps(r))
sys.exit(not (r["status"]=="complete" and all(d["state"] in {"restored","absent"} for d in r["devices"])))' >>"$VIGIL_LOG" 2>&1
elif sudo test -d /run/vigil-hotplug; then
    die "$(vigil_text 'Assistant de restitution absent ; inspectez l’état avant de continuer' 'Recovery helper missing; inspect runtime before continuing')"
fi
check_mounts
backup=$(mktemp -d "$HOME/vigil-uninstall.XXXXXX")
vigil_maintenance_step "$(vigil_text 'Lanceurs et protections' 'Launchers and protections')"
printf '\n%s: %s\n' "$(vigil_text 'Archive' 'Archive')" "$backup"
for file in "${launchers[@]}" "${files[@]}"; do
    if [[ $file == "$HOME/"* ]]; then rm -- "$file"; else sudo rm -- "$file"; fi
done
sudo udevadm control --reload-rules
profile=/etc/apparmor.d/local/usr.bin.freshclam
if sudo test -f "$profile"; then
    sudo cp -a "$profile" "$backup/freshclam-local"
    sudo sed -i '\|^[[:space:]]*owner /opt/vigil/data/state/clamav/ rw,$|d;\|^[[:space:]]*owner /opt/vigil/data/state/clamav/\*\* rwk,$|d' "$profile"
    if [[ -f /etc/apparmor.d/usr.bin.freshclam && $(cat /sys/module/apparmor/parameters/enabled 2>/dev/null || :) == Y ]]; then
        sudo apparmor_parser -r /etc/apparmor.d/usr.bin.freshclam
    fi
fi
vigil_maintenance_step "$(vigil_text 'Données et préférences' 'Data and preferences')"
for name in vigil-hotplug vigil-mount; do
    if sudo test -d "/run/$name"; then sudo mv -T "/run/$name" "$backup/$name"; fi
done
for zone in /investigation /stockage /etc/vigil; do
    if [[ -d $zone && ! -L $zone ]]; then sudo rmdir -- "$zone" || echo "$(vigil_text "Conservé car non vide : $zone" "Retained nonempty: $zone")"; fi
done
for path in "$HOME/.config/Vigil" "$HOME/.local/share/Vigil" "$HOME/.cache/Vigil" "$HOME/.local/state/Vigil"; do
    if [[ -e $path || -L $path ]]; then
        mkdir -p "$backup/user$(dirname "${path#"$HOME"}")"
        mv -- "$path" "$backup/user${path#"$HOME"}"
    fi
done
vigil_maintenance_step "$(vigil_text 'Dépendances et site' 'Dependencies and site')"
if (("${#packages[@]}")); then
    printf "\n"
    sudo apt-get purge --no-auto-remove -- "${packages[@]}"
fi
check_mounts
cd "$HOME"
sudo mv -T "$site" "$backup/site"
if ((legacy)); then
    while IFS= read -r -d '' path; do
        targets=$(findmnt -rn -o TARGET)
        if grep -Fqx "$path" <<< "$targets" || grep -Fq "$path/" <<< "$targets"; then die "$(vigil_text "Archive montée : $path" "Mounted archive: $path")"; fi
        sudo mv -- "$path" "$backup/"
    done < <(find /opt -maxdepth 1 -type d \( -name 'vigil-1.0-backup.*' -o -name 'vigil-ancien.*' \) -print0)
fi
vigil_maintenance_step "$(vigil_text 'Vérification finale' 'Final checks')"
if [[ $mode == purge ]]; then
    targets=$(findmnt -rn -o TARGET) || die "$(vigil_text 'Échec de findmnt' 'findmnt failed')"
    [[ $backup == "$HOME"/vigil-uninstall.* && -d $backup && ! -L $backup ]] || die "$(vigil_text 'Archive invalide' 'Invalid archive')"
    if grep -Fqx "$backup" <<< "$targets" || grep -Fq "$backup/" <<< "$targets"; then die "$(vigil_text 'Archive montée' 'Mounted archive')"; fi
    sudo rm -rf --one-file-system -- "$backup"
fi
printf '\n'
if ! sudo find /etc /usr/local /opt /run -xdev -path /run/user -prune -o -iname '*vigil*' -print >"$VIGIL_LOG.residuals" 2>>"$VIGIL_LOG"; then
    vigil_style 33 "[ WARN ] $(vigil_text 'Vérification des résidus incomplète' 'Residual scan incomplete')"
    exit 1
fi
if [[ -s "$VIGIL_LOG.residuals" ]]; then
    vigil_style 33 "[ WARN ] $(vigil_text 'Résidus à examiner' 'Residuals to review')"
    cat "$VIGIL_LOG.residuals" | tee -a "$VIGIL_LOG"
else
    vigil_style 32 "[ OK ] $(vigil_text 'Aucun résidu système détecté' 'No system residuals detected')"
fi
rm -- "$VIGIL_LOG.residuals"
vigil_maintenance_finish
echo "$(vigil_text 'Désinstallation terminée' 'Uninstall complete')"
printf '%s: %s\n' "$(vigil_text 'Résidus et détails' 'Residuals and details')" "$VIGIL_LOG"
echo "$(vigil_text 'Aucun autoremove automatique.' 'No automatic autoremove.')"
