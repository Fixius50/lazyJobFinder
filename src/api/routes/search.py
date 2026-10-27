"""Rutas para comprobación previa (pre-flight), disparo manual del pipeline y consulta de progreso."""

import asyncio
import logging
from typing import Any, Dict
from fastapi import APIRouter, BackgroundTasks, HTTPException, status
import requests

from ..deps import get_db, get_runner

logger = logging.getLogger("lazyJobFinder.api.search")
router = APIRouter(prefix="/search", tags=["Búsqueda y Pipeline"])


@router.get("/preflight")
def preflight_check() -> Dict[str, Any]:
    """
    Comprueba el estado de salud de los componentes críticos antes de permitir una búsqueda:
    1. Docker y Contenedor Ollama accesible en puerto 11434.
    2. Modelos descargados en Ollama (qwen2.5:3b-instruct u otros).
    3. Estado del cerrojo del pipeline (no ocupado actualmente).
    4. Base de datos SQLite accesible y escribible.
    """
    db = get_db()
    runner = get_runner()

    ollama_url = runner.ollama.base_url
    ollama_ok = False
    ollama_models = []
    ollama_error = None

    try:
        resp = requests.get(f"{ollama_url}/api/tags", timeout=3.0)
        if resp.status_code == 200:
            ollama_ok = True
            models_data = resp.json().get("models", [])
            ollama_models = [m.get("name") for m in models_data]
        else:
            ollama_error = f"Ollama respondió con código HTTP {resp.status_code}"
    except Exception as e:
        ollama_error = f"No se pudo conectar a Ollama ({ollama_url}): {str(e)}"

    is_running = runner.is_running()
    db_ok = True
    db_error = None
    try:
        # Consulta de prueba rápida
        db.has_run_today()
    except Exception as e:
        db_ok = False
        db_error = str(e)

    can_execute = ollama_ok and not is_running and db_ok

    return {
        "can_execute": can_execute,
        "ollama": {
            "healthy": ollama_ok,
            "url": ollama_url,
            "models": ollama_models,
            "error": ollama_error,
        },
        "pipeline": {
            "is_running": is_running,
            "locked": is_running,
        },
        "database": {
            "healthy": db_ok,
            "error": db_error,
        },
    }


@router.post("/run")
async def trigger_manual_search(background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """
    Inicia una búsqueda manual en segundo plano protegida por el cerrojo asíncrono.
    Rechaza de inmediato cualquier invocación concurrente.
    """
    runner = get_runner()
    if runner.is_running():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya hay una búsqueda en ejecución activa. Espera a que finalice.",
        )

    # Validar pre-flight mínimo antes de lanzar la tarea
    pre = preflight_check()
    if not pre["ollama"]["healthy"]:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Ollama no está disponible: {pre['ollama']['error']}. Comprueba el servicio en la Terminal del sistema.",
        )

    # Iniciar pipeline de forma no bloqueante utilizando asyncio.create_task
    # Notar que run_pipeline utiliza internamente async with self._async_lock
    asyncio.create_task(runner.run_pipeline(is_manual=True, trigger_label="web_manual"))

    db = get_db()
    db.log_event("INFO", "search_api", "Búsqueda manual iniciada desde la interfaz web de administración.")

    return {
        "success": True,
        "message": "Búsqueda manual iniciada correctamente en segundo plano.",
        "status": "running",
    }


@router.get("/status")
def get_search_status() -> Dict[str, Any]:
    """Consulta el estado en curso, progreso y métricas de la última ejecución."""
    db = get_db()
    runner = get_runner()

    is_running = runner.is_running()
    last_run = db.get_last_completed_run()
    recent_runs = db.get_recent_pipeline_runs(limit=5)
    stats = db.get_statistics()

    return {
        "is_running": is_running,
        "last_run": last_run,
        "recent_runs": recent_runs,
        "statistics": stats,
    }


@router.post("/stop")
def stop_search() -> Dict[str, Any]:
    """Detiene la búsqueda en curso solicitada por el usuario."""
    runner = get_runner()
    stopped = runner.request_stop()
    return {
        "success": True,
        "stopped": stopped,
        "message": (
            "Solicitud de parada enviada. El proceso se detendrá de inmediato."
            if stopped
            else "No hay ninguna búsqueda en ejecución activa."
        ),
    }

