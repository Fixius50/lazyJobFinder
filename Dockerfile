# =============================================================================
# Dockerfile para lazyJobFinder (Debian GNU/Linux 12 'Bookworm' Slim + Python 3.11)
# =============================================================================
# Base Linux oficial ultra-optimizada para inferencia nativa en CPU y bajo consumo de memoria.

FROM python:3.11-slim-bookworm

# Evitar prompts interactivos, buffers y optimizar subprocesos CPU
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPYCACHEPREFIX=/app/src/__pycache__ \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    OMP_NUM_THREADS=4 \
    MKL_NUM_THREADS=4

WORKDIR /app

# Instalar dependencias del sistema mínimas necesarias (curl para healthcheck, ca-certificates)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código fuente y el frontend compilado
COPY src/ /app/src/
COPY web/out/ /app/web/out/

# Crear directorios para persistencia de datos y documentos
RUN mkdir -p /app/data/documents

# Definir volumen para persistir la base de datos y los documentos
VOLUME ["/app/data"]

# Comprobación de salud básica del contenedor (vía API HTTP para no competir por bloqueos en SQLite)
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/docs', timeout=5)" || exit 1

# Comando por defecto: arrancar el orquestador principal
CMD ["python", "-m", "src.main"]
