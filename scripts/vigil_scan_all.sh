#!/bin/bash
set -uo pipefail

# --- Orchestrateur de scans Vigil ---
#
# Lance l'intégralité des analyses forensiques disponibles en une seule
# commande, dans l'ordre :
#   1. Recensement
#   2. Antivirus (ClamAV)
#   3. Fichiers image
#   4. Fichiers vidéo
#   5. Fichiers audio
#   6. Fichiers bureautiques
#   7. Fichiers archives
#   8. Fichiers verrouillés (crypto)
#   9. Fichiers à forte entropie
#  10. Fichiers volumineux
#
# Les scripts sont lancés avec --no-pdf --json-out <collect_dir> : aucun PDF
# individuel n'est généré, mais le JSON de résultat est copié dans un dossier
# de collecte temporaire. À la fin, un SEUL rapport PDF consolidé est généré
# via vigil_pdf.py --kind multi, assemblant toutes les sections + un sommaire.
#
# Les scripts sont lancés de façon indépendante : l'échec d'une analyse
# n'interrompt pas les suivantes. Un bilan global est affiché à la fin.

# --- Couleurs ---
RED='\e[91m'
GREEN='\e[92m'
YELLOW='\e[93m'
BLUE='\e[96m'
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

ERRORS=0
SUCCES=0
TOTAL=0

# Repertoire contenant ce script (scripts/), pour localiser les sous-scripts.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# --- Parsing des arguments ---
# --no-pdf  : desactiver la generation du rapport PDF consolide
# --pdf     : forcer la generation du rapport PDF consolide (defaut)
GEN_PDF=1
while [ $# -gt 0 ]; do
    case "$1" in
        --pdf)     GEN_PDF=1 ;;
        --no-pdf)  GEN_PDF=0 ;;
    esac
    shift
done

# --- Verifier qu'un utilisateur (obligatoire) est actif ---
VIGIL_BASE="${VIGIL_BASE:-/opt/vigil}"
ACTIVE_USER_FILE="$VIGIL_BASE/data/active_user"
if [ ! -f "$ACTIVE_USER_FILE" ]; then
    echo -e "${RED}❌ Aucun utilisateur actif sélectionné.${NC}"
    echo "Sélectionnez un utilisateur via l'interface GUI."
    exit 1
fi
ACTIVE_USER=$(cat "$ACTIVE_USER_FILE")
ACTIVE_PROJECT=$(cat "$VIGIL_BASE/data/active_project" 2>/dev/null || echo "")
if [ -z "$ACTIVE_PROJECT" ] || [ "$ACTIVE_PROJECT" = "(no-project)" ]; then
    ACTIVE_PROJECT="(no-project)"
fi

RAPPORTS_DIR="$VIGIL_BASE/rapports"
PDF_SCRIPT="$SCRIPT_DIR/pdf/vigil_pdf.py"
STAMP=$(date +"%Y%m%d_%H%M%S")

# Dossier de collecte des JSON pour le rapport consolide.
COLLECT_DIR=$(mktemp -d -t "vigil_multi_${STAMP}.XXXXXX" 2>/dev/null || echo "/tmp/vigil_multi_$$")

# Sections du rapport consolide : tableau de "kind:status:path".
SECTIONS=()

# --- final_pause : ne ferme jamais le terminal sans lecture ---
final_pause() {
    echo ""
    if [ "$ERRORS" -gt 0 ]; then
        echo -e "${RED}❌ Orchestration terminée avec $ERRORS erreur(s) sur $TOTAL analyse(s).${NC}"
    else
        echo -e "${GREEN}✅ Orchestration terminée : $SUCCES/$TOTAL analyse(s) réussie(s).${NC}"
    fi
    echo -e "${YELLOW}Appuyez sur Entrée pour fermer ce terminal...${NC}"
    read -r
}

# --- Lancer une analyse : execute un script en lui passant une entree vide
# pour satisfaire son final_pause (read -r) sans bloquer la chaine.
# Arguments : $1 = etiquette, $2 = kind (pour le PDF), $3 = chemin du script,
# $4 = nom du fichier JSON attendu dans COLLECT_DIR, $5+ = args supplementaires
run_analysis() {
    local label="$1"; shift
    local kind="$1"; shift
    local script="$1"; shift
    local json_name="$1"; shift
    local args=("$@")

    TOTAL=$((TOTAL + 1))
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  ${label}${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    if [ ! -f "$script" ]; then
        echo -e "${RED}❌ Script introuvable : $script${NC}"
        ERRORS=$((ERRORS + 1))
        SECTIONS+=("${kind}:error:")
        return 1
    fi

    # Entree vide pour le read final ; capture de la sortie + code retour.
    if echo "" | bash "$script" "${args[@]}" 2>&1; then
        echo -e "${GREEN}✅ ${label} : terminé avec succès.${NC}"
        SUCCES=$((SUCCES + 1))
        local json_path="$COLLECT_DIR/$json_name"
        if [ -f "$json_path" ]; then
            SECTIONS+=("${kind}:ok:${json_path}")
        else
            SECTIONS+=("${kind}:error:")
        fi
    else
        echo -e "${RED}❌ ${label} : terminé avec erreur(s).${NC}"
        ERRORS=$((ERRORS + 1))
        SECTIONS+=("${kind}:error:")
    fi
}

# --- En-tête ---
clear
print_banner
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  Vigil - Orchestrateur de scans complets   ${NC}"
echo -e "${BLUE}============================================${NC}"
if [ "$ACTIVE_PROJECT" = "(no-project)" ]; then
    echo -e "${BLUE}Projet : (aucun)${NC}"
else
    echo -e "${BLUE}Projet : ${ACTIVE_PROJECT}${NC}"
fi
echo -e "${BLUE}Utilisateur : ${ACTIVE_USER}${NC}"
echo -e "${BLUE}Rapport PDF consolide : $([ "$GEN_PDF" -eq 1 ] && echo "activé" || echo "désactivé")${NC}"
echo -e "${BLUE}Analyses : recensement, antivirus, images, vidéos, audio, bureautique, archives, verrouillés, entropie, volumineux${NC}"
echo ""

# --- Lancement des analyses ---
# Chaque script est lancé avec --no-pdf (pas de PDF individuel) et
# --json-out (copie du JSON vers COLLECT_DIR pour le rapport consolide).
# On transmet chaque arg séparément pour éviter les problèmes de splitting.

run_analysis "Recensement des fichiers" "census" \
    "$SCRIPT_DIR/analyse/vigil_census.sh" "vigil_census.json" --no-pdf --json-out "$COLLECT_DIR"

# ClamAV : --log conserve le journal clamscan pour le rapport consolide.
# Le journal est dans RAPPORTS_DIR/clamav_*_${STAMP}.log.
CLAM_STAMP=$(date +"%Y%m%d_%H%M%S")
echo "" | bash "$SCRIPT_DIR/clamav/vigil_clamav_scan.sh" --no-pdf --log --all --yes --comment "" 2>&1
CLAM_RC=$?
TOTAL=$((TOTAL + 1))
if [ $CLAM_RC -eq 0 ]; then
    echo -e "${GREEN}✅ Analyse antivirus (ClamAV) : terminé avec succès.${NC}"
    SUCCES=$((SUCCES + 1))
    # Trouver le journal clamav conservé.
    CLAM_LOG=$(ls -t "$RAPPORTS_DIR"/clamav_*_${CLAM_STAMP}.log 2>/dev/null | head -1)
    if [ -n "$CLAM_LOG" ] && [ -f "$CLAM_LOG" ]; then
        SECTIONS+=("clamav:ok:${CLAM_LOG}")
    else
        SECTIONS+=("clamav:error:")
    fi
else
    echo -e "${RED}❌ Analyse antivirus (ClamAV) : terminé avec erreur(s).${NC}"
    ERRORS=$((ERRORS + 1))
    SECTIONS+=("clamav:error:")
fi

run_analysis "Analyse des fichiers image" "images" \
    "$SCRIPT_DIR/analyse/vigil_images.sh" "vigil_images.json" --no-pdf --json-out "$COLLECT_DIR"

run_analysis "Analyse des fichiers vidéo" "videos" \
    "$SCRIPT_DIR/analyse/vigil_videos.sh" "vigil_videos.json" --no-pdf --json-out "$COLLECT_DIR"

run_analysis "Analyse des fichiers audio" "audio" \
    "$SCRIPT_DIR/analyse/vigil_audio.sh" "vigil_audio.json" --no-pdf --json-out "$COLLECT_DIR"

run_analysis "Analyse des fichiers bureautiques" "office" \
    "$SCRIPT_DIR/analyse/vigil_office.sh" "vigil_office.json" --no-pdf --json-out "$COLLECT_DIR"

run_analysis "Analyse des fichiers archives" "archives" \
    "$SCRIPT_DIR/analyse/vigil_archives.sh" "vigil_archives.json" --no-pdf --json-out "$COLLECT_DIR"

run_analysis "Analyse des fichiers verrouillés (crypto)" "crypto" \
    "$SCRIPT_DIR/analyse/vigil_crypto.sh" "vigil_crypto.json" --no-pdf --json-out "$COLLECT_DIR"

run_analysis "Analyse des fichiers à forte entropie" "entropy" \
    "$SCRIPT_DIR/analyse/vigil_entropy.sh" "vigil_entropy.json" --no-pdf --json-out "$COLLECT_DIR"

run_analysis "Analyse des fichiers volumineux" "bigfiles" \
    "$SCRIPT_DIR/analyse/vigil_bigfiles.sh" "vigil_bigfiles.json" --no-pdf --json-out "$COLLECT_DIR"

# --- Génération du rapport PDF consolidé ---
if [ "$GEN_PDF" -eq 1 ] && [ ${#SECTIONS[@]} -gt 0 ]; then
    echo ""
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}  Génération du rapport PDF consolidé       ${NC}"
    echo -e "${BLUE}============================================${NC}"

    if [ -f "$PDF_SCRIPT" ] && command -v python3 >/dev/null 2>&1; then
        SECTION_ARGS=()
        for sec in "${SECTIONS[@]}"; do
            SECTION_ARGS+=(--section "$sec")
        done
        MULTI_PDF=$(python3 "$PDF_SCRIPT" \
            --kind multi \
            "${SECTION_ARGS[@]}" \
            --user "$ACTIVE_USER" \
            --project "$ACTIVE_PROJECT" \
            --dir "$RAPPORTS_DIR" 2>&1)
        if [ $? -eq 0 ] && [ -n "$MULTI_PDF" ] && [ -f "$MULTI_PDF" ]; then
            echo -e "${GREEN}✅ Rapport PDF consolidé généré : $MULTI_PDF${NC}"
            # Copie dans le dossier du projet (pour l'export).
            if [ "$ACTIVE_PROJECT" != "(no-project)" ]; then
                PROJ_DIR="$VIGIL_BASE/data/projects/$ACTIVE_PROJECT"
                if [ -d "$PROJ_DIR" ] && [ -w "$PROJ_DIR" ]; then
                    cp -f "$MULTI_PDF" "$PROJ_DIR/" 2>/dev/null && \
                        echo -e "${GREEN}   Rapport copié dans le dossier du projet${NC}"
                fi
            fi
        else
            echo -e "${RED}❌ Échec de la génération du rapport PDF consolidé.${NC}"
            echo -e "${YELLOW}    $MULTI_PDF${NC}"
            ERRORS=$((ERRORS + 1))
        fi
    else
        echo -e "${RED}❌ python3 ou script PDF manquant, rapport consolidé ignoré.${NC}"
        ERRORS=$((ERRORS + 1))
    fi
fi

# --- Bilan final ---
echo ""
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  Bilan de l'orchestration                 ${NC}"
echo -e "${BLUE}============================================${NC}"
echo -e "${BOLD}Analyses lancées :${NC} $TOTAL"
echo -e "${GREEN}Réussies :${NC} $SUCCES"
echo -e "${RED}En erreur :${NC} $ERRORS"
[ "$GEN_PDF" -eq 1 ] && echo -e "${GREY}Rapport PDF consolidé disponible dans : ${RAPPORTS_DIR}${NC}"

# Nettoyage du dossier de collecte temporaire.
rm -rf "$COLLECT_DIR" 2>/dev/null || true

final_pause
