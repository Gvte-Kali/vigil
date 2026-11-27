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
[[ $EUID != 0 ]] || die 'Run as operator / Exécuter comme opérateur.'
[[ -d $site && ! -L $site ]] || die 'Site absent or invalid / Site absent ou invalide.'
. "$site/scripts/lib/vigil-launchers.sh"
. "$site/scripts/lib/vigil-terminal.sh"
check_mounts() {
    local targets
    targets=$(findmnt -rn -o TARGET) || die 'findmnt failed'
    if grep -Eq '^/(investigation|stockage|opt/vigil)(/|$)' <<< "$targets"; then
        die 'Active mounts / Montages actifs'
    fi
}
check_mounts
sudo -v
launchers=()
for dir in /usr/local/bin /usr/bin "$HOME/.local/bin"; do
    for name in vigil vigil-gui vigil-tui vigil2 vigil2-gui; do
        file="$dir/$name"
        if [[ -e $file || -L $file ]]; then
            vigil_owned_launcher "$file" "$site" || die "Unrecognized launcher: $file"
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
        sudo cmp -s "$file" "$source" || die "Unrecognized component: $file"
        files+=("$file")
    fi
done
for file in /usr/share/applications/vigil.desktop "$HOME/.local/share/applications/vigil.desktop"; do
    if [[ -e $file || -L $file ]]; then
        vigil_managed_desktop "$file" "$site" /usr/local/bin || die "Unrecognized shortcut: $file"
        files+=("$file")
    fi
done
packages=()
if ((deps)); then
    manifest="$site/data/apt-installed-by-vigil.txt"
    [[ -f $manifest ]] || die 'Missing APT inventory'
    while IFS= read -r pkg; do
        [[ $pkg =~ ^[a-z0-9][a-z0-9+.-]*(:[a-z0-9-]+)?$ ]] || die "Invalid package: $pkg"
        case "${pkg%%:*}" in sudo|git|python3|python3-minimal|apt|dpkg|udisks2|clamav*) continue ;; esac
        packages+=("$pkg")
    done < "$manifest"
    if (("${#packages[@]}")); then
        plan=$(LC_ALL=C apt-get -s purge -- "${packages[@]}") || die 'APT simulation failed'
        printf '%s\n' "$plan"
        if grep -Eq '^(Inst|Conf) ' <<< "$plan"; then die 'APT would install/configure other packages; review manually'; fi
        while read -r action pkg rest; do
            [[ $action == Purg || $action == Remv ]] || continue
            found=0
            for allowed in "${packages[@]}"; do
                [[ $pkg == "$allowed" ]] && found=1
            done
            ((found)) || die "Unexpected APT removal: $pkg"
        done <<< "$plan"
    fi
fi
printf 'Mode: %s\nSite: %s\n' "$mode" "$site"
printf 'Component: %s\n' "${launchers[@]}" "${files[@]}"
echo 'AppArmor: remove only Vigil FreshClam rules. Empty mount zones only.'
echo 'UDisks2: historical settings require manual review; never reset blindly.'
if ((legacy)); then
    echo 'Legacy archives / Archives historiques:'
    find /opt -maxdepth 1 -type d \( -name 'vigil-1.0-backup.*' -o -name 'vigil-ancien.*' \) -print
fi
((dry == 0)) || exit 0
read -r -p 'Type UNINSTALL to continue / Saisir UNINSTALL : ' answer
[[ $answer == UNINSTALL ]] || die 'Cancelled'
if [[ $mode == purge ]]; then
    read -r -p 'Permanent data loss. Type PURGE / Suppression définitive : ' answer
    [[ $answer == PURGE ]] || die 'Cancelled'
fi
vigil_maintenance_start uninstall 5 "Vigil · Désinstallation / Uninstall"
trap 'vigil_maintenance_exit "$?"' EXIT
vigil_maintenance_step "Restitution USB / USB recovery"
if sudo test -x /usr/local/sbin/vigil-hotplug; then
    sudo /usr/local/sbin/vigil-hotplug recover | python3 -c 'import json,sys
r=json.load(sys.stdin)
print(json.dumps(r))
sys.exit(not (r["status"]=="complete" and all(d["state"] in {"restored","absent"} for d in r["devices"])))' >>"$VIGIL_LOG" 2>&1
elif sudo test -d /run/vigil-hotplug; then
    die 'Recovery helper missing; inspect runtime before continuing'
fi
check_mounts
backup=$(mktemp -d "$HOME/vigil-uninstall.XXXXXX")
vigil_maintenance_step "Lanceurs et protections / Launchers and protections"
printf "\nArchive: %s\n" "$backup"
for file in "${launchers[@]}" "${files[@]}"; do
    sudo rm -- "$file"
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
vigil_maintenance_step "Données et préférences / Data and preferences"
for name in vigil-hotplug vigil-mount; do
    if sudo test -d "/run/$name"; then sudo mv -T "/run/$name" "$backup/$name"; fi
done
for zone in /investigation /stockage /etc/vigil; do
    if [[ -d $zone && ! -L $zone ]]; then sudo rmdir -- "$zone" || echo "Retained nonempty: $zone"; fi
done
for path in "$HOME/.config/Vigil" "$HOME/.local/share/Vigil" "$HOME/.cache/Vigil" "$HOME/.local/state/Vigil"; do
    if [[ -e $path || -L $path ]]; then
        mkdir -p "$backup/user$(dirname "${path#"$HOME"}")"
        mv -- "$path" "$backup/user${path#"$HOME"}"
    fi
done
vigil_maintenance_step "Dépendances et site / Dependencies and site"
if (("${#packages[@]}")); then
    printf "\n"
    sudo apt-get purge -- "${packages[@]}"
fi
check_mounts
cd "$HOME"
sudo mv -T "$site" "$backup/site"
if ((legacy)); then
    while IFS= read -r -d '' path; do
        targets=$(findmnt -rn -o TARGET)
        if grep -Fqx "$path" <<< "$targets" || grep -Fq "$path/" <<< "$targets"; then die "Mounted archive: $path"; fi
        sudo mv -- "$path" "$backup/"
    done < <(find /opt -maxdepth 1 -type d \( -name 'vigil-1.0-backup.*' -o -name 'vigil-ancien.*' \) -print0)
fi
vigil_maintenance_step "Vérification finale / Final checks"
if [[ $mode == purge ]]; then sudo rm -rf --one-file-system -- "$backup"; fi
printf '\n'
if ! sudo find /etc /usr/local /opt /run -xdev -path /run/user -prune -o -iname '*vigil*' -print >>"$VIGIL_LOG" 2>&1; then
    vigil_style 33 '[ WARN ] Vérification des résidus incomplète / Residual scan incomplete'
    exit 1
fi
vigil_maintenance_finish
echo 'Désinstallation terminée / Uninstall complete'
printf 'Residuals and details: %s\n' "$VIGIL_LOG"
echo 'No automatic autoremove. / Aucun autoremove automatique.'
