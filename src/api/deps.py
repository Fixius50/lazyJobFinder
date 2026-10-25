"""Dependencias e instancias compartidas para la API FastAPI de lazyJobFinder."""

import os
import threading
from typing import Any, Optional

from ..database import Database
from ..scheduler.runner import JobPipelineRunner

_runner_instance: Optional[JobPipelineRunner] = None
_db_instance: Optional[Database] = None
_stop_event: Optional[Any] = None
_lock = threading.Lock()


def set_stop_event(event: Any) -> None:
    """Registra el evento de parada global de la aplicación."""
    global _stop_event
    _stop_event = event


def trigger_shutdown() -> bool:
    """Solicita la parada limpia de lazyJobFinder."""
    global _stop_event
    if _stop_event is not None:
        if hasattr(_stop_event, "set"):
            _stop_event.set()
        return True
    return False


def get_db() -> Database:
    """Devuelve la instancia singleton de la base de datos."""
    global _db_instance
    if _db_instance is None:
        with _lock:
            if _db_instance is None:
                _db_instance = Database()
    return _db_instance


def get_runner() -> JobPipelineRunner:
    """Devuelve la instancia singleton del orquestador del pipeline."""
    global _runner_instance
    if _runner_instance is None:
        with _lock:
            if _runner_instance is None:
                _runner_instance = JobPipelineRunner()
    return _runner_instance
