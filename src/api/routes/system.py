"""Rutas de control de servicios Docker, estado y streaming de logs (SSE)."""

import asyncio
import json
import logging
import os
import subprocess
from typing import Any, AsyncGenerator, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ...shared_constants import SERVICES as ALLOWED_SERVICES, SERVICE_ACTIONS as ALLOWED_ACTIONS
from ..deps import get_db, get_runner

logger = logging.getLogger("lazyJobFinder.api.system")
router = APIRouter(prefix="/system", tags=["Sistema y Docker"])


class ServiceActionRequest(BaseModel):
    service: str  # "all", "ollama", o "lazyjobfinder"
    action: str   # "start", "stop", "restart"


def _get_docker_client():
    """Intenta inicializar el cliente Python de Docker."""
    try:
        import docker
        return docker.from_env()
    except Exception as e:
        logger.debug("docker-py no disponible o socket inaccesible directamente: %s", e)
        return None


def _inspect_services() -> Dict[str, Dict[str, Any]]:
    """
    Inspecciona el estado de los servicios.
    Detecta automáticamente si corre dentro de Docker (comprobando Ollama vía HTTP directamente)
    o en el host (mediante docker compose).
    """
    import shutil
    import urllib.request

    services = {
        "lazyjobfinder": {
            "status": "saludable",
            "health": "healthy",
            "container_name": "lazyjob_app",
            "raw_state": "running",
        },
        "ollama": {
            "status": "detenido",
            "health": "desconocido",
            "container_name": "lazyjob_ollama",
            "raw_state": "unknown",
        },
    }

    # Comprobación de salud directa de Ollama vía HTTP
    try:
        ollama_base = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434").rstrip("/")
        ollama_url = f"{ollama_base}/api/tags"
        req = urllib.request.Request(ollama_url, headers={"User-Agent": "lazyJobFinder/1.0"})
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            if resp.status == 200:
                services["ollama"]["status"] = "saludable"
                services["ollama"]["health"] = "healthy"
                services["ollama"]["raw_state"] = "running"
    except Exception as e:
        logger.debug("Ollama HTTP check no respondió: %s", e)
        services["ollama"]["status"] = "error"
        services["ollama"]["health"] = "unhealthy"

    # Si docker CLI está disponible en el entorno actual, enriquecer con metadatos de compose
    if shutil.which("docker"):
        try:
            cmd = ["docker", "compose", "ps", "--format", "json"]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=4,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                for line in result.stdout.strip().splitlines():
                    try:
                        data = json.loads(line)
                        svc_name = data.get("Service", "")
                        state = data.get("State", "").lower()
                        health = data.get("Health", "").lower()
                        if svc_name in services:
                            if "running" in state:
                                services[svc_name]["status"] = "saludable" if health != "unhealthy" else "error"
                            elif "restarting" in state:
                                services[svc_name]["status"] = "arrancando"
                            elif "dead" in state or "exited" in state:
                                services[svc_name]["status"] = "detenido"
                            services[svc_name]["health"] = health or "n/a"
                            services[svc_name]["raw_state"] = state
                    except Exception:
                        continue
        except Exception as e:
            logger.debug("Fallo al enriquecer con docker compose ps: %s", e)

    return services


@router.get("/status")
def get_services_status() -> Dict[str, Any]:
    """
    Devuelve el estado de salud y ciclo de vida de los servicios del proyecto:
    - detenido
    - arrancando
    - saludable
    - error
    """
    client = _get_docker_client()
    services_status = {}

    if client:
        container_map = {
            "ollama": "lazyjob_ollama",
            "lazyjobfinder": "lazyjob_app",
        }
        for svc_name, c_name in container_map.items():
            try:
                c = client.containers.get(c_name)
                c_state = c.status.lower()
                health_dict = c.attrs.get("State", {}).get("Health", {})
                h_status = health_dict.get("Status", "").lower()

                if c_state == "running":
                    if h_status == "healthy":
                        norm = "saludable"
                    elif h_status == "starting":
                        norm = "arrancando"
                    elif h_status == "unhealthy":
                        norm = "error"
                    else:
                        norm = "saludable"
                elif c_state == "restarting":
                    norm = "arrancando"
                elif c_state in ("exited", "dead"):
                    norm = "detenido"
                else:
                    norm = "error"

                services_status[svc_name] = {
                    "status": norm,
                    "health": h_status or "n/a",
                    "container_name": c_name,
                    "id": c.short_id,
                }
            except Exception:
                services_status[svc_name] = {
                    "status": "detenido",
                    "health": "desconocido",
                    "container_name": c_name,
                }
    else:
        # Fallback autónomo: comprueba Ollama vía HTTP y el propio proceso FastAPI
        services_status = _inspect_services()

    db = get_db()
    runner = get_runner()
    pipeline_state = {
        "is_running": runner.is_running(),
        "has_run_today": db.has_run_today(),
        "last_run": db.get_last_completed_run(),
    }

    return {
        "services": services_status,
        "pipeline": pipeline_state,
    }


@router.post("/action")
def execute_service_action(req: ServiceActionRequest) -> Dict[str, Any]:
    """
    Ejecuta una acción controlada de ciclo de vida sobre los servicios del proyecto.
    Acciones permitidas: start, stop, restart.
    Servicios permitidos: all, ollama, lazyjobfinder.
    """
    action = req.action.lower()
    service = req.service.lower()

    if action not in ALLOWED_ACTIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Acción '{action}' no permitida. Válidas: {list(ALLOWED_ACTIONS)}",
        )

    if service != "all" and service not in ALLOWED_SERVICES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Servicio '{service}' no permitido. Válidos: all, {list(ALLOWED_SERVICES)}",
        )

    # Protección y control de servicios vía Docker Python SDK (socket /var/run/docker.sock)
    client = _get_docker_client()
    if not client:
        raise HTTPException(
            status_code=503,
            detail="Socket Docker no disponible desde el contenedor. Comprueba los permisos de /var/run/docker.sock.",
        )

    # El servicio controlable de fondo es lazyjob_ollama
    # lazyjob_app es el backend web que aloja esta API y no debe auto-detenerse
    target_container = "lazyjob_ollama"

    try:
        c = client.containers.get(target_container)
        if action == "restart":
            c.restart(timeout=10)
        elif action == "stop":
            c.stop(timeout=10)
        elif action == "start":
            c.start()

        db = get_db()
        db.log_event("INFO", "docker", f"Acción '{action}' ejecutada sobre '{target_container}' vía Docker SDK.")
        return {
            "success": True,
            "message": f"Servicio {target_container} ({action}) ejecutado correctamente.",
            "action": action,
            "service": service,
        }
    except Exception as ce:
        logger.error("Fallo al controlar %s vía Docker SDK: %s", target_container, ce)
        raise HTTPException(
            status_code=500,
            detail=f"Fallo al ejecutar acción '{action}' sobre {target_container}: {str(ce)}",
        )


@router.get("/logs")
def get_system_logs(
    limit: int = Query(100, ge=1, le=500),
    level: Optional[str] = None,
    source: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Devuelve los registros históricos persistidos en SQLite."""
    db = get_db()
    return db.get_system_logs(limit=limit, level=level, source=source)


@router.get("/logs/container")
def get_container_logs(
    service: str = Query("all", regex="^(all|ollama|lazyjobfinder|app|container_app|container_ollama)$"),
    tail: int = Query(80, ge=10, le=500),
) -> Dict[str, str]:
    """
    Obtiene los registros recientes de Docker para un panel específico (ollama, app).
    Prioriza la consulta mediante el SDK de Docker (docker-py), seguido de docker CLI,
    y con fallback a los eventos registrados en la base de datos SQLite.
    """
    import shutil

    # 1. Intento vía Docker Python Client (a través del socket /var/run/docker.sock)
    client = _get_docker_client()
    if client:
        try:
            if service in ("ollama", "container_ollama"):
                targets = ["lazyjob_ollama"]
            elif service in ("lazyjobfinder", "app", "container_app"):
                targets = ["lazyjob_app"]
            else:
                targets = ["lazyjob_app", "lazyjob_ollama"]

            logs_list = []
            for name in targets:
                try:
                    c = client.containers.get(name)
                    raw = c.logs(tail=tail).decode("utf-8", errors="replace")
                    logs_list.append(f"--- [Contenedor: {name}] ---\n{raw.strip()}")
                except Exception as ce:
                    logs_list.append(f"--- [Contenedor: {name}] ---\n(No disponible: {ce})")

            return {
                "service": service,
                "logs": "\n\n".join(logs_list),
            }
        except Exception as e:
            logger.debug("docker-py fallo al obtener logs: %s", e)

    # 2. Intento vía docker CLI (si la herramienta está instalada en el PATH del sistema)
    if shutil.which("docker"):
        cmd = ["docker", "compose", "logs", f"--tail={tail}"]
        if service in ("ollama", "container_ollama"):
            cmd.append("ollama")
        elif service in ("lazyjobfinder", "app", "container_app"):
            cmd.append("lazyjobfinder")

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=8, check=False)
            output = res.stdout if res.returncode == 0 else (res.stderr or "No hay logs disponibles.")
            return {
                "service": service,
                "logs": output.strip(),
            }
        except Exception as e:
            logger.debug("subprocess docker logs fallo: %s", e)

    # 3. Fallback limpio mediante logs estructurados en SQLite
    db = get_db()
    source_filter = "ollama" if "ollama" in service else ("pipeline" if "pipeline" in service else None)
    events = db.get_system_logs(limit=tail, source=source_filter)
    if events:
        lines = [
            f"[{ev.get('timestamp', '')}] [{ev.get('level', 'INFO')}] [{ev.get('source', '')}] {ev.get('message', '')}"
            for ev in reversed(events)
        ]
        return {
            "service": service,
            "logs": f"[Logs en Base de Datos Local - Registro de Actividad]\n" + "\n".join(lines),
        }

    return {
        "service": service,
        "logs": f"Servicio '{service}' operativo. No hay eventos recientes registrados.",
    }


@router.get("/logs/stream")
async def stream_logs_sse(
    source: Optional[str] = None,
) -> StreamingResponse:
    """
    Transmite logs en tiempo real vía Server-Sent Events (SSE) a la consola web.
    Permite filtrar por canal: ollama, pipeline, app, o todos.
    """
    async def event_generator() -> AsyncGenerator[str, None]:
        db = get_db()
        last_seen_id = 0

        # Obtener el último ID registrado como punto de partida
        initial_logs = db.get_system_logs(limit=1)
        if initial_logs:
            last_seen_id = initial_logs[0]["id"]

        yield f"event: connected\ndata: {json.dumps({'message': 'Conexión SSE establecida con la consola de logs'})}\n\n"

        while True:
            await asyncio.sleep(2.0)
            try:
                new_logs = db.get_system_logs(limit=30, source=source)
                # Filtrar aquellos con ID mayor a last_seen_id
                fresh = [l for l in new_logs if l["id"] > last_seen_id]
                if fresh:
                    fresh.reverse()  # Orden cronológico ascendente para el frontend
                    for item in fresh:
                        last_seen_id = max(last_seen_id, item["id"])
                        yield f"event: log\ndata: {json.dumps(item)}\n\n"
            except Exception as e:
                logger.debug("Error en generador SSE de logs: %s", e)
                yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
