#!/usr/bin/env bash
# =============================================================================
# Detención de lazyJobFinder para Linux
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "====================================================================="
echo "              lazyJobFinder - Deteniendo Servicios"
echo "====================================================================="

docker compose stop
echo "[OK] Servicios detenidos ordenadamente."
