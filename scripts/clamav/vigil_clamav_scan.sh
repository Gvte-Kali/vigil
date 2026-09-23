#!/bin/bash
set -uo pipefail

# --- Scan antivirus ClamAV sur un ou plusieurs dossiers de /investigation/ ---
#
# Inspire de scalpel/bin/clamav (selection interactive + scan recursif) et
# scalpel/bin/clamscan (enveloppe colorisee de clamscan).
#
# Fonctionnalites :
#   - liste les dossiers montes dans /investigation/
#   - permet de scanner un dossier, plusieurs dossiers, ou tous
#   - colorise la sortie (fichiers infectes, erreurs, avertissements)
#   - enregistre un rapport par dossier scanne dans $VIGIL_BASE/rapports/
#     (le scan AV ne necessite pas de projet actif ni de chaine de custody)
#   - ne ferme jamais le terminal en cas d'erreur sans avoir affiche un
#     resume et attendu la frappe de l'utilisateur
#
# Usage : vigil_clamav_scan.sh [--pdf|--no-pdf] [--all] [--comment TXT] [--yes] [--user NOM] [--archives|--no-archives] [--json-out DIR]
#   --all        : scanner tous les dossiers (mode non-interactif)
#   --comment TXT : commentaire du scan (non-interactif)
#   --yes        : répondre oui aux confirmations (non-interactif)
#   --user NOM   : utilisateur effectuant le scan (écrase l'utilisateur actif)
#   --archives / --no-archives : le scan du contenu des archives (zip, tar,
#                  7z, rar...) est FORCÉ par défaut : clamscan extrait chaque
#                  fichier interne en mémoire et le scanne individuellement
#                  avec les signatures. --no-archives transmet --scan-archive=no
#                  pour aller plus vite sur de gros volumes sans archives
#                  (override CLI uniquement, plus de question interactive).
#   --size-unlimited / --size-limit : mode de taille des fichiers. clamscan
#                  saute par défaut les fichiers de plus de 25 Mo
#                  (--max-filesize) et limite le contenu des archives à
#                  100 Mo (--max-scansize). --size-unlimited (défaut) lève
#                  ces limites jusqu'au plafond réel de ClamAV : 2 GiB - 1
#                  (2147483647 octets), soit 2047 Mo. --size-limit applique
#                  une limite raisonnable (512 Mo par fichier) pour accélérer
#                  le scan sans sauter le contenu des archives. En mode
#                  interactif sans flag explicite, la question est posée
#                  juste après la sélection des dossiers.
#   --alert-encrypted / --no-alert-encrypted : le signalement des archives
#                  chiffrées (mot de passe) est FORCÉ par défaut. clamscan
#                  ne peut pas ouvrir une archive chiffrée : sans
#                  --alert-encrypted, elle est ignorée EN SILENCE (aucune
#                  menace remontée, aucun avertissement). Avec l'alerte, elle
#                  est signalée comme 'Heuristics.Encrypted.Zip' (ou .Rar,
#                  .7z...) : le rapport indique clairement qu'elle n'a pas
#                  pu être analysée. En forensique, ne pas savoir qu'une
#                  archive a échappé au scan est pire qu'une fausse alerte.
#                  --no-alert-encrypted est un override CLI uniquement, plus
#                  de question interactive.

# --- Couleurs ---
RED='\e[91m'
GREEN='\e[92m'
YELLOW='\e[93m'
BLUE='\e[96m'
ORANGE='\e[33m'
GREY='\e[90m'
BOLD='\e[1m'
NC='\e[0m'

print_banner() {
    echo -e "${BLUE}"
    cat <<'VIGILART'
█   █ ███  ███  ███ █     
█   █  █  █      █  █     
█   █  █  █  ██  █  █     
 █ █   █  █   █  █  █     
  █   ███  ███  ███ █████ 
VIGILART
    echo -e "${NC}"
}

print_options_table() {
    local arch_label size_label enc_label
    if [ "$SCAN_ARCHIVES" = "1" ]; then arch_label="contenu scanné"; else arch_label="non ouvertes"; fi
    if [ "$SIZE_MODE" = "unlimited" ]; then size_label="illimitée (2047 Mo max)"; else size_label="limitée (512 Mo max)"; fi
    if [ "$ALERT_ENC" = "1" ]; then enc_label="signalées"; else enc_label="ignorées"; fi
    echo -e "${BOLD}  Options du scan${NC}"
    echo -e "${GREY}  ---------------------------------${NC}"
    echo -e "  Utilisateur      : ${BOLD}${ACTIVE_USER:-$(echo '(no-user)')}${NC}"
    echo -e "  Archives         : ${BOLD}${arch_label}${NC}"
    echo -e "  Taille max       : ${BOLD}${size_label}${NC}"
    echo -e "  Chiffrées        : ${BOLD}${enc_label}${NC}"
    echo -e "  Journal clamscan : ${BOLD}$([ "$GEN_LOG" -eq 1 ] && echo "conservé" || echo "non conservé")${NC}"
    echo -e "  Rapport PDF      : ${BOLD}$([ "$GEN_PDF" -eq 1 ] && echo "généré" || echo "non généré")${NC}"
    echo ""
}

ERRORS=0
INFECTED_TOTAL=0
SCANNED_DIRS=()

# --- Vérifier qu'un utilisateur (obligatoire) et un projet sont actifs ---
VIGIL_BASE="${VIGIL_BASE:-/opt/vigil}"
VIGIL_DATA_DIR="${VIGIL_DATA_DIR:-$VIGIL_BASE/data}"
export VIGIL_BASE VIGIL_DATA_DIR

# --- Parsing des arguments ---
# --pdf          : forcer la génération du rapport PDF (comportement par défaut)
# --no-pdf       : désactiver la génération du rapport PDF
# --log          : conserver un fichier journal clamscan (.log) sur disque
# --no-log       : ne pas conserver de fichier journal (comportement par défaut)
# --all          : scanner tous les dossiers (mode non-interactif)
# --comment TXT  : commentaire du scan passé en argument (non-interactif)
# --yes          : répondre oui aux confirmations (mode non-interactif)
# Par défaut, aucun fichier journal n'est écrit sur disque (--no-log), et un
# rapport PDF consolidé est généré (--pdf). En mode interactif, l'opérateur
# choisit de conserver un journal et de générer le PDF s'il n'a pas fourni
# les flags correspondants.
GEN_PDF=1
GEN_LOG=0
PDF_SET=0
LOG_SET=0
SCAN_ALL=0
SCAN_COMMENT=""
COMMENT_SET=0
AUTO_YES=0
ARG_USER=""
ARCHIVES_SET=0
SCAN_ARCHIVES=1
SIZE_SET=0
SIZE_MODE="unlimited"
ALERT_ENC_SET=0
ALERT_ENC=1
JSON_OUT_DIR=""
while [ $# -gt 0 ]; do
    case "$1" in
        --pdf)        GEN_PDF=1; PDF_SET=1 ;;
        --no-pdf)     GEN_PDF=0; PDF_SET=1 ;;
        --log)        GEN_LOG=1; LOG_SET=1 ;;
        --no-log)     GEN_LOG=0; LOG_SET=1 ;;
        --all)        SCAN_ALL=1 ;;
        --comment)    shift; SCAN_COMMENT="${1:-}"; COMMENT_SET=1 ;;
        --comment=*) SCAN_COMMENT="${1#--comment=}"; COMMENT_SET=1 ;;
        --yes)        AUTO_YES=1 ;;
        --user)       shift; ARG_USER="${1:-}" ;;
        --user=*)     ARG_USER="${1#--user=}" ;;
        --archives)   SCAN_ARCHIVES=1; ARCHIVES_SET=1 ;;
        --no-archives) SCAN_ARCHIVES=0; ARCHIVES_SET=1 ;;
        --size-unlimited) SIZE_MODE="unlimited"; SIZE_SET=1 ;;
        --size-limit)     SIZE_MODE="limit"; SIZE_SET=1 ;;
        --alert-encrypted)    ALERT_ENC=1; ALERT_ENC_SET=1 ;;
        --no-alert-encrypted) ALERT_ENC=0; ALERT_ENC_SET=1 ;;
        --json-out)    shift; JSON_OUT_DIR="${1:-}" ;;
        --json-out=*)  JSON_OUT_DIR="${1#--json-out=}" ;;
    esac
    shift
done
ACTIVE_USER_FILE="$VIGIL_BASE/data/active_user"
CONFIG_FILE="$VIGIL_DATA_DIR/config/system.json"
INVESTIGATION_DIR="/investigation"
RAPPORTS_DIR="$VIGIL_BASE/rapports"

# Le scan antivirus ClamAV ne necessite pas de projet actif et ne logge pas
# dans la chaine de custody (exception prevue : l'AV n'est pas une analyse
# forensique a custody). L'operateur reste requis pour identifier l'auteur.
ACTIVE_USER=""
ACTIVE_ENTITY=""
if [ -n "$ARG_USER" ]; then
    ACTIVE_USER="$ARG_USER"
elif [ -f "$ACTIVE_USER_FILE" ]; then
    ACTIVE_USER=$(cat "$ACTIVE_USER_FILE")
fi
if [ -f "$CONFIG_FILE" ] && command -v jq >/dev/null 2>&1; then
    ACTIVE_ENTITY=$(jq -r '.entity_name // empty' "$CONFIG_FILE" 2>/dev/null || echo "")
fi

# --- Pause finale conditionnelle ---
# Note : la détection de menaces (INFECTED_TOTAL) est un RÉSULTAT d'analyse,
# pas une erreur d'exécution. Le script ne renvoie un code d'erreur que si
# l'exécution elle-même a échoué (ERRORS > 0), pas si des virus sont trouvés.
final_pause() {
    echo ""
    if [ "$ERRORS" -gt 0 ]; then
        echo -e "${RED}❌ Scan terminé avec $ERRORS erreur(s) d'exécution.${NC}"
        [ "$INFECTED_TOTAL" -gt 0 ] && echo -e "${RED}  ($INFECTED_TOTAL fichier(s) infecté(s) détecté(s)).${NC}"
        echo -e "${YELLOW}Appuyez sur Entrée pour fermer ce terminal...${NC}"
        read -r
        exit 1
    elif [ "$INFECTED_TOTAL" -gt 0 ]; then
        echo -e "${RED}❌ Scan terminé : $INFECTED_TOTAL fichier(s) infecté(s) détecté(s).${NC}"
        echo -e "${YELLOW}Appuyez sur Entrée pour fermer ce terminal...${NC}"
        read -r
    else
        echo -e "${GREEN}✅ Scan terminé sans erreur, aucun fichier infecté.${NC}"
    fi
}

# --- Barre de progression du scan ClamAV ---
#
# clamscan n'embarque aucune option de progression (voir clamscan --help) :
# on scanne donc SANS --infected afin que clamscan imprime chaque fichier
# ('chemin: OK'), et on suit sa sortie ligne par ligne pour afficher une
# barre de progression (pourcentage, fichiers traités, infectés, temps
# écoulé et temps restant estimé).
#
# La sortie complète (y compris les lignes 'chemin: OK') est conservée dans
# le journal : le générateur PDF (vigil_pdf.py) n'en utilise que le résumé
# ('Scanned files:', 'Infected files:', ...) et les lignes 'FOUND'.
#
# Remarque : le comptage initial (find) ne voit pas l'intérieur des
# archives ; sur des archives volumineuses le pourcentage affiché est
# donc une estimation (plafonnée à 99% pendant le scan).

fmt_duration() {
    # $1 : durée en secondes -> HH:MM:SS
    local t=${1:-0}
    printf '%02d:%02d:%02d' $((t / 3600)) $(((t % 3600) / 60)) $((t % 60))
}

progress_monitor() {
    # $1 : fichier journal (reçoit la sortie clamscan complète)
    # $2 : nombre total de fichiers (estimation, pour la barre)
    # $3 : 1 si la sortie est un terminal (barre), 0 sinon (sortie brute)
    local log_file="$1"
    local total=${2:-0}
    local use_tty=${3:-0}
    local done=0 infected=0
    local start=$SECONDS
    local bar_width=30 full="" empty=""
    local i line pct filled bar elapsed eta

    for ((i = 0; i < bar_width; i++)); do
        full+="#"
        empty+=" "
    done

    while IFS= read -r line; do
        printf '%s\n' "$line" >> "$log_file"
        case "$line" in
            *": OK")
                done=$((done + 1))
                if [ "$use_tty" = "1" ]; then
                    if [ "$total" -gt 0 ]; then
                        pct=$((done * 100 / total))
                        [ "$pct" -gt 99 ] && pct=99
                    else
                        pct=0
                    fi
                    filled=$((bar_width * pct / 100))
                    bar="${full:0:filled}${empty:0:$((bar_width - filled))}"
                    elapsed=$((SECONDS - start))
                    if [ "$done" -gt 0 ] && [ "$total" -gt "$done" ]; then
                        eta=$((elapsed * (total - done) / done))
                    else
                        eta=0
                    fi
                    printf '\r\033[96m[%s]\033[0m %3d%% \033[1m%s\033[0m/%s fichiers | infectés : %s | écoulé %s | reste ~%s   ' \
                        "$bar" "$pct" "$done" "$total" "$infected" \
                        "$(fmt_duration "$elapsed")" "$(fmt_duration "$eta")"
                fi
                ;;
            *" FOUND")
                infected=$((infected + 1))
                [ "$use_tty" = "1" ] && printf '\r\033[K'
                printf '\033[91m%s\033[0m\n' "$line"
                ;;
            "ERROR:"* | "WARNING:"*)
                [ "$use_tty" = "1" ] && printf '\r\033[K'
                printf '\033[33m%s\033[0m\n' "$line"
                ;;
            "")
                ;;
            *)
                [ "$use_tty" = "1" ] && printf '\r\033[K'
                printf '%s\n' "$line"
                ;;
        esac
    done

    if [ "$use_tty" = "1" ]; then
        elapsed=$((SECONDS - start))
        printf '\r\033[96m[%s]\033[0m 100%% \033[1m%s\033[0m/%s fichiers | infectés : %s | durée %s            \n' \
            "$full" "$done" "$total" "$infected" "$(fmt_duration "$elapsed")"
    fi
}

clear
print_banner

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  Vigil - Scan antivirus ClamAV               ${NC}"
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}Entité : ${ACTIVE_ENTITY} | Utilisateur : ${ACTIVE_USER}${NC}"
echo ""

# --- Vérification des dépendances ---
echo -e "${BLUE}=== Vérification des dépendances ===${NC}"
if ! command -v clamscan >/dev/null 2>&1; then
    echo -e "${RED}❌ clamscan n'est pas installé.${NC}"
    echo -e "${YELLOW}    Installez-le : sudo apt install clamav${NC}"
    echo -e "${YELLOW}    Puis mettez à jour les bases : sudo bash $(dirname "$0")/vigil_clamav_update.sh${NC}"
    ERRORS=$((ERRORS + 1))
    final_pause
    exit 1
fi

# Vérifier que les bases virales existent
DB_DIR=$(clamconf 2>/dev/null | sed -nE 's/^\s*DatabaseDirectory\s*=\s*"?([^"]*)"?\s*$/\1/p' | tail -1)
[ -z "$DB_DIR" ] && DB_DIR="/var/lib/clamav"
HAS_DB=0
for db in main.cvd main.cld daily.cvd daily.cld; do
    if [ -f "$DB_DIR/$db" ]; then HAS_DB=1; break; fi
done
if [ "$HAS_DB" = "0" ]; then
    echo ""
    echo -e "${YELLOW}⚠️  ${BOLD}Aucune base virale trouvée${NC} ${GREY}dans $DB_DIR${NC}"
    echo -e "  ${GREY}Mettez à jour les bases :${NC} ${BOLD}sudo bash $(dirname "$0")/vigil_clamav_update.sh${NC}"
    if [ "$AUTO_YES" = "1" ]; then
        echo -e "${GREY}--yes : continuation automatique sans base virale.${NC}"
    else
        echo -ne "\n${BOLD}${YELLOW}Voulez-vous continuer quand même ? (o/n) : ${NC}"
        read -r CONT
        [ "$CONT" = "o" ] || [ "$CONT" = "O" ] || { echo -e "${YELLOW}Annulé.${NC}"; exit 0; }
    fi
fi

echo -e "${GREEN}✅ clamscan disponible : $(clamscan --version 2>/dev/null | head -1)${NC}"
echo ""

# --- Lister les dossiers disponibles dans /investigation ---
echo ""
echo -e "${BOLD}Dossiers disponibles dans $INVESTIGATION_DIR :${NC}"
echo ""
if [ ! -d "$INVESTIGATION_DIR" ]; then
    echo -e "${RED}❌ ${BOLD}Le dossier $INVESTIGATION_DIR n'existe pas.${NC}"
    echo -e "  ${GREY}Montez d'abord un périphérique via le script de montage.${NC}"
    ERRORS=$((ERRORS + 1))
    final_pause
    exit 1
fi

# Collecter les sous-dossiers (et /investigation lui-même)
SCAN_DIRS=()
i=0
while IFS= read -r -d '' dir; do
    SCAN_DIRS+=("$dir")
    i=$((i + 1))
done < <(find "$INVESTIGATION_DIR" -maxdepth 1 -mindepth 1 -type d -print0 2>/dev/null)

# Proposer aussi /investigation lui-même s'il contient des fichiers directement
if [ -n "$(find "$INVESTIGATION_DIR" -maxdepth 1 -mindepth 1 -type f -print -quit 2>/dev/null)" ]; then
    SCAN_DIRS+=("$INVESTIGATION_DIR")
fi

if [ "${#SCAN_DIRS[@]}" -eq 0 ]; then
    echo -e "${YELLOW}ℹ️  Aucun dossier à scanner dans $INVESTIGATION_DIR.${NC}"
    echo -e "${YELLOW}     (le dossier est vide ou ne contient pas de sous-dossier)${NC}"
    # Aucun dossier à scanner (information seulement, pas de custody).
    final_pause
    exit 0
fi

for idx in "${!SCAN_DIRS[@]}"; do
    size=$(du -sh "${SCAN_DIRS[$idx]}" 2>/dev/null | awk '{print $1}' || echo "?")
    files=$(find "${SCAN_DIRS[$idx]}" -type f 2>/dev/null | wc -l || echo 0)
    echo -e "  ${BOLD}${BLUE}[$((idx+1))]${NC}  ${BOLD}${SCAN_DIRS[$idx]}${NC}  ${GREY}•${NC} ${BOLD}$size${NC} ${GREY}•${NC} ${BOLD}$files${NC} ${GREY}fichier(s)${NC}"
done
echo ""
echo -e "  ${BOLD}${BLUE}[t]${NC}  ${BOLD}Tous les dossiers${NC}"
echo -e "  ${BOLD}${BLUE}[q]${NC}  ${BOLD}Quitter${NC}"
echo ""

# --- Sélection des dossiers à scanner ---
TARGETS=()
if [ "$SCAN_ALL" = "1" ]; then
    # Mode non-interactif : scanner tous les dossiers disponibles.
    echo -e "${GREY}--all : sélection automatique de tous les dossiers.${NC}"
    TARGETS=("${SCAN_DIRS[@]}")
else
while true; do
    echo -ne "${BOLD}${YELLOW}Entrez le numéro d'un dossier, plusieurs numéros séparés par des espaces, 't' pour tous, ou 'q' : ${NC}"
    read -r CHOICE
    [ -z "$CHOICE" ] && continue

    if [ "$CHOICE" = "q" ]; then
        echo -e "${YELLOW}Annulé.${NC}"
        echo -e "${YELLOW}Scan annulé par l'utilisateur.${NC}"
        final_pause
        exit 0
    fi

    if [ "$CHOICE" = "t" ]; then
        TARGETS=("${SCAN_DIRS[@]}")
        break
    fi

    # Parser plusieurs numéros
    valid=1
    for num in $CHOICE; do
        if ! [[ "$num" =~ ^[0-9]+$ ]] || [ "$num" -lt 1 ] || [ "$num" -gt "${#SCAN_DIRS[@]}" ]; then
            echo -e "${RED}❌ Numéro invalide : $num${NC}"
            valid=0
            break
        fi
    done
    [ "$valid" = "0" ] && continue

    for num in $CHOICE; do
        TARGETS+=("${SCAN_DIRS[$((num-1))]}")
    done
    break
done
fi

echo ""
echo -e "${GREEN}Dossiers à scanner :${NC} ${BOLD}${#TARGETS[@]}${NC}"
for t in "${TARGETS[@]}"; do echo -e "  ${BLUE}•${NC} ${BOLD}$t${NC}"; done
echo ""

# --- Options de scan ---
# Les périphériques sont montés en lecture seule (blockdev --setro) :
# aucune action n'est possible sur les fichiers infectés (ni déplacement,
# ni suppression). On scanne sans limite de taille pour tout analyser.
CLAM_OPTS=""
ACTION_LABEL="aucune action (lecture seule)"

# --- Scan du contenu des archives (forcé par défaut) ---
# --scan-archive=yes est passé EXPLICITEMENT à clamscan : ne pas compter
# sur le défaut implicite de libclamav, qui pourrait changer selon la
# version ou la configuration (clamscan --help : --scan-archive[=yes(*)/no],
# le défaut est marqué (*) mais on le force pour garantir que le contenu
# des zip/tar.gz/7z/rar est extrait en mémoire et scanné individuellement
# avec les signatures). --no-archives (override CLI) transmet
# --scan-archive=no pour aller plus vite sur de gros volumes sans archives.
if [ "$SCAN_ARCHIVES" = "1" ]; then
    CLAM_OPTS="$CLAM_OPTS --scan-archive=yes"
else
    CLAM_OPTS="$CLAM_OPTS --scan-archive=no"
fi

# --- Taille des fichiers scannés (par défaut : illimité, plus de question) ---
# Par défaut, clamscan SAUTE les fichiers de plus de 25 Mo (--max-filesize)
# et ne scanne que les 100 premiers Mo du contenu d'une archive
# (--max-scansize). Vigil applique d'office le mode illimité :
# --max-filesize=2047M --max-scansize=2047M, soit le plafond réel de
# ClamAV (2 GiB - 1 = 2147483647 octets : au-delà, libclamav émet un
# warning et refuse de scanner). Tous les fichiers, même volumineux, sont
# scannés intégralement, sans question interactive.
# --size-limit (override CLI) limite à 512 Mo par fichier et 512 Mo de
# contenu d'archive — assez large pour ne rien sauter d'utile tout en
# évitant les fichiers monumentaux qui plafonnent la durée du scan.
if [ "$SIZE_MODE" = "unlimited" ]; then
    CLAM_OPTS="$CLAM_OPTS --max-filesize=2047M --max-scansize=2047M"
else
    CLAM_OPTS="$CLAM_OPTS --max-filesize=512M --max-scansize=512M"
fi

# --- Signalement des archives chiffrées (forcé par défaut) ---
# clamscan ne peut pas ouvrir une archive protégée par mot de passe : sans
# --alert-encrypted elle est ignorée EN SILENCE (aucun résultat, aucun
# avertissement dans le rapport). Avec --alert-encrypted, elle est signalée
# comme 'Heuristics.Encrypted.Zip' : le rapport indique clairement que
# l'archive n'a pas pu être analysée — indispensable en forensique.
# --no-alert-encrypted (override CLI) désactive ce signalement.
if [ "$ALERT_ENC" = "1" ]; then
    CLAM_OPTS="$CLAM_OPTS --alert-encrypted"
fi

# --- Commentaire du scan ---
echo ""
if [ "$COMMENT_SET" != "1" ]; then
    echo -ne "${BOLD}${YELLOW}Commentaire (facultatif, Entrée pour ignorer) : ${NC}"
    read -r SCAN_COMMENT
    [ -z "$SCAN_COMMENT" ] && SCAN_COMMENT=""
fi

# --- Options de sortie (journal + PDF) ---
# En mode interactif (pas de flag explicite), demander à l'opérateur s'il
# souhaite conserver un fichier journal et/ou générer un rapport PDF.
# Par défaut (mode non-interactif --all) : pas de log, PDF généré.
if [ "$AUTO_YES" != "1" ]; then
    if [ "$LOG_SET" != "1" ]; then
        echo -ne "${BOLD}${YELLOW}Conserver un journal clamscan (.log) ? (o/n) — non (par défaut) : ${NC}"
        read -r _ans
        case "$_ans" in o|O|y|Y) GEN_LOG=1 ;; *) GEN_LOG=0 ;; esac
    fi
    if [ "$PDF_SET" != "1" ]; then
        echo -ne "${BOLD}${YELLOW}Générer un rapport PDF ? (o/n) — oui (par défaut) : ${NC}"
        read -r _ans
        case "$_ans" in n|N) GEN_PDF=0 ;; *) GEN_PDF=1 ;; esac
    fi
    echo ""
fi

# --- Tableau récapitulatif des options (après clear + bannière) ---
clear
print_banner
print_options_table

# --- Scan de chaque dossier ---
# Par défaut, aucun fichier journal n'est conservé sur disque. La sortie
# clamscan est capturée dans des fichiers temporaires (sous /tmp) uniquement
# le temps de générer le rapport PDF consolidé. Ces temporaires sont
# supprimés en fin de script. Si --log est demandé, une copie persistante
# est conservée dans $RAPPORTS_DIR.
STAMP=$(date +"%Y%m%d_%H%M%S")
SCAN_LOGS=()          # fichiers conservés (si --log) ou temporaires (pour PDF)
TMP_LOGS=()
cleanup_tmp_logs() {
    for f in "${TMP_LOGS[@]}"; do
        rm -f "$f" 2>/dev/null || true
    done
}
trap cleanup_tmp_logs EXIT
for target in "${TARGETS[@]}"; do
    target_name=$(basename "$target")
    SCANNED_DIRS+=("$target_name")
    echo -e "${BOLD}Scan de $target_name :${NC} $target"
    echo ""
    mkdir -p "$RAPPORTS_DIR" 2>/dev/null || true

    # Nombre de fichiers à scanner (pour la barre de progression). Le
    # comptage peut prendre du temps sur un gros périphérique.
    echo -ne "${GREY}Comptage des fichiers à scanner...${NC}"
    TOTAL_FILES=$(find "$target" -type f 2>/dev/null | wc -l)
    echo -e "\r${GREY}Fichiers à scanner : ${NC}${BOLD}${TOTAL_FILES}${NC}        "
    echo ""

    # Fichier journal : persistant (--log) ou temporaire (PDF seulement).
    if [ "$GEN_LOG" -eq 1 ]; then
        RAPPORT="$RAPPORTS_DIR/clamav_${target_name}_${STAMP}.log"
        SCAN_LOGS+=("$RAPPORT")
        LOG_FILE="$RAPPORT.tmp"
        : > "$RAPPORT.tmp"
    else
        TMP_LOG="$(mktemp --tmpdir "clamav_${target_name}_${STAMP}.XXXXXX.log" 2>/dev/null || echo "/tmp/clamav_${target_name}_${STAMP}_$$.log")"
        TMP_LOGS+=("$TMP_LOG")
        SCAN_LOGS+=("$TMP_LOG")
        LOG_FILE="$TMP_LOG"
        : > "$TMP_LOG"
    fi

    # Scan SANS --infected : clamscan imprime chaque fichier ('chemin: OK'),
    # ce qui alimente la barre de progression. La sortie complète (OK, FOUND,
    # résumé) est écrite dans le journal ; sur terminal, seule la barre
    # s'affiche (les OK sont comptés silencieusement, les menaces et erreurs
    # s'affichent au fil de l'eau).
    if [ -t 1 ]; then
        USE_TTY=1
    else
        USE_TTY=0
    fi
    sudo clamscan --recursive --bell $CLAM_OPTS "$target" 2>&1 \
        | progress_monitor "$LOG_FILE" "$TOTAL_FILES" "$USE_TTY"
    CLAM_RC=${PIPESTATUS[0]:-0}

    if [ "$GEN_LOG" -eq 1 ]; then
        cp "$RAPPORT.tmp" "$RAPPORT" 2>/dev/null || true
        rm -f "$RAPPORT.tmp" 2>/dev/null || true
    fi
    # Extraire le nombre de fichiers infectés depuis le résumé
    INFECTED=$(grep -i "Infected files:" "$LOG_FILE" 2>/dev/null | awk -F: '{print $2}' | xargs || echo "0")
    [ -z "$INFECTED" ] && INFECTED=0
    SCANNED=$(grep -i "Scanned files:" "$LOG_FILE" 2>/dev/null | awk -F: '{print $2}' | xargs || echo "0")
    echo ""
    if [ "$CLAM_RC" = "0" ]; then
        echo -e "${GREEN}✅ Aucun fichier infecté dans $target ($SCANNED fichiers scannés).${NC}"
    elif [ "$CLAM_RC" = "1" ]; then
        # Code 1 = menaces détectées : c'est un résultat, pas une erreur d'exécution.
        echo -e "${RED}❌ $INFECTED fichier(s) infecté(s) détecté(s) dans $target ($SCANNED scannés).${NC}"
        [ "$GEN_LOG" -eq 1 ] && echo -e "${BLUE}Rapport : $RAPPORT${NC}"
        INFECTED_TOTAL=$((INFECTED_TOTAL + INFECTED))
    else
        echo -e "${RED}❌ clamscan a rencontré une erreur (code $CLAM_RC) sur $target.${NC}"
        echo -e "${YELLOW}  (code 2 = erreur de base virale ou de lecture ; vérifiez les logs)${NC}"
        [ "$GEN_LOG" -eq 1 ] && echo -e "${BLUE}Rapport : $RAPPORT${NC}"
        ERRORS=$((ERRORS + 1))
    fi
    echo ""
done

# --- Copie des journaux pour le rapport consolide (--json-out) ---
# Mode multi-analyses : les journaux clamscan (persistants ou temporaires)
# sont copies dans le dossier de collecte sous un nom previsible
# (clamav_<dossier>.log) pour etre assembles par vigil_pdf.py --kind multi.
if [ -n "$JSON_OUT_DIR" ] && [ "${#SCAN_LOGS[@]}" -gt 0 ]; then
    mkdir -p "$JSON_OUT_DIR" 2>/dev/null || true
    for lf in "${SCAN_LOGS[@]}"; do
        [ -f "$lf" ] || continue
        cp -f "$lf" "$JSON_OUT_DIR/" 2>/dev/null || true
    done
fi

# --- Résumé final ---
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Résumé du scan${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "Dossiers scannés : ${#SCANNED_DIRS[@]}"
for d in "${SCANNED_DIRS[@]}"; do echo -e "  ${BLUE}- $d${NC}"; done
echo -e "Fichiers infectés au total : ${INFECTED_TOTAL}"
echo -e "Erreurs : ${ERRORS}"
echo -e "Rapports : $RAPPORTS_DIR/clamav_*_${STAMP}.log"

# --- Génération du rapport PDF consolidé ---
# Un seul rapport PDF rassemblant tous les dossiers scannés (résumé global +
# détail par dossier + menaces). L'échec de la génération PDF n'échec pas le
# scan (le scan lui-même a réussi ; le PDF est un rendu de présentation).
echo ""
echo -e "${BLUE}=== Génération du rapport PDF ===${NC}"
if [ "$GEN_PDF" -eq 0 ]; then
    echo -e "${YELLOW}⏏️  Génération du rapport PDF désactivée (--no-pdf).${NC}"
else
    PDF_SCRIPT="$(dirname "$0")/../pdf/vigil_pdf.py"
    if [ -f "$PDF_SCRIPT" ]; then
        mkdir -p "$RAPPORTS_DIR" 2>/dev/null || true
        # Construire la liste des arguments --log pour tous les dossiers scannés.
        LOG_ARGS=()
        for lf in "${SCAN_LOGS[@]}"; do
            [ -f "$lf" ] && LOG_ARGS+=(--log "$lf")
        done
        if [ "${#LOG_ARGS[@]}" -eq 0 ]; then
            echo -e "${YELLOW}⚠️  Aucun journal de scan trouvé, rapport PDF ignoré.${NC}"
        elif command -v python3 >/dev/null 2>&1; then
            PDF_OUT=$(python3 "$PDF_SCRIPT" \
                --kind clamav \
                "${LOG_ARGS[@]}" \
                --user "$ACTIVE_USER" \
                --project "" \
                --action "$ACTION_LABEL" \
                --options="--recursive --bell $CLAM_OPTS" \
                --comment "$SCAN_COMMENT" \
                --dir "$RAPPORTS_DIR" 2>&1)
            if [ $? -eq 0 ] && [ -n "$PDF_OUT" ] && [ -f "$PDF_OUT" ]; then
                echo -e "${GREEN}✅ Rapport PDF généré : $PDF_OUT${NC}"
                # Copie du rapport PDF dans le dossier du projet actif (pour l'export).
                _AP=""
                [ -f "$VIGIL_BASE/data/active_project" ] && _AP=$(cat "$VIGIL_BASE/data/active_project" 2>/dev/null)
                if [ -n "$_AP" ] && [ "$_AP" != "(no-project)" ] && [ -d "$VIGIL_BASE/data/projects/$_AP" ] && [ -w "$VIGIL_BASE/data/projects/$_AP" ]; then
                    cp -f "$PDF_OUT" "$VIGIL_BASE/data/projects/$_AP/" 2>/dev/null && \
                        echo -e "${GREEN}   Rapport copié dans le dossier du projet : $VIGIL_BASE/data/projects/$_AP/$(basename "$PDF_OUT")${NC}"
                fi
            else
                echo -e "${RED}❌ Échec de la génération du rapport PDF (le scan lui-même a réussi).${NC}"
                echo -e "${YELLOW}    $PDF_OUT${NC}"
            fi
        else
            echo -e "${YELLOW}⚠️  python3 absent, impossible de générer le rapport PDF.${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  Script de génération PDF introuvable ($PDF_SCRIPT).${NC}"
    fi
fi
final_pause
