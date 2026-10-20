#!/usr/bin/env bash
# =============================================================================
# Asistente de Instalación de lazyJobFinder para Linux (x64)
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=====================================================================${NC}"
echo -e "${BLUE}          lazyJobFinder - Instalador para GNU/Linux (x64)             ${NC}"
echo -e "${BLUE}    Inferencia IA Local y Privada para Búsqueda Autónoma de Empleo    ${NC}"
echo -e "${BLUE}=====================================================================${NC}\n"

# 1. Comprobar Docker Engine
if ! command -v docker &> /dev/null; then
    echo -e "${RED}[ERROR] Docker no está instalado en este sistema.${NC}"
    echo "Instala Docker Engine siguiendo la guía oficial:"
    echo "https://docs.docker.com/engine/install/"
    exit 1
fi

# 2. Comprobar Docker Compose v2
if ! docker compose version &> /dev/null; then
    echo -e "${RED}[ERROR] El plugin de Docker Compose (v2) no está disponible.${NC}"
    echo "Instálalo con: sudo apt install docker-compose-plugin (en Debian/Ubuntu)"
    exit 1
fi

# 3. Comprobar permisos del usuario en Docker (Requisito obligatorio)
if ! docker info &> /dev/null; then
    echo -e "${RED}[ERROR] El usuario actual ($USER) no tiene acceso al daemon de Docker.${NC}"
    echo "Para otorgar permisos a tu usuario sin requerir sudo constante, ejecuta:"
    echo "  sudo usermod -aG docker $USER"
    echo "  newgrp docker"
    echo "A continuación, vuelve a ejecutar este instalador."
    exit 1
fi

# 4. Determinar directorio de instalación
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ "$EUID" -eq 0 ]; then
    INSTALL_DIR="/opt/lazyJobFinder"
    BIN_DIR="/usr/local/bin"
    APP_DIR="/usr/share/applications"
else
    INSTALL_DIR="$HOME/.local/share/lazyJobFinder"
    BIN_DIR="$HOME/.local/bin"
    APP_DIR="$HOME/.local/share/applications"
fi

echo -e "${GREEN}[i] Directorio de destino: $INSTALL_DIR${NC}"
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/data/uploaded_cvs"
mkdir -p "$INSTALL_DIR/data/documents"
mkdir -p "$INSTALL_DIR/config"
mkdir -p "$BIN_DIR"
mkdir -p "$APP_DIR"

# 5. Copiar archivos de la distribución
echo -e "${GREEN}[i] Copiando componentes del sistema...${NC}"
cp -f "$SCRIPT_DIR/docker-compose.yml" "$INSTALL_DIR/"
cp -f "$SCRIPT_DIR/launch.sh" "$INSTALL_DIR/"
cp -f "$SCRIPT_DIR/stop.sh" "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/launch.sh" "$INSTALL_DIR/stop.sh"

if [ ! -f "$INSTALL_DIR/.env" ]; then
    cp -f "$SCRIPT_DIR/.env.example" "$INSTALL_DIR/.env"
fi

# Copiar plantillas sin sobreescribir configuraciones existentes
for f in settings.yaml profile.yaml shared_constants.json; do
    if [ ! -f "$INSTALL_DIR/config/$f" ] && [ -f "$SCRIPT_DIR/config-templates/$f" ]; then
        cp -f "$SCRIPT_DIR/config-templates/$f" "$INSTALL_DIR/config/$f"
    fi
done

# 6. Importar imágenes si images.tar existe
if [ -f "$SCRIPT_DIR/images.tar" ]; then
    echo -e "${GREEN}[i] Importando imágenes de contenedores locales (lazyjobfinder y ollama)...${NC}"
    if ! docker load -i "$SCRIPT_DIR/images.tar"; then
        echo -e "${RED}[ERROR] Fallo al cargar las imágenes de images.tar.${NC}"
        exit 1
    fi
fi

# 6.1 Restaurar modelo de IA en el volumen de Ollama si ollama_model.tar.gz existe
if [ -f "$SCRIPT_DIR/ollama_model.tar.gz" ]; then
    echo -e "${GREEN}[i] Restaurando modelo de IA empaquetado en el volumen de Ollama...${NC}"
    cd "$INSTALL_DIR"
    docker compose up --no-start ollama >/dev/null 2>&1 || true
    if ! docker compose run --rm --entrypoint /bin/sh -v "$SCRIPT_DIR":/backup ollama -c "tar xzf /backup/ollama_model.tar.gz -C /root/.ollama"; then
        echo -e "${RED}[ERROR] No se pudo restaurar el modelo de IA en el volumen de Ollama.${NC}"
        exit 1
    fi
    echo -e "${GREEN}[OK] Modelo IA precargado en el volumen local de Ollama.${NC}"
fi

# 7. Crear enlace en PATH
ln -sf "$INSTALL_DIR/launch.sh" "$BIN_DIR/lazyjobfinder"
echo -e "${GREEN}[OK] Comando ejecutable creado en: $BIN_DIR/lazyjobfinder${NC}"

# 8. Crear lanzador de escritorio (.desktop)
DESKTOP_FILE="$APP_DIR/lazyjobfinder.desktop"
cat <<EOF > "$DESKTOP_FILE"
[Desktop Entry]
Version=1.0
Type=Application
Name=lazyJobFinder
Comment=Búsqueda local de empleo con IA y Telegram
Exec=$BIN_DIR/lazyjobfinder
Terminal=true
Categories=Office;Utility;Development;
EOF
chmod +x "$DESKTOP_FILE"

# También en el Escritorio si existe la carpeta Desktop
if [ -d "$HOME/Desktop" ]; then
    cp -f "$DESKTOP_FILE" "$HOME/Desktop/"
    chmod +x "$HOME/Desktop/lazyjobfinder.desktop" || true
fi

echo -e "\n${BLUE}=====================================================================${NC}"
echo -e "${GREEN}           ¡Instalación completada correctamente!                    ${NC}"
echo -e "${BLUE}=====================================================================${NC}"
echo "Puedes iniciar lazyJobFinder en cualquier momento ejecutando:"
echo -e "  ${YELLOW}lazyjobfinder${NC}"
echo "o desde el lanzador de aplicaciones de tu entorno de escritorio."
echo ""
read -p "¿Deseas iniciar lazyJobFinder ahora? [S/n]: " START_APP
if [[ ! "$START_APP" =~ ^[nN]$ ]]; then
    exec "$INSTALL_DIR/launch.sh"
fi
