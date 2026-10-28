"""lazyJobFinder: Sistema local, autónomo y gratuito de búsqueda de empleo automatizada.

Punto de entrada y exportación centralizada de la arquitectura del proyecto.
Permite importar los componentes centrales directamente desde 'src':
    from src import Database, JobPipelineRunner, ScoringEngine, JobModel, EvaluationModel
"""

from __future__ import annotations

import sys
from typing import Any, List

__version__ = "1.0.0"

# 1. Centralizar la caché de bytecode de Python en src/__pycache__ desde el arranque (Regla 13)
from .storage import setup_pycache_centralization

setup_pycache_centralization()

# 2. Mapeo de exportaciones perezosas (PEP 562) para evitar dependencias circulares o sobrecarga en arranque
_EXPORT_MAP = {
    "Database": ("src.database", "Database"),
    "JobModel": ("src.models", "JobModel"),
    "EvaluationModel": ("src.models", "EvaluationModel"),
    "GeneratedDocumentModel": ("src.models", "GeneratedDocumentModel"),
    "PipelineRunModel": ("src.models", "PipelineRunModel"),
    "SystemLogModel": ("src.models", "SystemLogModel"),
    "AppStateModel": ("src.models", "AppStateModel"),
    "CVCacheModel": ("src.models", "CVCacheModel"),
    "JobPipelineRunner": ("src.scheduler.runner", "JobPipelineRunner"),
    "ConnectorManager": ("src.connectors.manager", "ConnectorManager"),
    "BaseConnector": ("src.connectors.base", "BaseConnector"),
    "JobOffer": ("src.connectors.base", "JobOffer"),
    "ScoringEngine": ("src.evaluator.scoring_engine", "ScoringEngine"),
    "OllamaClient": ("src.evaluator.ollama_client", "OllamaClient"),
    "CVTailorer": ("src.tailoring.cv_tailorer", "CVTailorer"),
    "CoverLetterGenerator": ("src.tailoring.cover_letter", "CoverLetterGenerator"),
    "PDFRenderer": ("src.tailoring.pdf_renderer", "PDFRenderer"),
    "ProfileVerifier": ("src.tailoring.verifier", "ProfileVerifier"),
    "TelegramJobBot": ("src.telegram_bot.bot", "TelegramJobBot"),
}

__all__: List[str] = [
    "__version__",
    "setup_pycache_centralization",
    *list(_EXPORT_MAP.keys()),
]


def __getattr__(name: str) -> Any:
    """Importación perezosa de componentes centrales al acceder a ellos desde 'src'."""
    if name in _EXPORT_MAP:
        mod_name, attr_name = _EXPORT_MAP[name]
        mod = __import__(mod_name, fromlist=[attr_name])
        return getattr(mod, attr_name)
    raise AttributeError(f"El módulo 'src' no tiene el atributo o componente '{name}'")


def __dir__() -> List[str]:
    return sorted(list(globals().keys()) + __all__)
