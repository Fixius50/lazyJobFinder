"""Módulo de almacenamiento y resolución de rutas de lazyJobFinder.

Centraliza la arquitectura de persistencia y rutas entre 'src/' y 'data/',
garantizando:
1. Una única fuente de verdad para todas las rutas del proyecto (DB, secretos, CVs, docs).
2. Compatibilidad transparente entre entornos locales (Windows / Linux) y Docker (/app).
3. Centralización de la caché de bytecode de Python (sys.pycache_prefix).
4. Persistencia desacoplada y atómica de secretos locales (data/secrets.json).
5. Gestión del puntero de CV activo (data/active_cv.json).
6. Salvaguardas unificadas contra vulnerabilidades de Directory / Path Traversal.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from typing import Any, Dict, Optional

logger = logging.getLogger("lazyJobFinder.storage")

# =============================================================================
# 1. RESOLUCIÓN DE DIRECTORIOS RAÍZ
# =============================================================================

# Directorio raíz del repositorio o contenedor (/app o raíz del proyecto)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Directorios principales (personalizables mediante variables de entorno)
DATA_DIR = os.getenv("DATA_DIR", os.path.join(PROJECT_ROOT, "data"))
CONFIG_DIR = os.getenv("CONFIG_DIR", os.path.join(PROJECT_ROOT, "config"))
CACHE_DIR = os.getenv("PYTHONPYCACHEPREFIX", os.path.join(PROJECT_ROOT, ".cache", "pycache"))
WEB_OUT_DIR = os.getenv("WEB_OUT_DIR", os.path.join(PROJECT_ROOT, "web", "out"))

# Subdirectorios de datos persistentes
DOCUMENTS_DIR = os.getenv("DOCUMENTS_DIR", os.path.join(DATA_DIR, "documents"))
UPLOAD_DIR = os.getenv("UPLOAD_DIR", os.path.join(DATA_DIR, "uploaded_cvs"))

# Archivos de datos persistentes
DB_PATH = os.getenv("DATABASE_PATH", os.path.join(DATA_DIR, "lazyjobfinder.db"))
SECRETS_FILE = os.getenv("SECRETS_FILE", os.path.join(DATA_DIR, "secrets.json"))
ACTIVE_CV_FILE = os.getenv("ACTIVE_CV_FILE", os.path.join(DATA_DIR, "active_cv.json"))

# Archivos de configuración estática y plantillas del usuario
SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.yaml")
PROFILE_FILE = os.path.join(CONFIG_DIR, "profile.yaml")
BASE_CV_FILE = os.path.join(CONFIG_DIR, "cv_base.md")
CONSTANTS_FILE = os.path.join(CONFIG_DIR, "shared_constants.json")


# =============================================================================
# 2. CENTRALIZACIÓN DE BYTECODE PYTHON (__pycache__)
# =============================================================================

def setup_pycache_centralization(cache_dir: Optional[str] = None) -> str:
    """Configura sys.pycache_prefix para agrupar todos los .pyc en una carpeta única.
    
    Evita la dispersión de subcarpetas __pycache__ en src/, packaging/, scripts/, etc.
    """
    target = cache_dir or CACHE_DIR
    try:
        os.makedirs(target, exist_ok=True)
        if getattr(sys, "pycache_prefix", None) != target:
            sys.pycache_prefix = target
            os.environ["PYTHONPYCACHEPREFIX"] = target
    except Exception as exc:
        logger.debug("No se pudo fijar sys.pycache_prefix a %s: %s", target, exc)
    return target


# =============================================================================
# 3. CICLO DE VIDA E INICIALIZACIÓN DE DIRECTORIOS
# =============================================================================

def ensure_storage_dirs() -> None:
    """Crea de forma idempotente las carpetas necesarias en data/ y .cache/."""
    for folder in (DATA_DIR, DOCUMENTS_DIR, UPLOAD_DIR, CACHE_DIR):
        try:
            os.makedirs(folder, exist_ok=True)
        except Exception as exc:
            logger.warning("Error creando directorio de almacenamiento %s: %s", folder, exc)


# =============================================================================
# 4. GESTIÓN DE SECRETOS PERSISTENTES (data/secrets.json)
# =============================================================================

def read_persisted_secrets() -> Dict[str, str]:
    """Lee las credenciales privadas almacenadas en el volumen persistente (data/secrets.json)."""
    if not os.path.exists(SECRETS_FILE):
        return {}
    try:
        with open(SECRETS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items() if v is not None}
            return {}
    except Exception as exc:
        logger.warning("No se pudo leer data/secrets.json: %s", exc)
        return {}


def get_secret(key: str, default: str = "") -> str:
    """Recupera un secreto con orden de precedencia: 1) data/secrets.json, 2) os.environ, 3) default."""
    persisted = read_persisted_secrets()
    val = persisted.get(key)
    if val:
        return str(val).strip()
    env_val = os.getenv(key)
    if env_val:
        return env_val.strip()
    return default


def save_persisted_secret(key: str, value: str) -> None:
    """Guarda o actualiza un secreto en data/secrets.json de manera atómica."""
    ensure_storage_dirs()
    data = read_persisted_secrets()
    data[key] = value

    tmp_file = f"{SECRETS_FILE}.tmp.{os.getpid()}"
    try:
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_file, SECRETS_FILE)
    except Exception as exc:
        if os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except OSError:
                pass
        logger.error("No se pudo escribir atómicamente en data/secrets.json: %s", exc)
        raise


def delete_persisted_secret(key: str) -> None:
    """Elimina una credencial de data/secrets.json."""
    data = read_persisted_secrets()
    if key in data:
        data.pop(key, None)
        tmp_file = f"{SECRETS_FILE}.tmp.{os.getpid()}"
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_file, SECRETS_FILE)
        except Exception as exc:
            if os.path.exists(tmp_file):
                try:
                    os.remove(tmp_file)
                except OSError:
                    pass
            logger.error("No se pudo actualizar data/secrets.json al eliminar clave: %s", exc)
            raise


def sync_secrets_to_env() -> None:
    """Sincroniza los secretos persistentes en os.environ al arrancar la aplicación."""
    persisted = read_persisted_secrets()
    for k, v in persisted.items():
        if v:
            os.environ[k] = str(v)
    if persisted:
        logger.info(
            "Credenciales persistentes sincronizadas correctamente desde data/secrets.json (%d claves).",
            len(persisted),
        )


# =============================================================================
# 5. GESTIÓN DEL PUNTERO DE CV ACTIVO (data/active_cv.json)
# =============================================================================

def read_active_cv_pointer() -> Dict[str, Any]:
    """Lee el puntero del CV activo desde data/active_cv.json."""
    if not os.path.exists(ACTIVE_CV_FILE):
        return {"selected_filename": "none"}
    try:
        with open(ACTIVE_CV_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception as exc:
        logger.debug("Error leyendo active_cv.json: %s", exc)
    return {"selected_filename": "none"}


def write_active_cv_pointer(filename: str) -> None:
    """Escribe de manera atómica la selección del CV activo en data/active_cv.json."""
    ensure_storage_dirs()
    payload = {
        "selected_filename": filename,
        "updated_at": time.time(),
    }
    tmp_file = f"{ACTIVE_CV_FILE}.tmp.{os.getpid()}"
    try:
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        os.replace(tmp_file, ACTIVE_CV_FILE)
    except Exception as exc:
        if os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except OSError:
                pass
        logger.error("Error guardando active_cv.json: %s", exc)
        raise


def resolve_active_cv_path() -> Optional[str]:
    """Resuelve la ruta absoluta del CV activo si existe físicamente en data/uploaded_cvs/."""
    pointer = read_active_cv_pointer()
    selected = pointer.get("selected_filename", "none")
    if not selected or selected in ("none", "Ninguno", "default"):
        return None

    clean_name = os.path.basename(selected)
    candidate = os.path.join(UPLOAD_DIR, clean_name)
    if os.path.isfile(candidate):
        return candidate
    return None


# =============================================================================
# 6. SEGURIDAD CONTRA PATH TRAVERSAL
# =============================================================================

def is_safe_path(target_path: str, base_dir: Optional[str] = None) -> bool:
    """Verifica si target_path reside estrictamente dentro de base_dir (por defecto PROJECT_ROOT)."""
    if not target_path:
        return False
    try:
        root_dir = os.path.realpath(base_dir or PROJECT_ROOT)
        resolved = os.path.realpath(target_path)
        return resolved == root_dir or resolved.startswith(root_dir + os.sep)
    except Exception:
        return False
