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
import threading
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
CONFIG_DIR = os.getenv("CONFIG_DIR", DATA_DIR)
CACHE_DIR = os.getenv("PYTHONPYCACHEPREFIX", os.path.join(PROJECT_ROOT, "src", "__pycache__"))
WEB_OUT_DIR = os.getenv("WEB_OUT_DIR", os.path.join(PROJECT_ROOT, "web", "out"))

# Subdirectorios de datos persistentes
DOCUMENTS_DIR = os.getenv("DOCUMENTS_DIR", os.path.join(DATA_DIR, "documents"))
UPLOAD_DIR = os.getenv("UPLOAD_DIR", os.path.join(DATA_DIR, "uploaded_cvs"))

# Base de datos unificada SQLite
DB_PATH = os.getenv("DATABASE_PATH", os.path.join(DATA_DIR, "lazyjobfinder.db"))

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    from pydantic import Field

    class AppSettings(BaseSettings):
        """Configuración y rutas fuertemente tipadas del entorno mediante pydantic-settings."""
        model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

        project_root: str = Field(default_factory=lambda: PROJECT_ROOT)
        data_dir: str = Field(default_factory=lambda: DATA_DIR)
        documents_dir: str = Field(default_factory=lambda: DOCUMENTS_DIR)
        upload_dir: str = Field(default_factory=lambda: UPLOAD_DIR)
        database_path: str = Field(default_factory=lambda: DB_PATH)
        ollama_base_url: str = Field(default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://ollama:11434"))
        ollama_model: str = Field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "qwen2.5:3b-instruct"))
        telegram_bot_token: str = Field(default="")
        telegram_allowed_user_id: int = Field(default=0)
except ImportError:
    AppSettings = None


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
# 4. GESTIÓN DE ESTADO Y SECRETOS EN SQLITE (lazyjobfinder.db -> app_state)
# =============================================================================

_storage_db: Optional[Any] = None
_storage_db_lock = threading.Lock()


def _get_storage_db() -> Any:
    """Retorna la instancia reutilizable de Database para operaciones de almacenamiento."""
    global _storage_db
    if _storage_db is None:
        with _storage_db_lock:
            if _storage_db is None:
                from .database import Database
                _storage_db = Database()
    return _storage_db


def _get_sqlite_state(key: str, default: Any = None) -> Any:
    """Lee un valor persistente de app_state en SQLite a través de la capa canónica Database."""
    try:
        return _get_storage_db().get_app_state(key, default=default)
    except Exception as e:
        logger.debug("Error leyendo app_state (%s) en SQLite: %s", key, e)
        return default


def _set_sqlite_state(key: str, value: Any) -> None:
    """Guarda un valor de app_state en SQLite de manera atómica a través de Database."""
    ensure_storage_dirs()
    _get_storage_db().set_app_state(key, value)


def read_persisted_secrets() -> Dict[str, str]:
    """Lee las credenciales privadas almacenadas en SQLite."""
    data = _get_sqlite_state("secrets")
    if data is not None and isinstance(data, dict):
        return {str(k): str(v) for k, v in data.items() if v is not None}
    return {}


def get_secret(key: str, default: str = "") -> str:
    """Recupera un secreto con orden de precedencia: 1) SQLite, 2) os.environ, 3) default."""
    persisted = read_persisted_secrets()
    val = persisted.get(key)
    if val:
        return str(val).strip()
    env_val = os.getenv(key)
    if env_val:
        return env_val.strip()
    return default


def save_persisted_secret(key: str, value: str) -> None:
    """Guarda o actualiza un secreto en SQLite."""
    data = read_persisted_secrets()
    data[key] = value
    _set_sqlite_state("secrets", data)


def delete_persisted_secret(key: str) -> None:
    """Elimina una credencial de SQLite."""
    data = read_persisted_secrets()
    if key in data:
        data.pop(key, None)
        _set_sqlite_state("secrets", data)


def sync_secrets_to_env() -> None:
    """Sincroniza los secretos persistentes en os.environ al arrancar la aplicación."""
    persisted = read_persisted_secrets()
    for k, v in persisted.items():
        if v:
            os.environ[k] = str(v)
    if persisted:
        logger.info(
            "Credenciales persistentes sincronizadas correctamente desde SQLite (%d claves).",
            len(persisted),
        )


# =============================================================================
# 5. GESTIÓN DEL PUNTERO DE CV ACTIVO EN SQLITE
# =============================================================================

def read_active_cv_pointer() -> Dict[str, Any]:
    """Lee el puntero del CV activo directamente desde la tabla app_state de SQLite."""
    data = _get_sqlite_state("active_cv_pointer")
    if data is not None and isinstance(data, dict):
        return data
    return {"selected_filename": "none"}


def write_active_cv_pointer(
    filename: str,
    search_terms: Optional[list] = None,
    primary_role: Optional[str] = None,
) -> None:
    """Escribe de manera atómica la selección del CV activo en SQLite con sus términos de búsqueda."""
    existing = read_active_cv_pointer()
    payload = {
        "selected_filename": filename,
        "updated_at": time.time(),
        "search_terms": search_terms if search_terms is not None else existing.get("search_terms", []),
        "primary_role": primary_role if primary_role is not None else existing.get("primary_role", ""),
    }
    _set_sqlite_state("active_cv_pointer", payload)


def get_persisted_settings() -> Dict[str, Any]:
    """Recupera la configuración del sistema desde la tabla app_state de SQLite."""
    import copy
    from .shared_constants import DEFAULT_SETTINGS
    data = _get_sqlite_state("settings")
    if data is not None and isinstance(data, dict):
        return data

    # Migración transparente desde settings.yaml legacy si existiese
    legacy_file = os.path.join(PROJECT_ROOT, "config", "settings.yaml")
    if os.path.exists(legacy_file):
        try:
            import yaml
            with open(legacy_file, "r", encoding="utf-8") as f:
                legacy = yaml.safe_load(f)
            if isinstance(legacy, dict) and legacy:
                _set_sqlite_state("settings", legacy)
                return legacy
        except Exception as exc:
            logger.debug("Error migrando settings.yaml a SQLite: %s", exc)

    return copy.deepcopy(DEFAULT_SETTINGS)


def save_persisted_settings(data: Dict[str, Any]) -> None:
    """Persiste la configuración del sistema directamente en SQLite."""
    _set_sqlite_state("settings", data)


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
