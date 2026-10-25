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
CONFIG_DIR = os.getenv("CONFIG_DIR", DATA_DIR)
CACHE_DIR = os.getenv("PYTHONPYCACHEPREFIX", os.path.join(PROJECT_ROOT, "src", "__pycache__"))
WEB_OUT_DIR = os.getenv("WEB_OUT_DIR", os.path.join(PROJECT_ROOT, "web", "out"))

# Subdirectorios de datos persistentes
DOCUMENTS_DIR = os.getenv("DOCUMENTS_DIR", os.path.join(DATA_DIR, "documents"))
UPLOAD_DIR = os.getenv("UPLOAD_DIR", os.path.join(DATA_DIR, "uploaded_cvs"))

# Archivos de datos persistentes
DB_PATH = os.getenv("DATABASE_PATH", os.path.join(DATA_DIR, "lazyjobfinder.db"))
SECRETS_FILE = os.getenv("SECRETS_FILE", os.path.join(DATA_DIR, "secrets.json"))
ACTIVE_CV_FILE = os.getenv("ACTIVE_CV_FILE", os.path.join(DATA_DIR, "active_cv.json"))

# Archivos de configuración y compatibilidad
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.yaml")
PROFILE_FILE = os.path.join(DATA_DIR, "profile.yaml")
BASE_CV_FILE = os.path.join(DATA_DIR, "cv_base.md")
CONSTANTS_FILE = os.path.join(DATA_DIR, "shared_constants.json")


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

def _get_sqlite_state(key: str, default: Any = None) -> Any:
    """Lee un valor persistente de app_state en SQLite (lazyjobfinder.db)."""
    import sqlite3
    if not os.path.exists(DB_PATH):
        return default
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='app_state'")
        if not cursor.fetchone():
            conn.close()
            return default
        cursor = conn.execute("SELECT value FROM app_state WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return default
        return json.loads(row["value"])
    except Exception as e:
        logger.debug("Error leyendo app_state (%s) en SQLite: %s", key, e)
        return default


def _set_sqlite_state(key: str, value: Any) -> None:
    """Guarda un valor de app_state en SQLite de manera atómica."""
    import sqlite3
    ensure_storage_dirs()
    val_str = json.dumps(value, ensure_ascii=False)
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT DEFAULT (datetime('now', 'localtime'))
            );
            """
        )
        conn.execute(
            """
            INSERT INTO app_state (key, value, updated_at)
            VALUES (?, ?, datetime('now', 'localtime'))
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = datetime('now', 'localtime')
            """,
            (key, val_str),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error("Error guardando app_state (%s) en SQLite: %s", key, e)
        raise


def read_persisted_secrets() -> Dict[str, str]:
    """Lee las credenciales privadas almacenadas en SQLite."""
    data = _get_sqlite_state("secrets")
    if data is not None and isinstance(data, dict):
        return {str(k): str(v) for k, v in data.items() if v is not None}

    # Migración transparente desde secrets.json legacy si existiese
    if os.path.exists(SECRETS_FILE):
        try:
            with open(SECRETS_FILE, "r", encoding="utf-8") as f:
                legacy = json.load(f)
            if isinstance(legacy, dict) and legacy:
                _set_sqlite_state("secrets", legacy)
                try:
                    os.remove(SECRETS_FILE)
                except OSError:
                    pass
                return {str(k): str(v) for k, v in legacy.items() if v is not None}
        except Exception as exc:
            logger.warning("Error migrando data/secrets.json a SQLite: %s", exc)

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
    if os.path.exists(SECRETS_FILE):
        try:
            os.remove(SECRETS_FILE)
        except OSError:
            pass


def delete_persisted_secret(key: str) -> None:
    """Elimina una credencial de SQLite."""
    data = read_persisted_secrets()
    if key in data:
        data.pop(key, None)
        _set_sqlite_state("secrets", data)
    if os.path.exists(SECRETS_FILE):
        try:
            os.remove(SECRETS_FILE)
        except OSError:
            pass


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

    # Migración transparente desde active_cv.json legacy si existiese
    if os.path.exists(ACTIVE_CV_FILE):
        try:
            with open(ACTIVE_CV_FILE, "r", encoding="utf-8") as f:
                legacy = json.load(f)
            if isinstance(legacy, dict) and legacy:
                _set_sqlite_state("active_cv_pointer", legacy)
                try:
                    os.remove(ACTIVE_CV_FILE)
                except OSError:
                    pass
                return legacy
        except Exception as exc:
            logger.debug("Error migrando active_cv.json a SQLite: %s", exc)

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
    if os.path.exists(ACTIVE_CV_FILE):
        try:
            os.remove(ACTIVE_CV_FILE)
        except OSError:
            pass


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
