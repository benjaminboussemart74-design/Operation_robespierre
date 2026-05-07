#!/usr/bin/env bash
# Télécharge les comptes rendus de la commission d'enquête sur les
# vulnérabilités numériques (cenum, session 2025-2026).
# À exécuter depuis une machine avec accès internet non restreint.

BASE_URL="https://www.assemblee-nationale.fr/dyn/17/comptes-rendus/cenum"
OUT_DIR="$(dirname "$0")/../Compte rendu/cenum"
MAX_CR=30   # on tente jusqu'au n°30, les 404 sont ignorés

mkdir -p "$OUT_DIR"

for i in $(seq -w 1 $MAX_CR); do
    NUM=$(printf "%03d" $i)
    URL="${BASE_URL}/l17cenum2526${NUM}_compte-rendu"
    OUT_HTML="${OUT_DIR}/l17cenum2526${NUM}.html"
    OUT_PDF="${OUT_DIR}/l17cenum2526${NUM}.pdf"

    # HTML
    HTTP=$(curl -s -o "$OUT_HTML" -w "%{http_code}" \
        -H "User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36" \
        -H "Accept: text/html,application/xhtml+xml" \
        -H "Accept-Language: fr-FR,fr;q=0.9" \
        --max-time 30 \
        "$URL")

    if [ "$HTTP" = "200" ]; then
        echo "[OK] CR n°$i — HTML"
        # PDF
        curl -s -o "$OUT_PDF" \
            -H "User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36" \
            --max-time 30 \
            "${URL}.pdf" 2>/dev/null
    elif [ "$HTTP" = "404" ]; then
        rm -f "$OUT_HTML"
        echo "[STOP] CR n°$i — 404, fin de liste"
        break
    else
        rm -f "$OUT_HTML"
        echo "[SKIP] CR n°$i — HTTP $HTTP"
    fi

    sleep 1  # politesse
done

echo ""
echo "Téléchargement terminé. Fichiers dans : $OUT_DIR"
echo "Lance ensuite : cd src && python parse_cenum.py"
