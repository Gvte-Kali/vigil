#!/bin/bash
set -uo pipefail

# --- Détection des visages sur les fichiers image ---
#
# Inspiré de scalpel/bin/faces : recherche des visages dégagés et de face
# parmi les fichiers image détectés lors de l'analyse.
#
# Le script reçoit en arguments :
#   $1 : le dossier d'analyse (OUTPUT_DIR) créé par vigil_images.sh
#   $2 : le fichier de liste d'images (TSV : chemin<TAB>mime<TAB>taille)
#
# Le script :
#   1. sélectionne les images de plus de 8192 px² (trop petites = pas fiable) ;
#   2. tente la détection via facedetect (si disponible) ;
#   3. sinon, fallback via python3 + OpenCV (cv2) ;
#   4. génère un JSON faces_result.json dans OUTPUT_DIR.
#
# Les copies optionnelles des fichiers avec visages se font vers le dossier
# choisi par l'utilisateur (option --copy-to). Aucun lien symbolique n'est créé.

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

VIGIL_BASE="${VIGIL_BASE:-/opt/vigil}"
ACTIVE_USER_FILE="$VIGIL_BASE/data/active_user"
ACTIVE_USER=$(cat "$ACTIVE_USER_FILE" 2>/dev/null || echo "(inconnu)")

# --- Arguments ---
OUTPUT_DIR="${1:-}"
IMAGE_LIST="${2:-}"
COPY_TO=""
if [ "${3:-}" = "--copy-to" ] && [ -n "${4:-}" ]; then
    COPY_TO="$4"
fi
if [ -z "$OUTPUT_DIR" ] || [ ! -d "$OUTPUT_DIR" ]; then
    echo -e "${RED}❌ Dossier d'analyse manquant ou inexistant.${NC}"
    echo "Usage : $0 <output_dir> <image_list.tsv> [--copy-to <dossier>]"
    exit 1
fi
if [ -z "$IMAGE_LIST" ] || [ ! -f "$IMAGE_LIST" ]; then
    echo -e "${RED}❌ Liste d'images manquante ou inexistante.${NC}"
    echo "Usage : $0 <output_dir> <image_list.tsv> [--copy-to <dossier>]"
    exit 1
fi

STAMP=$(date +"%Y%m%d_%H%M%S")
# FACES_DIR n'est plus un dossier de stockage, juste le dossier temporaire
# de travail pour les fichiers .faces_*.txt et .selected_*.txt.
FACES_DIR="$OUTPUT_DIR"


# --- Écran d'accueil ---
clear
print_banner

# --- Vérifier les dépendances ---
echo -e "${BLUE}=== Vérification des dépendances ===${NC}"
DETECT_METHOD=""
if command -v facedetect >/dev/null 2>&1; then
    DETECT_METHOD="facedetect"
    echo -e "${GREEN}✅ facedetect détecté.${NC}"
elif command -v python3 >/dev/null 2>&1 && python3 -c "import cv2" 2>/dev/null; then
    DETECT_METHOD="opencv"
    echo -e "${GREEN}✅ python3 + OpenCV (cv2) détecté.${NC}"
else
    echo -e "${RED}❌ Aucun outil de détection des visages disponible.${NC}"
    echo -e "${YELLOW}    Installez l'un des suivants :${NC}"
    echo -e "${GREY}    - sudo apt install facedetect${NC}"
    echo -e "${GREY}    - sudo apt install python3-opencv${NC}"
    echo ""
    echo -e "${YELLOW}Détection des visages annulée.${NC}"
    rmdir "$FACES_DIR" 2>/dev/null
    exit 1
fi

# --- Sélection des images ---
# Scalpel sélectionne les images de plus de 8192 px² (trop petites = pas
# fiable pour la détection de visages). Comme on n'a pas toujours la surface
# exacte, on se base sur la taille du fichier (> 8 Ko) comme proxy, et on
# limite à 2048 fichiers pour les performances (comme Scalpel).
echo ""
echo -e "${BLUE}=== Sélection des images candidates ===${NC}"
MIN_FILESIZE=8192  # 8 Ko minimum
MAX_FILES=2048

# Extraire les chemins des images de la liste TSV
# Format : chemin<TAB>mime<TAB>taille
ALL_IMAGES=$(cut -f1 "$IMAGE_LIST" 2>/dev/null | grep -v '^$' || true)
TOTAL_CANDIDATES=$(echo "$ALL_IMAGES" | grep -c '.' 2>/dev/null || echo 0)

# Filtrer par taille de fichier
SELECTED=""
count=0
while IFS= read -r img; do
    [ -z "$img" ] && continue
    [ -f "$img" ] || continue
    fsize=$(stat -c%s "$img" 2>/dev/null || echo 0)
    if [ "$fsize" -ge "$MIN_FILESIZE" ]; then
        SELECTED="${SELECTED}${img}"$'\n'
        count=$((count + 1))
        [ "$count" -ge "$MAX_FILES" ] && break
    fi
done <<< "$ALL_IMAGES"

if [ "$count" -eq 0 ]; then
    echo -e "${YELLOW}⚠️  Aucune image candidate (trop petites ou absentes).${NC}"
    rmdir "$FACES_DIR" 2>/dev/null
    exit 0
fi

echo -e "${GREEN}✅ ${count} image(s) candidate(s) sélectionnée(s) sur ${TOTAL_CANDIDATES}.${NC}"
echo ""

# --- Détection des visages ---
echo -e "${BLUE}=== Recherche des visages ===${NC}"
echo -e "${GREY}(la recherche porte uniquement sur les visages dégagés et de face)${NC}"
echo ""

FACES_FOUND=0
FACES_LIST="$FACES_DIR/.faces_${STAMP}.txt"
: > "$FACES_LIST"

if [ "$DETECT_METHOD" = "facedetect" ]; then
    # Méthode 1 : facedetect (wrapper OpenCV en ligne de commande)
    while IFS= read -r img; do
        [ -z "$img" ] && [ ! -f "$img" ] && continue
        # facedetect sort une ligne par visage (ou rien si aucun)
        result=$(facedetect "$img" 2>/dev/null | grep -E '^[0-9]+' || true)
        if [ -n "$result" ]; then
            echo "$img" >> "$FACES_LIST"
            FACES_FOUND=$((FACES_FOUND + 1))
            echo -e "  ${GREEN}✅${NC} ${GREY}$(basename "$img")${NC}"
        fi
    done <<< "$SELECTED"
else
    # Méthode 2 : python3 + OpenCV (cv2)
    # On passe la liste des images à un script Python qui fait la détection
    SELECTED_FILE="$FACES_DIR/.selected_${STAMP}.txt"
    echo -n "$SELECTED" > "$SELECTED_FILE"
    python3 - "$SELECTED_FILE" "$FACES_LIST" <<'PYEOF' || ERRORS=$((ERRORS+1))
import sys
import os
import cv2

# Classifieur Haar en cascade pour la détection des visages (de face)
cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
if not os.path.exists(cascade_path):
    sys.exit(1)
face_cascade = cv2.CascadeClassifier(cascade_path)

selected_file = sys.argv[1]
faces_list = sys.argv[2]

found = 0
with open(selected_file) as f:
    images = [l.strip() for l in f if l.strip()]

for img_path in images:
    if not os.path.exists(img_path):
        continue
    try:
        # cv2 ne lit pas les fichiers avec caractères spéciaux ; utiliser imread
        img = cv2.imread(img_path)
        if img is None:
            continue
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
        )
        if len(faces) > 0:
            with open(faces_list, "a") as out:
                out.write(img_path + "\n")
            found += 1
            print("  \033[92m✅\033[0m \033[90m" + os.path.basename(img_path) + "\033[0m")
    except Exception:
        continue

print(f"\n\033[92m✅ {found} image(s) avec visage(s) détectée(s).\033[0m")
PYEOF
    FACES_FOUND=$(grep -c '.' "$FACES_LIST" 2>/dev/null || echo 0)
fi

# --- Résultats de la détection ---
echo ""
echo -e "${BLUE}=== Résultats de la détection ===${NC}"
if [ "$FACES_FOUND" -gt 0 ]; then
    echo -e "${GREEN}✅ ${FACES_FOUND} image(s) avec visage(s) détectée(s).${NC}"
    echo ""
    echo -e "${GREY}⚠️  CERTAINES IMAGES POURRAIENT ÊTRE CHOQUANTES${NC}"
else
    echo -e "${YELLOW}⚠️  Aucun visage n'a été découvert.${NC}"
fi

# --- Copie optionnelle des fichiers avec visages ---
if [ "$FACES_FOUND" -gt 0 ] && [ -n "$COPY_TO" ]; then
    echo ""
    echo -e "${BLUE}=== Copie des fichiers avec visages ===${NC}"
    if [ ! -d "$COPY_TO" ]; then
        mkdir -p "$COPY_TO" 2>/dev/null || {
            echo -e "${RED}❌ Impossible de créer le dossier de destination : ${COPY_TO}${NC}"
            ERRORS=$((ERRORS + 1))
        }
    fi
    if [ -d "$COPY_TO" ]; then
        COPIED=0
        while IFS= read -r img; do
            [ -z "$img" ] && continue
            [ -f "$img" ] || continue
            if cp -p "$img" "$COPY_TO/$(basename "$img")" 2>/dev/null; then
                COPIED=$((COPIED + 1))
            fi
        done < "$FACES_LIST"
        echo -e "${GREEN}✅ ${COPIED} fichier(s) copié(s) vers : ${COPY_TO}${NC}"
    fi
fi

# --- Génération du JSON de résultats (faces_result.json) ---
FACES_JSON="$OUTPUT_DIR/faces_result.json"
if command -v jq >/dev/null 2>&1; then
    FACES_ARRAY=$(while IFS= read -r img; do
        [ -z "$img" ] && continue
        printf '%s\n' "$img"
    done < "$FACES_LIST" | jq -R . | jq -s .)
    [ -z "$FACES_ARRAY" ] && FACES_ARRAY="[]"
    jq -n         --argjson faces_count "$FACES_FOUND"         --argjson faces_files "$FACES_ARRAY"         --argjson faces_available "true"         --arg faces_dir "$FACES_DIR"         '{faces_count:$faces_count, faces_files:$faces_files,
          faces_available:$faces_available, faces_dir:$faces_dir}'         > "$FACES_JSON" 2>/dev/null || true
else
    # Fallback sans jq
    FACES_ARRAY=$(while IFS= read -r img; do
        [ -z "$img" ] && continue
        printf '"%s",' "$(echo "$img" | sed 's/"/\\"/g; s/\\/\\\\/g')"
    done < "$FACES_LIST" | sed 's/,$//')
    [ -z "$FACES_ARRAY" ] && FACES_ARRAY=""
    cat > "$FACES_JSON" <<EOFJSON
{"faces_count":$FACES_FOUND,"faces_files":[$FACES_ARRAY],"faces_available":true,"faces_dir":"$FACES_DIR"}
EOFJSON
fi

# --- Nettoyage ---
rm -f "$FACES_DIR/.faces_${STAMP}.txt" "$FACES_DIR/.selected_${STAMP}.txt" 2>/dev/null || true

if [ "$ERRORS" -gt 0 ]; then
    exit 1
fi
exit 0
