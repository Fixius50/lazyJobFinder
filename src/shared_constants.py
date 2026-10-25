"""Constantes canónicas compartidas para lazyJobFinder."""

from typing import Any, Dict, List, Set

APPLICATION_STATUSES: Set[str] = {
    "discovered",
    "evaluating",
    "generating_docs",
    "evaluated",
    "notified",
    "applied",
    "interview",
    "discarded",
    "rejected",
    "archived",
}

SERVICES: Set[str] = {"ollama", "lazyjobfinder"}
SERVICE_ACTIONS: Set[str] = {"start", "stop", "restart"}

DOCUMENT_TYPES: Dict[str, Any] = {
    "cv_pdf": {"label": "CV Adaptado (PDF)", "mime": "application/pdf", "ext": ".pdf"},
    "cv_md": {"label": "CV Adaptado (Markdown)", "mime": "text/markdown", "ext": ".md"},
    "letter_pdf": {"label": "Carta de Presentación (PDF)", "mime": "application/pdf", "ext": ".pdf"},
    "letter_md": {"label": "Carta de Presentación (Markdown)", "mime": "text/markdown", "ext": ".md"},
}

CONFIRMATION_PHRASES: Dict[str, str] = {
    "clear_history": "BORRAR_HISTORIAL",
    "down_containers": "ELIMINAR_CONTENEDORES",
    "destroy_volumes": "DESTRUIR_VOLUMENES_PERMANENTE",
}

CV_LIMITS: Dict[str, Any] = {
    "max_size_bytes": 5 * 1024 * 1024,
    "max_size_mb": 5,
    "allowed_extensions": [".pdf", ".md", ".txt"],
}

PORTAL_SOURCES: Dict[str, Any] = {
    "tecnoempleo": {"label": "Tecnoempleo", "type": "rss"},
    "tecnoempleo_rss": {"label": "Tecnoempleo RSS", "type": "rss"},
    "infojobs": {"label": "InfoJobs", "type": "api"},
    "infojobs_api": {"label": "InfoJobs API", "type": "api"},
    "linkedin": {"label": "LinkedIn", "type": "scraper"},
    "indeed": {"label": "Indeed", "type": "scraper"},
    "glassdoor": {"label": "Glassdoor", "type": "scraper"},
    "google": {"label": "Google Jobs", "type": "scraper"},
    "jobspy": {"label": "JobSpy Multi-portal", "type": "scraper"},
}

SCORING_THRESHOLDS: Dict[str, int] = {
    "default_threshold": 65,
    "high_fit_threshold": 80,
    "moderate_fit_threshold": 65,
}

DEFAULT_SETTINGS: Dict[str, Any] = {
    "busqueda": {
        "terminos": [],
        "ubicaciones": ["Spain", "Remoto"],
        "filtros_exclusion": [],
        "antiguedad_horas": 48,
        "limite_por_fuente": 15,
    },
    "fuentes": {
        "tecnoempleo_rss": {"habilitado": False},
        "jobspy": {
            "habilitado": True,
            "sitios": ["indeed", "linkedin", "glassdoor", "google"],
        },
        "infojobs_api": {
            "habilitado": True,
            "client_id": "",
        },
    },
    "evaluacion": {
        "umbral_minimo_puntuacion": 65,
        "generar_documentos": True,
        "idioma_documentos": "es",
        "concurrencia": 2,
    },
    "notificaciones": {
        "guardar_en_interfaz": True,
        "enviar_telegram": True,
        "telegram": {
            "habilitado": True,
            "adjuntar_documentos": True,
            "notificar_solo_superan_umbral": True,
            "notificar_resumen_vacio": True,
        },
    },
    "horario": {
        "hora": 8,
        "minuto": 30,
    },
}
