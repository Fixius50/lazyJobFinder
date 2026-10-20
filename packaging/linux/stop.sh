#!/usr/bin/env bash
# =============================================================================
# Detención de lazyJobFinder para Linux
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "====================================================================="
echo "              lazyJobFinder - Deteniendo Servicios"
echo "====================================================================="

if ! docker info &>/dev/null; then
    echo "[ERROR] El daemon de Docker no está accesible o no se tienen permisos."
    exit 1
fi

if docker compose stop; then
    echo "[OK] Servicios detenidos ordenadamente."
    exit 0
else
    echo "[ERROR] Falló la detención de los servicios con docker compose stop."
    exit 1
fi
