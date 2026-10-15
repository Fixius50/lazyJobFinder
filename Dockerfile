# =============================================================================
# Dockerfile para lazyJobFinder (Python 3.11 Slim)
# =============================================================================

FROM python:3.11-slim

# Evitar prompts interactivos y buffers de Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Instalar dependencias del sistema mínimas necesarias (curl para healthcheck, ca-certificates)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código fuente y las configuraciones base
COPY src/ /app/src/
COPY config/ /app/config/

# Crear directorios para persistencia de datos y documentos
RUN mkdir -p /app/data/documents

# Definir volúmenes para persistir la base de datos y la configuración personalizada
VOLUME ["/app/data", "/app/config"]

# Comprobación de salud básica del contenedor
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD python -c "import sqlite3; conn = sqlite3.connect('/app/data/lazyjobfinder.db'); conn.execute('SELECT 1'); conn.close()" || exit 1

# Comando por defecto: arrancar el orquestador principal
CMD ["python", "-m", "src.main"]
