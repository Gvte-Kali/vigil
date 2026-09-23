#!/bin/bash
set -uo pipefail

# --- Mise a jour des bases virales ClamAV ---
# Contrairement a Scalpel (100% hors reseau, qui recupere les bases via un
# intranet), cette machine est connectee a Internet : on utilise freshclam
# directement pour mettre a jour les signatures (main.cvd, daily.cvd,
# bytecode.cvd).
#
# Usage : vigil_clamav_update.sh
# Peut etre lance seul (hors projet) ou depuis un terminal projet.

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

final_pause() {
    echo ""
    if [ "$ERRORS" -gt 0 ]; then
        echo -e "${RED}❌ Mise à jour terminée avec $ERRORS erreur(s).${NC}"
        echo -e "${YELLOW}Appuyez sur Entrée pour fermer ce terminal...${NC}"
        read -r
        exit 1
    else
        echo -e "${GREEN}✅ Mise à jour terminée sans erreur.${NC}"
    fi
}

clear
print_banner

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  Vigil - Mise à jour ClamAV                 ${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# --- Vérifier que freshclam / clamscan sont installés ---
echo -e "${BLUE}=== Vérification des dépendances ===${NC}"
MISSING=0
for cmd in freshclam clamscan; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo -e "${RED}❌ Outil requis absent : $cmd${NC}"
        echo -e "${YELLOW}    Installez-le : sudo apt install clamav clamav-daemon${NC}"
        MISSING=$((MISSING + 1))
    fi
done
[ "$MISSING" -gt 0 ] && { ERRORS=$MISSING; final_pause; }

# --- Arrêter le daemon freshclam s'il tourne (peut bloquer la maj manuelle) ---
echo -e "${YELLOW}Arrêt du daemon freshclam (s'il tourne)...${NC}"
if systemctl is-active --quiet clamav-freshclam 2>/dev/null; then
    sudo systemctl stop clamav-freshclam 2>/dev/null || true
    FRESHCLAM_WAS_RUNNING=1
else
    FRESHCLAM_WAS_RUNNING=0
fi

# --- Mettre à jour les bases virales ---
echo -e "${BLUE}=== Téléchargement des signatures virales ===${NC}"
echo -e "${YELLOW}Connexion aux serveurs ClamAV (database.clamav.net)...${NC}"
echo ""

if sudo freshclam --quiet 2>&1; then
    echo ""
    echo -e "${GREEN}✅ Bases virales mises à jour avec succès.${NC}"
else
    echo ""
    echo -e "${YELLOW}⚠️  freshclam a retourné un code non nul (les bases sont peut-être déjà à jour).${NC}"
    # freshclam renvoie parfois un code != 0 même en cas de "up to date"
fi

# --- Test sur signature EICAR ---
echo ""
echo -e "${BLUE}=== Test sur signature EICAR ===${NC}"
EICAR='WDVPIVAlQEFQWzRcUFpYNTQoUF4pN0NDKTd9JEVJQ0FSLVNUQU5EQVJELUFOVElWSVJVUy1URVNULUZJTEUhJEgrSCo='
EICAR_TMP=$(mktemp 2>/dev/null || echo "/tmp/vigil_eicar_$$.tmp")
echo "$EICAR" | base64 -d > "$EICAR_TMP" 2>/dev/null
# clamscan renvoie 0=propre, 1=virus detecte, 2=erreur ; on accepte aussi la
# sortie texte (Win.Test.Eicar-Test-Signature FOUND) au cas ou le code de
# sortie serait peu fiable.
clamscan --no-summary --infected "$EICAR_TMP" >"${EICAR_TMP}.out" 2>&1
EICAR_RC=$?
EICAR_OUT=$(cat "${EICAR_TMP}.out" 2>/dev/null)
rm -f "$EICAR_TMP" "${EICAR_TMP}.out" 2>/dev/null
if [ "$EICAR_RC" = "1" ] || echo "$EICAR_OUT" | grep -qi "eicar\|FOUND"; then
    echo -e "${GREEN}✅ Test EICAR réussi : ClamAV détecte correctement les signatures.${NC}"
else
    echo -e "${RED}❌ Le test EICAR a échoué : les bases virales pourraient être incorrectes.${NC}"
    echo -e "${YELLOW}    (clamscan a retourné le code $EICAR_RC)${NC}"
    ERRORS=$((ERRORS + 1))
fi

# --- Redémarrer le daemon freshclam s'il tournait avant ---
if [ "$FRESHCLAM_WAS_RUNNING" = "1" ]; then
    echo -e "${YELLOW}Redémarrage du daemon freshclam...${NC}"
    sudo systemctl start clamav-freshclam 2>/dev/null || true
fi

# --- Afficher la version et l'état des bases ---
echo ""
echo -e "${BLUE}=== État des bases ===${NC}"
clamscan --version 2>/dev/null || true
DB_DIR=$(clamconf 2>/dev/null | sed -nE 's/^\s*DatabaseDirectory\s*=\s*"?([^"]*)"?\s*$/\1/p' | tail -1)
[ -z "$DB_DIR" ] && DB_DIR="/var/lib/clamav"
[ -d "$DB_DIR" ] && ls -lh "$DB_DIR"/*.cvd "$DB_DIR"/*.cld 2>/dev/null | awk '{print "  " $9 " (" $5 ")"}' || true

final_pause
