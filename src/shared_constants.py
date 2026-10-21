"""Carga centralizada de constantes compartidas entre el backend Python y el frontend Next.js."""

import json
import os
from typing import Any, Dict, List, Set

from .storage import CONSTANTS_FILE, PROJECT_ROOT

BASE_DIR = PROJECT_ROOT


def _load_constants() -> Dict[str, Any]:
    if os.path.exists(CONSTANTS_FILE):
        try:
            with open(CONSTANTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


_DATA = _load_constants()

APPLICATION_STATUSES: Set[str] = set(_DATA.get("application_statuses", {}).keys()) or {
    "discovered", "evaluated", "notified", "applied", "interview", "rejected", "archived"
}

SERVICES: Set[str] = set(_DATA.get("services", ["ollama", "lazyjobfinder"]))
SERVICE_ACTIONS: Set[str] = set(_DATA.get("service_actions", ["start", "stop", "restart"]))

DOCUMENT_TYPES: Dict[str, Any] = _DATA.get("document_types", {})

CONFIRMATION_PHRASES: Dict[str, str] = _DATA.get(
    "confirmation_phrases",
    {
        "clear_history": "BORRAR_HISTORIAL",
        "down_containers": "ELIMINAR_CONTENEDORES",
        "destroy_volumes": "DESTRUIR_VOLUMENES_PERMANENTE",
    },
)

CV_LIMITS = _DATA.get(
    "cv_upload_limits",
    {
        "max_size_bytes": 5 * 1024 * 1024,
        "max_size_mb": 5,
        "allowed_extensions": [".pdf", ".md", ".txt"],
    },
)

PORTAL_SOURCES: Dict[str, Any] = _DATA.get("portal_sources", {})
