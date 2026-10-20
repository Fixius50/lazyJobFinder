#!/usr/bin/env bash
# =============================================================================
# Lanzador de lazyJobFinder para Linux
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "====================================================================="
echo "               lazyJobFinder - Iniciando Aplicación"
echo "====================================================================="

# 1. Comprobar .env
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    cp ".env.example" ".env"
fi

# 2. Levantar contenedores
docker compose up -d

# 3. Esperar al backend
echo "--> Esperando a que el panel responda en http://127.0.0.1:8000..."
RETRY=0
while [ $RETRY -lt 30 ]; do
    if curl -s -f --connect-timeout 2 --max-time 3 http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
        break
    fi
    RETRY=$((RETRY+1))
    sleep 2
done

# 4. Comprobar modelo de Ollama
if ! docker exec lazyjob_ollama ollama list 2>/dev/null | grep -qi "qwen2.5:3b-instruct"; then
    echo "--> Descargando modelo qwen2.5:3b-instruct en Ollama..."
    docker exec lazyjob_ollama ollama pull qwen2.5:3b-instruct
fi

echo ""
echo "====================================================================="
echo "  [SISTEMA LISTO] lazyJobFinder está activo:"
echo "    - Panel Web:    http://localhost:8000"
echo "    - Motor Ollama: http://localhost:11434"
echo "====================================================================="
echo ""

# Abrir navegador si xdg-open está disponible
if command -v xdg-open &>/dev/null; then
    xdg-open "http://localhost:8000" &>/dev/null &
fi

echo "Para detener la aplicación, ejecuta: ./stop.sh"
echo "Pulsa [ENTER] para detener los servicios ahora..."
read -r
./stop.sh
