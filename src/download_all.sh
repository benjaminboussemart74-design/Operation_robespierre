#!/usr/bin/env bash
# Télécharge et structure toutes les données de l'AN pour le pipeline.
# À exécuter depuis ta machine locale.
#
# Usage : bash src/download_all.sh

set -e
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# ── 1. Réunions (agenda 17e législature) ─────────────────────────────────────
echo "[1/3] Téléchargement des réunions (Agenda.json.zip)..."
mkdir -p "$REPO_DIR/Réunions"
curl -L --progress-bar \
  "https://data.assemblee-nationale.fr/static/openData/repository/17/vp/reunions/Agenda.json.zip" \
  -o /tmp/Agenda.json.zip
unzip -o /tmp/Agenda.json.zip -d "$REPO_DIR/Réunions/"
echo "[OK] Réunions extraites dans $REPO_DIR/Réunions/"

# ── 2. Comptes rendus commission cenum (vulnérabilités numériques) ────────────
echo ""
echo "[2/3] Téléchargement des CR de la commission cenum..."
BASE_CR="https://www.assemblee-nationale.fr/dyn/17/comptes-rendus/cenum"
OUT_CR="$REPO_DIR/Compte rendu/cenum"
mkdir -p "$OUT_CR"

for i in $(seq 1 40); do
    NUM=$(printf "%03d" $i)
    URL="${BASE_CR}/l17cenum2526${NUM}_compte-rendu"
    OUT="$OUT_CR/l17cenum2526${NUM}.html"

    HTTP=$(curl -s -o "$OUT" -w "%{http_code}" \
        -H "User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36" \
        -H "Accept-Language: fr-FR,fr;q=0.9" \
        --max-time 30 "$URL")

    if [ "$HTTP" = "200" ]; then
        echo "  [OK] CR n°$i"
    elif [ "$HTTP" = "404" ]; then
        rm -f "$OUT"
        echo "  [FIN] CR n°$i introuvable — fin de liste"
        break
    else
        rm -f "$OUT"
        echo "  [SKIP] CR n°$i — HTTP $HTTP"
    fi
    sleep 1
done

# ── 3. Lancer l'extraction ────────────────────────────────────────────────────
echo ""
echo "[3/3] Lancement du pipeline d'extraction..."
cd "$REPO_DIR/src"
python3 parse_reunions.py
python3 parse_cenum.py
python3 run.py
echo ""
echo "Terminé. Résultats dans $REPO_DIR/results/"
