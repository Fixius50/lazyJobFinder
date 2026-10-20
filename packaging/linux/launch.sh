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

# 1. Comprobar Docker y conectividad con el daemon
if ! command -v docker &>/dev/null; then
    echo "[ERROR] Docker no está instalado o no se encuentra en el PATH."
    exit 1
fi

if ! docker info &>/dev/null; then
    echo "[ERROR] El daemon de Docker no está en ejecución o el usuario no tiene permisos."
    echo "Asegúrate de que el servicio 'docker' esté activo (sudo systemctl start docker)."
    exit 1
fi

# 2. Comprobar y preparar .env garantizando COMPOSE_PROJECT_NAME
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp ".env.example" ".env"
        RAND_SUFFIX="$(head /dev/urandom | tr -dc a-z0-9 | head -c 6 || echo $RANDOM)"
        echo "" >> ".env"
        echo "# Identificador único de proyecto Compose" >> ".env"
        echo "COMPOSE_PROJECT_NAME=lazyjob_${RAND_SUFFIX}" >> ".env"
        echo "[i] Archivo .env inicializado con proyecto único."
    else
        echo "[ERROR] No se encontró el archivo .env ni .env.example."
        exit 1
    fi
else
    # Validar que .env contenga una variable COMPOSE_PROJECT_NAME no vacía
    CURRENT_PROJ="$(grep -E '^COMPOSE_PROJECT_NAME=' .env | cut -d '=' -f2- | tr -d ' "''' || true)"
    if [ -z "$CURRENT_PROJ" ]; then
        RAND_SUFFIX="$(head /dev/urandom | tr -dc a-z0-9 | head -c 6 || echo $RANDOM)"
        echo "" >> ".env"
        echo "# Identificador único de proyecto Compose incorporado" >> ".env"
        echo "COMPOSE_PROJECT_NAME=lazyjob_${RAND_SUFFIX}" >> ".env"
        echo "[i] COMPOSE_PROJECT_NAME incorporado a .env existente."
    fi
fi

# 3. Cargar imágenes si no están presentes
if ! docker compose images -q 2>/dev/null | grep -q .; then
    if [ -f "images.tar" ]; then
        echo "--> Importando imágenes de contenedores desde images.tar..."
        if ! docker load -i "images.tar"; then
            echo "[ERROR] Falló la importación de imágenes desde images.tar."
            exit 1
        fi
        echo "[OK] Imágenes importadas correctamente."
    else
        echo "[ERROR] No se encontraron imágenes en Docker ni existe 'images.tar' para importarlas."
        echo "Asegúrate de ejecutar el instalador (./installer.sh) antes de lanzar el sistema."
        exit 1
    fi
fi

# 4. Levantar contenedores
echo "--> Iniciando servicios con Docker Compose..."
if ! docker compose up -d; then
    echo "[ERROR] Falló el inicio de los contenedores Docker."
    exit 1
fi

# 5. Esperar al backend
echo "--> Esperando a que el panel responda en http://127.0.0.1:8000..."
RETRY=0
MAX_RETRIES=30
APP_READY=0
while [ $RETRY -lt $MAX_RETRIES ]; do
    if curl -s -f --connect-timeout 2 --max-time 3 http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
        APP_READY=1
        break
    fi
    RETRY=$((RETRY+1))
    echo "    Esperando a la API... [$RETRY/$MAX_RETRIES]"
    sleep 2
done

if [ $APP_READY -ne 1 ]; then
    echo "[ERROR] La API de lazyJobFinder no respondió tras 60s."
    echo "Consulta los registros con: docker compose logs"
    exit 1
fi

# 6. Comprobar modelo de Ollama
echo "--> Verificando disponibilidad del modelo de IA..."
if ! docker compose exec -T ollama ollama list 2>/dev/null | grep -qi "qwen2.5:3b-instruct"; then
    echo "--> Descargando modelo qwen2.5:3b-instruct en Ollama..."
    if ! docker compose exec -T ollama ollama pull qwen2.5:3b-instruct; then
        echo "[ERROR] Falló la descarga del modelo en Ollama."
        exit 1
    fi
fi

# Doble comprobación de que el modelo está efectivamente disponible
if ! docker compose exec -T ollama ollama list 2>/dev/null | grep -qi "qwen2.5:3b-instruct"; then
    echo "[ERROR] El modelo qwen2.5:3b-instruct no está listo en Ollama."
    exit 1
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

