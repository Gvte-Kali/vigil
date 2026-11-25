#!/bin/bash
set -uo pipefail

export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH"

. "$(dirname -- "${BASH_SOURCE[0]}")/../lib/vigil-terminal.sh"
. "$(dirname -- "${BASH_SOURCE[0]}")/../lib/vigil-device-triage.sh"

print_banner() {
    vigil_logo
}
# --- Vérifier qu'un utilisateur (obligatoire) et un projet sont actifs ---
# --- Contexte actif (utilisateur + projet) : non bloquant pour le montage ---
# Le montage est une opération matérielle utilitaire : elle doit rester
# possible même sans utilisateur/projet actifs. Si un contexte existe, on
# l'utilise pour tracer l'action dans la chaîne de custody ; sinon, on monte
# quand même et on n'écrit pas de log.
VIGIL_BASE="${VIGIL_BASE:-/opt/vigil}"
VIGIL_DATA_DIR="${VIGIL_DATA_DIR:-$VIGIL_BASE/data}"
USB_LISTS_DIR="$VIGIL_DATA_DIR/usb"
USB_WHITELIST_FILE="$USB_LISTS_DIR/whitelist.txt"
USB_BLACKLIST_FILE="$USB_LISTS_DIR/blacklist.txt"
mkdir -p "$USB_LISTS_DIR" 2>/dev/null || true
touch "$USB_WHITELIST_FILE" "$USB_BLACKLIST_FILE" 2>/dev/null || true
ACTIVE_PROJECT_FILE="$VIGIL_BASE/data/active_project"
ACTIVE_USER_FILE="$VIGIL_BASE/data/active_user"
PROJECTS_DIR="$VIGIL_BASE/data/projects"
CONFIG_FILE="${VIGIL_DATA_DIR:-$VIGIL_BASE/data}/config/system.json"

ERRORS=0

ACTIVE_USER="(no-user)"
[ -f "$ACTIVE_USER_FILE" ] && ACTIVE_USER=$(cat "$ACTIVE_USER_FILE" 2>/dev/null)
[ -n "${VIGIL_LEGACY_CASE_DIR:-}" ] && ACTIVE_USER="${VIGIL_ACTIVE_USER:-}"
[ -z "$ACTIVE_USER" ] && ACTIVE_USER="(no-user)"

ACTIVE_PROJECT="(no-project)"
[ -f "$ACTIVE_PROJECT_FILE" ] && ACTIVE_PROJECT=$(cat "$ACTIVE_PROJECT_FILE" 2>/dev/null || echo "")
[ -n "${VIGIL_LEGACY_CASE_DIR:-}" ] && ACTIVE_PROJECT="${VIGIL_LEGACY_PROJECT:-}"
[ -z "$ACTIVE_PROJECT" ] && ACTIVE_PROJECT="(no-project)"

ACTIVE_ENTITY="(non configuree)"
if [ -f "$CONFIG_FILE" ] && command -v jq >/dev/null 2>&1; then
    ACTIVE_ENTITY=$(jq -r '.entity_name // empty' "$CONFIG_FILE" 2>/dev/null || echo "")
    [ -z "$ACTIVE_ENTITY" ] && ACTIVE_ENTITY="(non configuree)"
fi

PROJECT_TEE=(sudo tee)
if [ -n "${VIGIL_LEGACY_CASE_DIR:-}" ]; then
    PROJECT_TEE=(tee)
    PROJECT_LOG_DIR="$VIGIL_LEGACY_CASE_DIR"
elif [ "$ACTIVE_PROJECT" = "(no-project)" ]; then
    PROJECT_LOG_DIR="/tmp"
else
    PROJECT_LOG_DIR="$PROJECTS_DIR/$ACTIVE_PROJECT"
fi

# --- Compteur d'erreurs global et pause finale ---
# final_pause() s'assure que le terminal (Konsole) ne se ferme jamais sans
# que l'utilisateur ait lu le message d'erreur final.
final_pause() {
    echo ""
    if [ "$ERRORS" -gt 0 ]; then
        echo -e "${RED}❌ Script terminé avec $ERRORS erreur(s).${NC}"
        echo -e "${YELLOW}$(vigil_text "Appuyez sur Entrée pour fermer ce terminal..." "Press Enter to close this terminal...")${NC}"
        read -r
        exit 1
    else
        echo -e "${GREEN}✅ Script terminé sans erreur.${NC}"
    fi
}

# error_exit : affiche un message d'erreur, incrémente le compteur et pause.
# Ne quitte PAS brutalement : l'utilisateur garde la main sur le terminal.
fail() {
    echo -e "${RED}❌ $1${NC}"
    ERRORS=$((ERRORS + 1))
    final_pause
    exit 1
}

# --- Fonction pour logger ---
log_action() {
    local action="$1"
    local device="$2"
    local file_path="$3"
    local status="$4"
    local message="$5"

    # Chasse (recherche de menaces) : chaque evenement est journalise dans
    # hunt/chain_of_custody.json (section custody du rapport consolide),
    # meme sans projet. VIGIL_HUNT_CUSTODY est exporte par la chasse.
    if [ -n "${VIGIL_HUNT_CUSTODY:-}" ]; then
        local timestamp
        timestamp=$(date +"%Y-%m-%dT%H:%M:%S.%6NZ")
        local _user="$ACTIVE_USER"
        [ -n "${VIGIL_ACTIVE_USER:-}" ] && _user="$VIGIL_ACTIVE_USER"
        if command -v jq >/dev/null 2>&1; then
            jq -c -n \
                --arg timestamp "$timestamp" \
                --arg user "$_user" \
                --arg action "$action" \
                --arg status "$status" \
                --arg message "$message" \
                --arg device "$device" \
                '{timestamp: $timestamp, user: $user, action: $action,
                  status: $status, message: $message, device: $device}' \
                >> "$VIGIL_HUNT_CUSTODY" 2>/dev/null || true
        else
            printf '{"timestamp":"%s","user":"%s","action":"%s","status":"%s","message":"%s"}\n' \
                "$timestamp" "$_user" "$action" "$status" "$message" \
                >> "$VIGIL_HUNT_CUSTODY" 2>/dev/null || true
        fi
    fi
    # Sans utilisateur ni projet actif, pas de chaîne de custody projet.
    [ "$ACTIVE_USER" = "(no-user)" ] && return
    [ "$ACTIVE_PROJECT" = "(no-project)" ] && return

    local timestamp=$(date +"%Y-%m-%dT%H:%M:%S.%6NZ")
    local log_entry="[$timestamp] User:$ACTIVE_USER | Entity:$ACTIVE_ENTITY | Project:$ACTIVE_PROJECT | Action:$action | Device:$device | File:$file_path | Status:$status | Message:$message"

    echo "$log_entry" | "${PROJECT_TEE[@]}" -a "$PROJECT_LOG_DIR/chain_of_custody.log" > /dev/null 2>&1 || true

    if command -v jq >/dev/null 2>&1; then
        jq -n \
            --arg timestamp "$timestamp" \
            --arg user "$ACTIVE_USER" \
            --arg entity "$ACTIVE_ENTITY" \
            --arg project "$ACTIVE_PROJECT" \
            --arg action "$action" \
            --arg device "$device" \
            --arg file_path "$file_path" \
            --arg status "$status" \
            --arg message "$message" \
            '{timestamp: $timestamp, user: $user, entity: $entity, project: $project, action: $action, device: $device, file_path: $file_path, status: $status, message: $message}' \
        | "${PROJECT_TEE[@]}" -a "$PROJECT_LOG_DIR/actions.log" > /dev/null 2>&1 || true
    fi
}

# --- Lister les points de montage réels sous /investigation (récursif) ---
# Les montages multi-partitions sont imbriqués (/investigation/<disk>/<part>),
# donc un simple `find -maxdepth 1` ne les détecte pas. /proc/mounts est la
# source de vérité du noyau : fichier texte listant tous les montages du
# namespace courant, sans dépendre d'aucune commande externe. On lit le
# 2e champ (point de montage) des lignes sous /investigation, puis on trie
# du plus profond au moins profond afin de démonter les enfants avant les
# parents (sinon umount renvoie "target busy"). Fallback lsblk (qui lit
# /sys) si /proc/mounts est vide pour une raison inattendue.
list_mounts_under_investigation() {
    local mounts
    mounts="$(awk '$2 ~ "^/investigation/" {print $2}' /proc/mounts 2>/dev/null)"
    if [ -z "$mounts" ] && command -v lsblk >/dev/null 2>&1; then
        mounts="$(lsblk -J -o MOUNTPOINTS 2>/dev/null \
            | grep -oE '"/investigation/[^"]*"' | tr -d '"')"
    fi
    printf '%s\n' "$mounts" \
        | awk -v base="/investigation/" 'index($0, base) == 1' \
        | awk '{ print length($0), $0 }' | sort -rn | cut -d' ' -f2-
}

# Créer les dossiers de logs et d'investigation s'ils n'existent pas
mkdir -p "$PROJECT_LOG_DIR" 2>/dev/null || {
    echo -e "${RED}❌ Impossible de créer $PROJECT_LOG_DIR${NC}"
    echo -e "${YELLOW}    Vérifiez les droits d'écriture sur $VIGIL_BASE/data/projects/${NC}"
    ERRORS=$((ERRORS + 1))
    final_pause
    exit 1
}
sudo mkdir -p /investigation 2>/dev/null || true
sudo chmod 755 /investigation 2>/dev/null || true

# --- Vérifications des privilèges et dépendances ---
if [ "$(id -u)" -ne 0 ] && ! sudo -n true 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Ce script nécessite des privilèges root pour monter les périphériques.${NC}"
    echo -e "${YELLOW}    Vérifiez la configuration sudo de l'utilisateur courant.${NC}"
fi

echo -e "${BLUE}=== Vérification des dépendances ===${NC}"
MISSING_DEPS=0
for cmd in lsblk mount find sha256sum; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo -e "${RED}❌ Outil requis absent : $cmd${NC}"
        MISSING_DEPS=$((MISSING_DEPS + 1))
    fi
done
# Outils optionnels (avertissement seulement)
for cmd in jq cryptsetup clamscan jmtpfs eject blockdev; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  Outil optionnel absent : $cmd (certaines fonctionnalités seront désactivées)${NC}"
    fi
done

if [ "$MISSING_DEPS" -gt 0 ]; then
    fail "Dépendances obligatoires manquantes ($MISSING_DEPS). Installez-les avant de continuer."
fi


# --- Nettoyer l'écran ---
clear
print_banner
# L’opérateur transmis par la GUI ou la chasse est prioritaire.
ACTIVE_USER="${VIGIL_ACTIVE_USER:-$ACTIVE_USER}"
printf '%b%s%b\n' "$BLUE" "$(vigil_text "Projet :" "Project:") $ACTIVE_PROJECT | $(vigil_text "Entité :" "Entity:") $ACTIVE_ENTITY | $(vigil_text "Utilisateur :" "Operator:") $ACTIVE_USER" "$NC"
echo ""

# --- 0. Démontage automatique des périphériques existants dans /investigation ---
echo -e "${YELLOW}$(vigil_text "Démontage automatique des périphériques existants dans /investigation..." "Automatically unmounting existing devices under /investigation...")${NC}"
while IFS= read -r dir; do
    [ -z "$dir" ] && continue
    echo -e "${YELLOW}Démontage de $dir...${NC}"
    sudo umount "$dir" 2>/dev/null && sudo rmdir "$dir" 2>/dev/null && {
        echo -e "${GREEN}✅ $dir démonté et nettoyé.${NC}"
        log_action "auto_umount" "" "$dir" "success" "Démontage automatique avant nouveau montage"
    }
done < <(list_mounts_under_investigation)

# Vérifier qu'aucun périphérique n'est plus monté
REMAINING_MOUNTS=0
while IFS= read -r dir; do
    [ -n "$dir" ] && {
        REMAINING_MOUNTS=$((REMAINING_MOUNTS + 1))
        echo -e "${YELLOW}⚠️  $dir est toujours monté.${NC}"
    }
done < <(list_mounts_under_investigation)

if [ "$REMAINING_MOUNTS" -gt 0 ]; then
    echo -e "${YELLOW}⚠️  Certains périphériques sont encore montés. Nouvelle tentative (lazy umount)...${NC}"
    while IFS= read -r dir; do
        [ -n "$dir" ] && sudo umount -l "$dir" 2>/dev/null || true
    done < <(list_mounts_under_investigation)
    log_action "auto_umount_all" "" "/investigation" "warning" "Démontage lazy appliqué sur restes"
fi

# Nettoyage des dossiers vides résiduels
while IFS= read -r -d '' dir; do
    [ -d "$dir" ] && [ -z "$(ls -A "$dir" 2>/dev/null)" ] && sudo rmdir "$dir" 2>/dev/null
done < <(find /investigation -mindepth 1 -depth -type d -print0 2>/dev/null)

echo -e "${GREEN}✅ $(vigil_text "Nettoyage initial terminé." "Initial cleanup complete.")${NC}"
# --- Triage USB commun ---
TRIAGE_DIR=$(mktemp -d -t "vigil_triage_XXXXXXXX") || exit 1
trap 'rm -rf -- "$TRIAGE_DIR"' EXIT
report_usb_triage() {
    local new_file="$1" hid_file="$2" prot_file="$3" baseline_count="$4"
    local after_count="$5" new_count="$6" protected="$7" blocked="$8" unblockable="$9"
    local USBHID_JSON DATE_ANALYSIS PDF_SCRIPT PDF_OUT
    local busdev port vid pid mfr prod ser first hidflag protflag blflag
    # Rapport PDF de triage (toujours généré : trace de la procedure)
    USBHID_JSON="$TRIAGE_DIR/usbhid.json"
    DATE_ANALYSIS=$(date +"%d/%m/%Y à %H:%M:%S")
    {
        printf '{"date": "%s", "baseline_count": %s, "after_count": %s, "new_count": %s, "hid_count": %s, "protected_count": %s, "blocked_count": %s, "block_fail_count": %s, "blacklisted_count": %s, "devices": [' \
            "$DATE_ANALYSIS" "$baseline_count" "$after_count" "$new_count" "$HID_ALERT_COUNT" "$protected" "$blocked" "$unblockable" "$BL_COUNT"
        first=1
        while IFS='|' read -r busdev port vid pid mfr prod ser; do
            [ -z "$busdev" ] && continue
            [ $first -eq 0 ] && printf ','
            first=0
            hidflag=false
            protflag=false
            blflag=false
            grep -q "^${busdev}|" "$hid_file" 2>/dev/null && hidflag=true
            grep -qxF "$busdev" "$prot_file" 2>/dev/null && protflag=true
            grep -qxF "${vid}:${pid}" "$USB_BLACKLIST_FILE" 2>/dev/null && blflag=true
            { [ -n "$ser" ] && grep -qxF "$ser" "$USB_BLACKLIST_FILE" 2>/dev/null; } && blflag=true
            printf '{"bus_dev": "%s", "vid": "%s", "pid": "%s", "manufacturer": "%s", "product": "%s", "serial": "%s", "hid": %s, "protected": %s, "blacklisted": %s}' \
                "$busdev" "$vid" "$pid" "$mfr" "$prod" "$ser" "$hidflag" "$protflag" "$blflag"
        done < "$new_file"
        printf ']}'
    } > "$USBHID_JSON"
    # Recherche de menaces uniquement : si VIGIL_MOUNT_TRIAGE_JSON_OUT est
    # defini (chemin de collecte de vigil_malware_hunt.sh), le triage est
    # consolide dans le rapport final UNIQUE (pas de PDF usbhid autonome) :
    # le JSON est copie vers le chemin demande pour etre assemble plus tard.
    if [ -n "${VIGIL_MOUNT_TRIAGE_JSON_OUT:-}" ]; then
        if cp -f "$USBHID_JSON" "$VIGIL_MOUNT_TRIAGE_JSON_OUT" 2>/dev/null; then
            echo -e "${GREEN}✅ Triage USB consolidé dans le rapport final (pas de PDF séparé).${NC}"
            log_action "usb_triage_json" "" "$VIGIL_MOUNT_TRIAGE_JSON_OUT" "success" "Triage USB exporté vers le rapport consolidé"
        else
            echo -e "${YELLOW}⚠️  Échec de l'export du triage USB vers le rapport consolidé.${NC}"
            log_action "usb_triage_json" "" "" "warning" "Échec de l'export du JSON de triage"
        fi
    fi
    PDF_SCRIPT="$VIGIL_BASE/scripts/pdf/vigil_pdf.py"
    if [ -z "${VIGIL_MOUNT_TRIAGE_JSON_OUT:-}" ] \
       && [ -f "$PDF_SCRIPT" ] && command -v python3 >/dev/null 2>&1; then
        PDF_OUT=$(python3 "$PDF_SCRIPT" --kind usbhid --json "$USBHID_JSON" \
            --user "$ACTIVE_USER" --project "$ACTIVE_PROJECT" \
            --dir "$VIGIL_BASE/rapports" --config-dir "$VIGIL_DATA_DIR" 2>&1)
        if [ -n "$PDF_OUT" ] && [ -f "$PDF_OUT" ]; then
            echo -e "${GREEN}✅ Rapport de triage USB généré : $PDF_OUT${NC}"
            log_action "usb_triage_pdf" "" "$PDF_OUT" "success" "Rapport de triage USB généré"
            if [ "$ACTIVE_PROJECT" != "(no-project)" ] && [ -d "$PROJECT_LOG_DIR" ] && [ -w "$PROJECT_LOG_DIR" ]; then
                cp -f "$PDF_OUT" "$PROJECT_LOG_DIR/" 2>/dev/null || true
            fi
        else
            echo -e "${YELLOW}⚠️  Échec de la génération du rapport de triage PDF.${NC}"
            log_action "usb_triage_pdf" "" "" "warning" "Échec de la génération du PDF de triage"
        fi
    fi
}

finish_mount_triage() {
    local new_count=$TRIAGE_NEW_COUNT blocked=$TRIAGE_BLOCKED unblockable=$TRIAGE_UNBLOCKABLE
    local _dsk _usb_storage_count
    # Si le SEUL périphérique apparu est un clavier suspect bloqué, il n'y a
    # rien à monter : le rapport PDF de triage vient d'être généré, on
    # termine proprement le script. Garde : si un périphérique de stockage
    # est par ailleurs présent (ex. clé restée branchée pendant la
    # baseline), on continue normalement.
    # Compter les disques de stockage USB en excluant les périphériques
    # bloqués au triage (un ducky peut exposer une partition stockage :
    # elle ne doit pas justifier la poursuite du script). Le port USB de
    # chaque disque est résolu via /sys/block/<nom>.
    _usb_storage_count=0
    while IFS= read -r _dsk; do
        [ -z "$_dsk" ] && continue
        triage_disk_blocked "${_dsk##*/}" && continue
        _usb_storage_count=$((_usb_storage_count + 1))
    done < <(lsblk -rpn -o NAME,TYPE,TRAN,RM 2>/dev/null \
        | awk '$2=="disk" && ($3=="usb" || $4=="1") {print $1}')
    _usb_storage_count=${_usb_storage_count:-0}
    if [ "$HID_ALERT_COUNT" -gt 0 ] \
       && [ "$new_count" -eq "$HID_ALERT_COUNT" ] \
       && [ "$blocked" -gt 0 ] \
       && [ "$unblockable" -eq 0 ] \
       && [ "$_usb_storage_count" -eq 0 ]; then
        echo ""
        echo -e "${RED}${BOLD}🚨 Le seul périphérique détecté est un clavier suspect (bloqué).${NC}"
        echo -e "${RED}Il ne peut pas être monté ni analysé : débranchez-le et jugez ${NC}"
        echo -e "${RED}s'il s'agit d'un clavier de travail (relancez alors le script).${NC}"
        if [ -n "${VIGIL_MOUNT_TRIAGE_JSON_OUT:-}" ]; then
            echo -e "${GREEN}Le triage est consolidé dans le rapport final (recherche de menaces).${NC}"
        else
            echo -e "${GREEN}Le rapport PDF de triage a été généré (rapport_usbhid_*).${NC}"
        fi
        log_action "usb_triage_end" "" "$after_file" "alert" "Fin du montage : seul périphérique détecté = clavier suspect bloqué"
        END_AFTER_TRIAGE=1
        return 0
    fi
    # Même logique pour un périphérique BLACKLISTÉ : bloqué (authorized=0),
    # il n'apparaît plus dans lsblk — rien à monter ni analyser.
    if [ "$BL_COUNT" -gt 0 ] \
       && [ "$new_count" -eq "$BL_COUNT" ] \
       && [ "$_usb_storage_count" -eq 0 ]; then
        echo ""
        echo -e "${RED}${BOLD}🚨 Le seul périphérique détecté est BLACKLISTÉ (bloqué).${NC}"
        echo -e "${RED}Il ne peut pas être monté ni analysé. Pour l'autoriser à nouveau,${NC}"
        echo -e "${RED}retirez-le de la blacklist (Accueil > Configuration > Périphériques USB).${NC}"
        if [ -n "${VIGIL_MOUNT_TRIAGE_JSON_OUT:-}" ]; then
            echo -e "${GREEN}Le triage est consolidé dans le rapport final (recherche de menaces).${NC}"
        else
            echo -e "${GREEN}Le rapport PDF de triage a été généré (rapport_usbhid_*).${NC}"
        fi
        log_action "usb_triage_end" "" "$after_file" "alert" "Fin du montage : seul périphérique détecté = blacklisté bloqué"
        END_AFTER_TRIAGE=1
        return 0
    fi
}

END_AFTER_TRIAGE=0
if ! run_usb_triage; then
    echo -e "${YELLOW}$(vigil_text "Annulé." "Cancelled.")${NC}"
    exit 0
fi
finish_mount_triage
if [ "$END_AFTER_TRIAGE" -eq 1 ]; then
    final_pause
    exit 0
fi


# --- 1. Sélection du type de périphérique ---
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Sélection du type de périphérique          ${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREY}$(vigil_text "Quel type de périphérique souhaitez-vous analyser ?" "Which device type do you want to examine?")${NC}"
echo ""
echo -e "  ${BOLD}${BLUE}[1]${NC}  ${BOLD}Smartphone${NC}  ${GREY}(MTP/PTP)${NC}"
echo -e "  ${BOLD}${BLUE}[2]${NC}  ${BOLD}Périphérique de stockage USB${NC}  ${GREY}(clé, disque dur, etc.)${NC}"
echo -e "  ${BOLD}${BLUE}[3]${NC}  ${BOLD}Autre${NC}  ${GREY}(scanner tous les types de périphériques)${NC}"
echo ""
echo -e "  ${BOLD}${BLUE}[q]${NC}  ${BOLD}Quitter${NC}"
echo ""
echo -ne "${BOLD}${YELLOW}Entrez votre choix (1-3, q pour quitter) : ${NC}"
read -r DEVICE_TYPE_CHOICE

case "$DEVICE_TYPE_CHOICE" in
    1)
        DEVICE_MODE="smartphone"
        echo -e "${GREEN}Mode : Détection des smartphones (MTP/PTP)${NC}"
        log_action "device_type_selection" "" "" "success" "Type : Smartphone (MTP/PTP)"
        ;;
    2)
        DEVICE_MODE="usb_storage"
        echo -e "${GREEN}Mode : Périphériques de stockage USB uniquement${NC}"
        log_action "device_type_selection" "" "" "success" "Type : Stockage USB"
        ;;
    3)
        DEVICE_MODE="all"
        echo -e "${GREEN}Mode : Détection de tous les types de périphériques${NC}"
        log_action "device_type_selection" "" "" "success" "Type : Tous"
        ;;
    q|Q)
        echo -e "${YELLOW}$(vigil_text "Annulé." "Cancelled.")${NC}"
        log_action "device_type_selection" "" "" "success" "Quitter à la sélection du type de périphérique"
        final_pause
        exit 0
        ;;
    *)
        fail "Choix invalide : $DEVICE_TYPE_CHOICE"
        ;;
esac

# --- Nouvel écran avec ASCII art avant la sélection du périphérique ---
# Banniere en ROUGE si un périphérique suspect a été détecté au triage,
# bleu sinon. Le résumé du contrôle est rappelé pour les non-techniciens.
clear
if [ "$HID_ALERT_COUNT" -gt 0 ]; then
    print_banner
    echo -e "${RED}${BOLD}  ⚠ ATTENTION : $HID_ALERT_COUNT périphérique(s) suspect(s) détecté(s)${NC}"
    echo -e "${RED}  Un périphérique se fait passer pour un clavier : ses frappes sont${NC}"
    echo -e "${RED}  bloquées et il ne peut PAS être monté. Voir le rapport PDF de triage.${NC}"
    echo ""
elif [ "$HID_PROTECTED_COUNT" -gt 0 ]; then
    print_banner
    echo -e "${GREEN}${BOLD}  Contrôle USB terminé : $HID_PROTECTED_COUNT périphérique(s) protégé(s) par vos soins${NC}"
    echo -e "${GREEN}  (clavier/souris de travail) — ils fonctionnent normalement.${NC}"
    echo ""
else
    print_banner
    echo -e "${GREEN}  ✅ Contrôle USB terminé : aucun périphérique suspect détecté.${NC}"
    echo ""
fi

# --- 1.5. Autorisation des périphériques USB bloqués (authorized=0) ---
# usbguard a été purgé du système mais les périphériques branchés pendant
# qu'il tournait (ou juste branchés) restent bloqués au niveau noyau
# (authorized=0), invisibles dans lsblk. Cette fonction autorise tous les
# périphériques USB bloqués et attend que le noyau les enregistre.
authorize_blocked_usb() {
    if [ ! -d /sys/bus/usb/devices ]; then
        return 0
    fi
    local found=0
    local authfile devpath state prod mfr
    for authfile in /sys/bus/usb/devices/*/authorized; do
        [ -f "$authfile" ] || continue
        state=$(cat "$authfile" 2>/dev/null || echo "")
        if [ "$state" = "0" ]; then
            devpath="${authfile%/authorized}"
            triage_port_blocked "${devpath##*/}" && continue
            usb_is_listed "$devpath" "$USB_BLACKLIST_FILE" && continue
            if [ "$found" -eq 0 ]; then
                echo -e "${YELLOW}Réparation des périphériques USB bloqués (authorized=0)...${NC}"
            fi
            found=1
            prod=$(cat "$devpath/product" 2>/dev/null || echo "?")
            mfr=$(cat "$devpath/manufacturer" 2>/dev/null || echo "?")
            if echo 1 | sudo tee "$authfile" >/dev/null 2>&1; then
                echo -e "  ${GREEN}✅ Autorisé :${NC} ${GREY}${mfr} / ${prod}${NC}"
            else
                echo -e "  ${RED}❌ Échec d'autorisation :${NC} ${GREY}${mfr} / ${prod}${NC}"
            fi
        fi
    done
    if [ "$found" -eq 1 ]; then
        echo -e "${YELLOW}    Attente de la reconnaissance par le noyau...${NC}"
        udevadm settle --timeout=10 2>/dev/null || sleep 2
        sleep 1
    fi
    return $found
}

# --- 2. Détection des périphériques selon le mode sélectionné ---

# --- 2.1. Détection des DVD/CD-ROM (uniquement en mode "Autre") ---
if [ "$DEVICE_MODE" = "all" ] && [ -e /dev/cdrom ]; then
    echo -e "${YELLOW}Recherche de lecteurs CD-ROM...${NC}"
    if command -v eject >/dev/null 2>&1 && eject -t /dev/cdrom 2>/dev/null; then
        sleep 2
        sudo mkdir -p /investigation/cdrom 2>/dev/null || true
        if mount /dev/cdrom /investigation/cdrom -o ro,noexec,nosuid,nodev,noatime 2>/dev/null; then
            echo -e "${GREEN}✅ Média optique monté dans /investigation/cdrom${NC}"
            log_action "mount" "/dev/cdrom" "/investigation/cdrom" "success" "Média optique monté en lecture seule"
            echo -e "\n${GREEN}✅ Montage terminé sans erreur.${NC}"
            exit 0
        else
            echo -e "${YELLOW}⚠️  Aucun média optique détecté ou échec du montage.${NC}"
            log_action "mount_attempt" "/dev/cdrom" "/investigation/cdrom" "warning" "Échec du montage du média optique"
            sudo rmdir /investigation/cdrom 2>/dev/null || true
        fi
    fi
fi

# --- 2.2. Détection des périphériques MTP (Smartphone ou Autre) ---
if [ "$DEVICE_MODE" = "smartphone" ] || [ "$DEVICE_MODE" = "all" ]; then
    if command -v jmtpfs >/dev/null 2>&1; then
        echo -e "${YELLOW}Recherche de périphériques MTP...${NC}"
        MTP_DEVICES=$(jmtpfs -l 2>/dev/null | grep -E "^Device [0-9]+" || true)
        if [ -n "$MTP_DEVICES" ]; then
            echo -e "${GREEN}✅ Périphérique MTP détecté :${NC}"
            echo "$MTP_DEVICES" | while IFS= read -r line; do
                echo -e "   ${line}"
            done
            sudo mkdir -p /investigation/mtp 2>/dev/null || true
            if sudo jmtpfs /investigation/mtp -o ro 2>/dev/null; then
                echo -e "${GREEN}✅ Périphérique MTP monté dans /investigation/mtp${NC}"
                log_action "mount" "MTP" "/investigation/mtp" "success" "Périphérique MTP monté en lecture seule"
                echo -e "\n${GREEN}✅ Montage terminé sans erreur.${NC}"
                exit 0
            else
                echo -e "${YELLOW}⚠️  Échec du montage MTP.${NC}"
                log_action "mount_attempt" "MTP" "/investigation/mtp" "failed" "Échec du montage MTP"
                sudo rmdir /investigation/mtp 2>/dev/null || true
            fi
        else
            echo -e "${YELLOW}⚠️  Aucun périphérique MTP détecté.${NC}"
            log_action "mount_attempt" "MTP" "" "warning" "Aucun périphérique MTP détecté"
        fi
    else
        echo -e "${YELLOW}⚠️  jmtpfs non installé. Impossible de détecter les périphériques MTP.${NC}"
        log_action "mount_attempt" "MTP" "" "warning" "jmtpfs non disponible"
    fi
fi

# --- 2.3. Détection des périphériques USB (Stockage USB ou Autre) ---
# Détection robuste avec retry automatique : on tente la détection, et si rien
# n'est trouvé on autorise les périphériques USB bloqués (authorized=0) puis
# on réessaie, jusqu'à 3 passes. On détecte les partitions ET les disques USB
# sans partition (filesystem direct sur le disque, ex. /dev/sdb sans table).
detect_usb_devices() {
    declare -gA USB_DEVICES=() PARENT_MODEL=() PARENT_SIZE=() DEVICE_ACCESS=()
    declare -gA DISK_PARTS=() DISK_PARTCOUNT=()
    local -a raw_disks=()
    DEVICE_NUM=0
    MOUNTED_NUM=0
    MOUNTED_USB=()

    local record kind name size model fs label parttype parent inventory i disk e
    inventory=$(/usr/bin/python3 -I "$(dirname -- "${BASH_SOURCE[0]}")/../lib/vigil_block_inventory.py") || return 1
    while IFS= read -r record; do
        IFS='|' read -r kind name size model fs label parttype parent <<< "$record"
        case "$kind" in
            parent)
                PARENT_SIZE["$name"]="$size"
                PARENT_MODEL["$name"]="$model"
                DEVICE_ACCESS["$name"]="$fs"
                ;;
            access) DEVICE_ACCESS["$name"]="$size" ;;
            mounted)
                MOUNTED_USB[$MOUNTED_NUM]="${record#*|}"
                MOUNTED_NUM=$((MOUNTED_NUM + 1))
                ;;
            part)
                triage_disk_blocked "$parent" && continue
                USB_DEVICES[$DEVICE_NUM]="$record"
                DEVICE_NUM=$((DEVICE_NUM + 1))
                DISK_PARTS["$parent"]="${DISK_PARTS["$parent"]:-}$name "
                DISK_PARTCOUNT["$parent"]=$((${DISK_PARTCOUNT["$parent"]:-0} + 1))
                ;;
            rawdisk)
                triage_disk_blocked "$name" || raw_disks+=("$record")
                ;;
        esac
    done <<< "$inventory"

    # 2bis. Insertion d'une entrée « Monter tout le disque » pour chaque disque
    # USB possédant au moins 2 partitions montables. L'entrée est préfixée
    # « whole » et porte le nom du disque parent ; le montage itérera sur ses
    # partitions (DISK_PARTS). On insère ces entrées EN TÊTE de la liste afin
    # qu'elles apparaissent avant les partitions individuelles à l'affichage.
    if [ "${#DISK_PARTS[@]}" -gt 0 ]; then
        local _new_list=()
        for i in "${!USB_DEVICES[@]}"; do _new_list+=("${USB_DEVICES[$i]}"); done
        local _inserted=()
        for disk in "${!DISK_PARTS[@]}"; do
            local cnt=${DISK_PARTCOUNT["$disk"]:-0}
            if [ "$cnt" -ge 2 ]; then
                local dsize=${PARENT_SIZE["$disk"]:-?}
                local dmodel=${PARENT_MODEL["$disk"]:-?}
                _inserted+=("whole|$disk|$dsize|$dmodel|$cnt|")
            fi
        done
        # Reconstruire USB_DEVICES : entrées whole d'abord, puis partitions
        USB_DEVICES=()
        DEVICE_NUM=0
        for e in "${_inserted[@]}"; do
            USB_DEVICES[$DEVICE_NUM]="$e"
            DEVICE_NUM=$((DEVICE_NUM + 1))
        done
        for e in "${_new_list[@]}"; do
            USB_DEVICES[$DEVICE_NUM]="$e"
            DEVICE_NUM=$((DEVICE_NUM + 1))
        done
    fi

    for record in "${raw_disks[@]}"; do
        USB_DEVICES[$DEVICE_NUM]="$record"
        DEVICE_NUM=$((DEVICE_NUM + 1))
    done
}

if [ "$DEVICE_MODE" = "usb_storage" ] || [ "$DEVICE_MODE" = "all" ]; then
    echo -e "${YELLOW}Recherche des périphériques USB/Disques...${NC}"

    # Boucle de retry : jusqu'à 3 passes. À chaque passe on tente la détection ;
    # si rien n'est trouvé on autorise les USB bloqués puis on réessaie.
    ATTEMPT=0
    MAX_ATTEMPTS=3
    while [ "$ATTEMPT" -lt "$MAX_ATTEMPTS" ]; do
        ATTEMPT=$((ATTEMPT + 1))
        detect_usb_devices || fail "Impossible de relever les périphériques de stockage."
        if [ "$DEVICE_NUM" -gt 0 ]; then
            break
        fi
        if [ "$ATTEMPT" -lt "$MAX_ATTEMPTS" ]; then
            echo -e "${GREY}    (tentative $ATTEMPT/$MAX_ATTEMPTS : aucun périphérique, vérification des USB bloqués...)${NC}"
            authorize_blocked_usb
        fi
    done

    if [ "$DEVICE_NUM" -eq 0 ]; then
        echo -e "${RED}❌ Aucun périphérique USB/Disque non monté détecté.${NC}"
        # Cas fréquent : un périphérique USB est déjà monté ailleurs
        # (ex. dans /stockage via le montage de stockage). On le signale et
        # on propose de le démonter pour pouvoir l'analyser en lecture seule.
        if [ "$MOUNTED_NUM" -gt 0 ] && [ "${VIGIL_CASE_CENSUS:-0}" != "1" ]; then
            echo ""
            echo -e "${YELLOW}⚠️  ${MOUNTED_NUM} périphérique(s) USB déjà monté(s) :${NC}"
            for i in "${!MOUNTED_USB[@]}"; do
                IFS='|' read -r m_name m_mount m_size m_model <<< "${MOUNTED_USB[$i]}"
                echo -e "  ${BOLD}/dev/$m_name${NC}  ${GREY}• Monté dans :${NC} ${BOLD}$m_mount${NC}  ${GREY}• Taille :${NC} ${BOLD}$m_size${NC}"
            done
            echo ""
            echo -ne "${BOLD}${YELLOW}$(vigil_text "Démonter ces périphériques et relancer la détection ? (o/n, q pour quitter) :" "Unmount these devices and rescan? (o=yes, n=no, q=quit):") ${NC}"
            read -r UM_ANSWER
            if [ "$UM_ANSWER" = "q" ] || [ "$UM_ANSWER" = "Q" ]; then
                echo -e "${YELLOW}Quitter.${NC}"
                final_pause
                exit 0
            fi
            if [ "$UM_ANSWER" = "o" ] || [ "$UM_ANSWER" = "O" ] || [ "$UM_ANSWER" = "y" ] || [ "$UM_ANSWER" = "Y" ]; then
                for i in "${!MOUNTED_USB[@]}"; do
                    IFS='|' read -r m_name m_mount m_size m_model <<< "${MOUNTED_USB[$i]}"
                    echo -e "${YELLOW}Démontage de /dev/$m_name ($m_mount)...${NC}"
                    if sudo umount "$m_mount" 2>/dev/null; then
                        echo -e "  ${GREEN}✅ /dev/$m_name démonté.${NC}"
                        log_action "umount_for_ro" "/dev/$m_name" "$m_mount" "success" "Démonté pour analyse RO"
                    else
                        echo -e "  ${RED}❌ Échec du démontage de /dev/$m_name.${NC}"
                    fi
                done
                # Replacer le disque en read-only après démontage
                for i in "${!MOUNTED_USB[@]}"; do
                    IFS='|' read -r m_name m_mount m_size m_model <<< "${MOUNTED_USB[$i]}"
                    sudo blockdev --setro "/dev/$m_name" 2>/dev/null || true
                done
                sleep 1
                # Relancer la détection une dernière fois
                detect_usb_devices || fail "Impossible de relever les périphériques de stockage."
            fi
        fi
        if [ "$DEVICE_NUM" -eq 0 ]; then
            echo ""
            echo -e "${YELLOW}Diagnostic : si votre clé USB est branchée mais invisible dans lsblk :${NC}"
            echo -e "${GREY}  • Vérifiez : lsblk (la clé doit apparaître, ex. /dev/sdb)${NC}"
            echo -e "${GREY}  • Vérifiez : sudo dmesg | tail -20 (cherchez 'authorized' ou 'not authorized')${NC}"
            echo -e "${GREY}  • Vérifiez : systemctl is-enabled usbguard (doit être disabled/masked)${NC}"
            echo -e "${GREY}  • Débranchez puis rebranchez physiquement la clé${NC}"
            log_action "mount_attempt" "" "/investigation" "failed" "Aucun périphérique détecté"
            if [ "$DEVICE_MODE" = "usb_storage" ]; then
                final_pause
                exit 1
            fi
        fi
    fi
fi

    _case_lock_block_ro() {
        local dev="$1"
        if ! sudo blockdev --setro "$dev" ||
           [ "$(sudo blockdev --getro "$dev")" != "1" ]; then
            echo "Montage refusé : lecture seule au niveau bloc non confirmée pour $dev."
            log_action "set_ro" "$dev" "" "failed" "Protection bloc RO non confirmée"
            return 1
        fi
        echo "Lecture seule au niveau bloc confirmée : $dev"
        log_action "set_ro" "$dev" "" "success" "Protection bloc RO confirmée"
    }

    _case_lock_disk_ro() {
        local disk="$1" mountpoints
        if [ "$(lsblk -dnro TYPE -- "$disk")" != "disk" ] ||
           ! mountpoints=$(lsblk -nr -o MOUNTPOINTS -- "$disk") ||
           [[ "$mountpoints" =~ [^[:space:]] ]]; then
            echo "Montage refusé : disque $disk déjà utilisé ou absence de montage non vérifiable."
            log_action "set_ro" "$disk" "" "failed" "Disque parent non vérifié ou déjà monté"
            return 1
        fi
        _case_lock_block_ro "$disk"
    }

    # --- Helper : montage lecture seule d'un device dans un point de montage ---
    # Renvoie 0 si OK, 1 si échec. Affiche le détail et log la custody.
    _mount_single_ro() {
        local dev="$1" mnt="$2"
        local fstype mount_opts ro_check

        sudo mkdir -p "$mnt" 2>/dev/null || {
            echo -e "${RED}❌ Impossible de créer le point de montage $mnt.${NC}"
            log_action "mkdir_mountpoint" "$dev" "$mnt" "failed" "Échec de la création du répertoire"
            return 1
        }

        if [ "${VIGIL_CASE_CENSUS:-0}" = "1" ]; then
            _case_lock_block_ro "$dev" || {
                sudo rmdir "$mnt" 2>/dev/null || true
                return 1
            }
        elif command -v blockdev >/dev/null 2>&1; then
            sudo blockdev --setro "$dev" 2>/dev/null || true
        fi

        fstype=$(lsblk -no FSTYPE "$dev" 2>/dev/null || echo "")
        mount_opts="-o ro,noexec,nosuid,nodev,noatime"
        case "$fstype" in
            fat32|vfat) mount_opts="$mount_opts,utf8=true" ;;
            ext3|ext4)  mount_opts="$mount_opts,noload" ;;
            ufs)        mount_opts="$mount_opts,ufstype=ufs2" ;;
            iso9660)    mount_opts="$mount_opts,unhide" ;;
            btrfs)      mount_opts="$mount_opts,subvolid=0" ;;
        esac

        local mount_rc=0
        if [ "${VIGIL_CASE_CENSUS:-0}" = "1" ]; then
            sudo mount $mount_opts "$dev" "$mnt" || mount_rc=$?
        else
            sudo mount $mount_opts "$dev" "$mnt" 2>/dev/null || mount_rc=$?
        fi
        if [ "$mount_rc" -ne 0 ]; then
            echo -e "${RED}❌ Échec du montage de $dev → $mnt${NC}"
            if [ "${VIGIL_CASE_CENSUS:-0}" != "1" ]; then
                sudo mount $mount_opts "$dev" "$mnt" 2>&1 || true
            fi
            log_action "mount" "$dev" "$mnt" "failed" "Échec du montage"
            sudo rmdir "$mnt" 2>/dev/null || true
            return 1
        fi

        ro_check=$(lsblk -o RO "$dev" 2>/dev/null | tail -n 1 | awk '{print $1}' || echo "")
        if [ "$ro_check" != "1" ]; then
            echo -e "${RED}❌ $dev n'est pas monté en lecture seule !${NC}"
            sudo umount "$mnt" 2>/dev/null || true
            sudo rmdir "$mnt" 2>/dev/null || true
            if [ "${VIGIL_CASE_CENSUS:-0}" != "1" ]; then
                command -v blockdev >/dev/null 2>&1 && sudo blockdev --setrw "$dev" 2>/dev/null || true
            fi
            log_action "mount" "$dev" "$mnt" "failed" "Périphérique non monté en lecture seule"
            return 1
        fi

        echo -e "${GREEN}✅ ${NC}${BOLD}$dev${NC}${GREEN} → $mnt${NC}"
        log_action "mount" "$dev" "$mnt" "success" "Périphérique monté en lecture seule"
        return 0
    }

    # --- Helper : vérification chiffrement LUKS/BitLocker sur un device ---
    _is_encrypted() {
        local dev="$1"
        if command -v cryptsetup >/dev/null 2>&1 && cryptsetup isLuks "$dev" 2>/dev/null; then
            echo "LUKS"
            return 0
        fi
        local sig sig_b64
        local bitlocker_signatures=("61iQLUZWRS1GUy0=" "61KQLUZWRS1GUy0=" "61iQTVNXSU40LjE=")
        sig_b64=$(dd if="$dev" bs=11 count=1 status=none 2>/dev/null | base64 || true)
        for sig in "${bitlocker_signatures[@]}"; do
            if [ "$sig_b64" = "$sig" ]; then
                echo "BitLocker"
                return 0
            fi
        done
        echo ""
        return 1
    }

    # --- Helper : calcul du hash SHA-256 d'un point de montage ---
    _compute_hash() {
        local dev="$1" mnt="$2" tag="$3"
        if [ "${VIGIL_CASE_INTEGRITY:-}" = "1" ]; then
            local result
            if result=$(python3 "$VIGIL_BASE/scripts/analyse/vigil_mount_integrity.py" record "$mnt" "$PROJECT_LOG_DIR" 2>&1); then
                echo "$result"
                log_action "hash_calculation" "$dev" "$mnt" "success" "$result"
            else
                echo "$result" >&2
                log_action "hash_calculation" "$dev" "$mnt" "warning" "$result"
            fi
            return 0
        fi
        local hash_file
        hash_file="$PROJECT_LOG_DIR/device_${tag}.sha256"
        sudo rm -f "$hash_file"
        if [ -n "$(ls -A "$mnt" 2>/dev/null)" ]; then
            find "$mnt" -type f -exec sha256sum {} + 2>/dev/null | sort | sha256sum | awk '{print $1}' > "$hash_file" || true
            echo -e "${GREEN}✅ Hash SHA-256 ($tag) :${NC} $(cat "$hash_file" 2>/dev/null)  ${GREY}→ $hash_file${NC}"
            log_action "hash_calculation" "$dev" "$hash_file" "success" "Hash SHA-256 calculé ($tag) : $(cat "$hash_file" 2>/dev/null) — arbre complet des fichiers (find+sha256sum+sort)"
        else
            echo -e "${YELLOW}⚠️  $mnt est vide, aucun hash généré ($tag).${NC}"
            log_action "hash_calculation" "$dev" "" "warning" "$mnt est vide ($tag)"
        fi
    }

    if [ "$DEVICE_NUM" -gt 0 ]; then
    # --- Affichage des peripheriques (regroupe par disque, reutilise par 'r') ---
        # Le montage utilise le même menu et sait relancer sa détection.
        while true; do
            echo -e "${GREEN}✅ $DEVICE_NUM périphérique(s) détecté(s) :${NC}"
            display_usb_devices
            select_usb_device "à monter" && break
            case $? in
                2)
                    detect_usb_devices || fail "Impossible de relever les périphériques de stockage."
                    if [ "$DEVICE_NUM" -eq 0 ]; then
                        authorize_blocked_usb
                        detect_usb_devices || fail "Impossible de relever les périphériques de stockage."
                    fi
                    ;;
                *)
                    log_action "mount_cancelled" "" "/investigation" "success" "Montage annulé par l'utilisateur"
                    final_pause
                    exit 0
                    ;;
            esac
        done
        IFS='|' read -r SELECTED_KIND SELECTED_DEVICE SELECTED_SIZE SELECTED_MODEL SELECTED_FSTYPE SELECTED_LABEL SELECTED_PARTTYPE SELECTED_PKNAME <<< "${USB_DEVICES[$SELECTED_INDEX]}"

        if triage_disk_blocked "${SELECTED_PKNAME:-$SELECTED_DEVICE}"; then
            fail "Montage refusé : périphérique exclu du triage."
        fi

        # --- 5/6. Montage selon le kind d'entrée sélectionnée ---
        echo -e "\n${YELLOW}Montage en lecture seule...${NC}"

        if [ "$SELECTED_KIND" = "whole" ]; then
            # Monter toutes les partitions du disque sous /investigation/<disk>/<part>
            echo -e "${YELLOW}Montage de toutes les partitions de /dev/$SELECTED_DEVICE...${NC}"
            if [ "${VIGIL_CASE_CENSUS:-0}" = "1" ]; then
                _case_lock_disk_ro "/dev/$SELECTED_DEVICE" || exit 1
            elif command -v blockdev >/dev/null 2>&1; then
                if sudo blockdev --setro "/dev/$SELECTED_DEVICE" 2>/dev/null; then
                    echo -e "${GREEN}✅ Mode RO forcé au niveau block device (/dev/$SELECTED_DEVICE).${NC}"
                    log_action "set_ro" "/dev/$SELECTED_DEVICE" "" "success" "Mode RO forcé au niveau block device"
                else
                    echo -e "${YELLOW}⚠️  blockdev --setro a échoué. Poursuite avec montage read-only standard.${NC}"
                    log_action "set_ro" "/dev/$SELECTED_DEVICE" "" "warning" "blockdev --setro a échoué (non bloquant)"
                fi
            fi

            _ok=0; _fail=0
            _parts="${DISK_PARTS["$SELECTED_DEVICE"]:-}"
            for _part in $_parts; do
                _dev="/dev/$_part"; _mnt="/investigation/$SELECTED_DEVICE/$_part"
                _enc=$(_is_encrypted "$_dev")
                if [ -n "$_enc" ]; then
                    echo -e "${RED}❌ $_dev est chiffré ($_enc). Ignoré.${NC}"
                    log_action "mount_attempt" "$_dev" "$_mnt" "failed" "Partition chiffrée ($_enc)"
                    _fail=$((_fail + 1))
                    continue
                fi
                if _mount_single_ro "$_dev" "$_mnt"; then
                    _ok=$((_ok + 1))
                    if [ "${VIGIL_CASE_INTEGRITY:-}" = "1" ]; then
                        _compute_hash "$_dev" "$_mnt" "$_part"
                    fi
                else
                    _fail=$((_fail + 1))
                fi
            done

            echo ""
            echo -e "${GREEN}✅ $_ok partition(s) montée(s), $_fail échec(s) sous /investigation/$SELECTED_DEVICE/${NC}"
            log_action "mount_whole" "/dev/$SELECTED_DEVICE" "/investigation/$SELECTED_DEVICE" "success" "$_ok partition(s) montée(s), $_fail échec(s)"

            if [ "${VIGIL_CASE_CENSUS:-0}" = "1" ] && [ "$_ok" -eq 0 ]; then
                exit 1
            fi

            # Hash global du disque (union de toutes les partitions montées)
            if [ "${VIGIL_CASE_INTEGRITY:-}" != "1" ]; then
                _compute_hash "/dev/$SELECTED_DEVICE" "/investigation/$SELECTED_DEVICE" "$SELECTED_DEVICE"
            fi

        else
            # Montage d'un device unique (partition ou disque sans table)
            DEVICE_PATH="/dev/$SELECTED_DEVICE"
            _enc=$(_is_encrypted "$DEVICE_PATH")
            if [ -n "$_enc" ]; then
                echo -e "${RED}❌ Ce périphérique est chiffré ($_enc).${NC}"
                echo -e "${YELLOW}Utilisez un outil de déchiffrement avant de continuer.${NC}"
                log_action "mount_attempt" "$DEVICE_PATH" "/investigation" "failed" "Périphérique chiffré ($_enc)"
                final_pause
                exit 1
            fi

            MOUNT_POINT="/investigation/$SELECTED_DEVICE"
            echo -e "${YELLOW}Montage de ${GREEN}$DEVICE_PATH${YELLOW} dans $MOUNT_POINT...${NC}"

            if [ "${VIGIL_CASE_CENSUS:-0}" = "1" ]; then
                _disk="$DEVICE_PATH"
                if [ "$SELECTED_KIND" = "part" ]; then
                    _parent=$(lsblk -dnro PKNAME -- "$DEVICE_PATH")
                    if [ -z "$_parent" ] || [ "$_parent" != "$SELECTED_PKNAME" ]; then
                        echo "Montage refusé : disque parent non confirmé pour $DEVICE_PATH."
                        exit 1
                    fi
                    _disk="/dev/$_parent"
                fi
                _case_lock_disk_ro "$_disk" || exit 1
            elif command -v blockdev >/dev/null 2>&1; then
                if sudo blockdev --setro "$DEVICE_PATH" 2>/dev/null; then
                    echo -e "${GREEN}✅ Mode RO forcé au niveau block device.${NC}"
                    log_action "set_ro" "$DEVICE_PATH" "" "success" "Mode RO forcé au niveau block device"
                else
                    echo -e "${YELLOW}⚠️  blockdev --setro a échoué. Poursuite avec montage read-only standard.${NC}"
                    log_action "set_ro" "$DEVICE_PATH" "" "warning" "blockdev --setro a échoué (non bloquant)"
                fi
            else
                echo -e "${YELLOW}⚠️  blockdev non disponible. Montage read-only standard uniquement.${NC}"
            fi

            if ! _mount_single_ro "$DEVICE_PATH" "$MOUNT_POINT"; then
                final_pause
                exit 1
            fi

            _compute_hash "$DEVICE_PATH" "$MOUNT_POINT" "$SELECTED_DEVICE"
        fi

        # --- 8. Pause avant de quitter ---
        final_pause
        exit 0
    fi

echo -e "\n${GREEN}Script terminé.${NC}"
final_pause
