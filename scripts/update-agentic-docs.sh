#!/usr/bin/env bash
#
# update-agentic-docs.sh — Analiza cambios en código fuente y sugiere o ejecuta
# la actualización de la documentación agéntica en .cursor/
#
# Modos:
#   --check     Solo reporta qué docs necesitan actualización (no modifica nada)
#   --auto      Ejecuta la actualización automática (solo cambios leves)
#   (sin flags) Modo interactivo: pregunta al usuario

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
BASE_REF="${BASE_REF:-HEAD~1}"

MODE="${1:-}"
CURSOR_DIR="$ROOT/.cursor"

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "============================================"
echo "  WebTranslatorr — Agentic Docs Updater"
echo "============================================"
echo ""

# Obtener archivos cambiados
CHANGED_FILES=$(git diff --name-only "$BASE_REF" 2>/dev/null | grep -E '(app/|config\.py|main\.py|Dockerfile|docker-compose\.yml)' || true)

if [ -z "$CHANGED_FILES" ]; then
    echo "No source file changes detected since $BASE_REF."
    echo "Documentation is up to date."
    exit 0
fi

echo "Changed source files:"
echo "$CHANGED_FILES" | while read -r f; do echo "  - $f"; done
echo ""

# Clasificar cambios
CLASSIFY_OUTPUT=$(python "$SCRIPT_DIR/classify_changes.py" --base "$BASE_REF" --json 2>/dev/null || echo '{"severity":"unknown"}')
SEVERITY=$(echo "$CLASSIFY_OUTPUT" | python -c "import sys,json; d=json.load(sys.stdin); print(d['severity'])" 2>/dev/null || echo "unknown")
DOCS_NEEDED=$(echo "$CLASSIFY_OUTPUT" | python -c "import sys,json; d=json.load(sys.stdin); print('true' if d.get('docs_update_required') else 'false')" 2>/dev/null || echo "false")
AFFECTED_DOCS=$(echo "$CLASSIFY_OUTPUT" | python -c "import sys,json; d=json.load(sys.stdin); print('\n'.join(d.get('affected_docs',[])))" 2>/dev/null || echo "")

echo "Change severity: $SEVERITY"
echo "Docs update needed: $DOCS_NEEDED"

if [ -n "$AFFECTED_DOCS" ]; then
    echo ""
    echo "Documents that may need updating:"
    echo "$AFFECTED_DOCS" | while read -r doc; do
        if [ -n "$doc" ]; then
            echo "  - $CURSOR_DIR/$doc"
        fi
    done
fi

echo ""

if [ "$MODE" = "--check" ]; then
    if [ "$DOCS_NEEDED" = "true" ]; then
        echo -e "${YELLOW}Documentation update required. Run without --check to proceed.${NC}"
        exit 1
    else
        echo -e "${GREEN}No documentation update needed.${NC}"
        exit 0
    fi
elif [ "$MODE" = "--auto" ]; then
    if [ "$SEVERITY" = "low" ] || [ "$SEVERITY" = "cosmetic" ]; then
        echo "Minor changes detected. Auto-update safe."
        echo -e "${GREEN}Documentation considered up to date for minor changes.${NC}"
        exit 0
    else
        echo -e "${RED}Significant changes detected (severity: $SEVERITY). Auto-update not possible.${NC}"
        echo "Please manually review and update the affected documents."
        echo ""
        echo "Run validation: python scripts/validate_docs.py --strict"
        exit 1
    fi
else
    echo "Validation:"
    python "$SCRIPT_DIR/validate_docs.py"
    echo ""
    echo -e "${YELLOW}Please review the affected documents manually and update as needed.${NC}"
fi
