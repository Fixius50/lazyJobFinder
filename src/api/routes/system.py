"""Rutas de control de servicios Docker, estado y streaming de logs (SSE)."""

import asyncio
import json
import logging
import os
import re
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


def _resolve_current_project() -> Optional[str]:
    """
    Obtiene el nombre del proyecto de Compose actual desde las variables de entorno
    o leyendo el archivo .env en la raíz del proyecto.
    Si no está configurado, devuelve None para forzar política estricta anti-colisión.
    """
    proj = os.getenv("COMPOSE_PROJECT_NAME")
    if proj and proj.strip():
        return proj.strip()

    env_paths = [
        os.path.join(os.getcwd(), ".env"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), ".env"),
    ]
    for env_path in env_paths:
        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("COMPOSE_PROJECT_NAME="):
                            val = line.split("=", 1)[1].strip(" \"'")
                            if val:
                                return val
            except Exception:
                pass
    return None


def _find_compose_container(client, service_name: str, project_name: Optional[str] = None):
    """
    Localiza un contenedor de forma dinámica por la etiqueta de servicio de Docker Compose
    (com.docker.compose.service) y por el proyecto (com.docker.compose.project).
    Garantiza aislamiento estricto entre múltiples instalaciones concurrentes.
    Si no hay project_name configurado, descarta contenedores de otros proyectos y evita fallbacks arbitrarios.
    """
    if not client:
        return None
    try:
        resolved_proj = project_name or _resolve_current_project()
        containers = client.containers.list(all=True)

        # 1. Búsqueda estricta por etiquetas de Compose
        for c in containers:
            labels = c.labels or {}
            c_svc = labels.get("com.docker.compose.service", "")
            c_proj = labels.get("com.docker.compose.project", "")

            if resolved_proj:
                if c_proj != resolved_proj:
                    continue
            else:
                # Si no hay proyecto configurado, no secuestrar contenedores de proyectos específicos
                if c_proj:
                    continue

            if c_svc == service_name:
                return c

        # 2. Fallback por convención exacta de nombres de Compose (evita coincidencias accidentales)
        if resolved_proj:
            proj_prefix = re.escape(resolved_proj.lower())
            svc_pattern = re.compile(
                rf"^{proj_prefix}[_-]{re.escape(service_name.lower())}(?:[_-]\d+)?$"
            )
            for c in containers:
                c_name = c.name.lower()
                if svc_pattern.match(c_name):
                    return c
        # Si no hay proyecto configurado, se rechaza cualquier fallback genérico por seguridad
    except Exception as e:
        logger.debug("Error buscando contenedor para servicio '%s': %s", service_name, e)
    return None


@router.get("/status")
def get_services_status() -> Dict[str, Any]:
    """
    Devuelve el estado de salud y ciclo de vida de los servicios del proyecto:
    - detenido
    - arrancando
    - saludable
    - error
    Utiliza resolución 100% dinámica por etiquetas de Compose y aislamiento por proyecto.
    """
    client = _get_docker_client()
    services_status = {}
    current_project = _resolve_current_project()

    if client:
        services_to_query = {
            "ollama": "ollama",
            "lazyjobfinder": "lazyjobfinder",
        }
        for svc_key, compose_svc in services_to_query.items():
            c = _find_compose_container(client, compose_svc, current_project)
            if c:
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

                services_status[svc_key] = {
                    "status": norm,
                    "health": h_status or "n/a",
                    "container_name": c.name,
                    "id": c.short_id,
                }
            else:
                services_status[svc_key] = {
                    "status": "detenido",
                    "health": "desconocido",
                    "container_name": f"{compose_svc} (no detectado)",
                }
    else:
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
    Ejecuta una acción controlada de ciclo de vida sobre los servicios del proyecto con aislamiento por proyecto.
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

    client = _get_docker_client()
    if not client:
        return {
            "success": False,
            "status": "unavailable",
            "message": (
                f"La acción '{action}' sobre '{service}' no puede ejecutarse desde la interfaz web porque el socket de Docker no está accesible. "
                "Para iniciar, detener o reiniciar los servicios, utiliza los scripts locales de control (launch.bat / stop.bat en Windows o launch.sh / stop.sh en Linux)."
            ),
            "action": action,
            "service": service,
            "error_code": "DOCKER_UNAVAILABLE",
        }

    current_project = _resolve_current_project()
    results = []
    db = get_db()

    # Procesamiento para servicio único lazyjobfinder
    if service == "lazyjobfinder":
        if action == "stop":
            return {
                "success": False,
                "status": "rejected",
                "message": "lazyJobFinder aloja la API web activa. Para apagar el contenedor app sin interrumpir abruptamente el servidor, utiliza los scripts locales launch/stop.",
                "action": action,
                "service": service,
                "project": current_project,
            }
        if action == "start":
            return {
                "success": True,
                "status": "noop",
                "message": "El contenedor de la aplicación ya se encuentra en ejecución y operativo.",
                "action": action,
                "service": service,
                "project": current_project,
            }

    # Procesar Ollama (para "ollama" o "all")
    if service in ("ollama", "all"):
        target_ollama = _find_compose_container(client, "ollama", current_project)
        if not target_ollama:
            results.append({
                "service": "ollama",
                "success": False,
                "status": "not_found",
                "message": f"No se encontró el contenedor de Ollama para el proyecto '{current_project or 'default'}'.",
            })
        else:
            try:
                if action == "restart":
                    target_ollama.restart(timeout=10)
                elif action == "stop":
                    target_ollama.stop(timeout=10)
                elif action == "start":
                    target_ollama.start()

                msg = f"Servicio '{target_ollama.name}' ({action}) ejecutado correctamente."
                db.log_event("INFO", "docker", f"Acción '{action}' sobre '{target_ollama.name}' (Proyecto: {current_project or 'n/a'}).")
                results.append({
                    "service": "ollama",
                    "container_name": target_ollama.name,
                    "success": True,
                    "status": "executed",
                    "message": msg,
                })
            except Exception as ce:
                logger.warning("Fallo al ejecutar '%s' sobre '%s': %s", action, target_ollama.name, ce)
                results.append({
                    "service": "ollama",
                    "container_name": target_ollama.name,
                    "success": False,
                    "status": "error",
                    "message": f"Fallo al ejecutar '{action}' sobre '{target_ollama.name}': {str(ce)}",
                })

    # Procesar lazyjobfinder cuando se solicita "all" o "lazyjobfinder"
    if service == "all":
        if action == "start":
            results.append({
                "service": "lazyjobfinder",
                "success": True,
                "status": "noop",
                "message": "El contenedor de la aplicación ya se encuentra en ejecución y operativo.",
            })
        elif action == "stop":
            results.append({
                "service": "lazyjobfinder",
                "success": True,
                "status": "preserved",
                "message": "La API web se conserva activa para atender la sesión. Para detenerla por completo, ejecuta stop.bat o stop.sh.",
            })
        elif action == "restart":
            target_app = _find_compose_container(client, "lazyjobfinder", current_project)
            if target_app:
                try:
                    target_app.restart(timeout=10)
                    results.append({
                        "service": "lazyjobfinder",
                        "container_name": target_app.name,
                        "success": True,
                        "status": "executed",
                        "message": f"Servicio '{target_app.name}' (restart) ejecutado correctamente.",
                    })
                except Exception as ce:
                    results.append({
                        "service": "lazyjobfinder",
                        "container_name": target_app.name,
                        "success": False,
                        "status": "error",
                        "message": f"Fallo reiniciando '{target_app.name}': {str(ce)}",
                    })

    elif service == "lazyjobfinder" and action == "restart":
        target_app = _find_compose_container(client, "lazyjobfinder", current_project)
        if target_app:
            try:
                target_app.restart(timeout=10)
                results.append({
                    "service": "lazyjobfinder",
                    "container_name": target_app.name,
                    "success": True,
                    "status": "executed",
                    "message": f"Servicio '{target_app.name}' (restart) ejecutado correctamente.",
                })
            except Exception as ce:
                results.append({
                    "service": "lazyjobfinder",
                    "container_name": target_app.name,
                    "success": False,
                    "status": "error",
                    "message": f"Fallo reiniciando '{target_app.name}': {str(ce)}",
                })

    all_success = len(results) > 0 and all(r["success"] for r in results)
    primary_status = results[0]["status"] if len(results) == 1 else ("executed" if all_success else "partial_error")

    return {
        "success": all_success,
        "status": primary_status,
        "action": action,
        "service": service,
        "project": current_project,
        "details": results,
        "message": "; ".join(r["message"] for r in results) if results else "No se ejecutaron acciones.",
    }


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
    Prioriza la consulta dinámica mediante el SDK de Docker (docker-py), seguido de docker CLI,
    y con fallback a los eventos registrados en la base de datos SQLite.
    """
    import shutil

    # 1. Intento vía Docker Python Client con resolución dinámica por etiquetas
    client = _get_docker_client()
    current_project = os.getenv("COMPOSE_PROJECT_NAME")
    if client:
        try:
            services_to_inspect = []
            if service in ("ollama", "container_ollama"):
                services_to_inspect = ["ollama"]
            elif service in ("lazyjobfinder", "app", "container_app"):
                services_to_inspect = ["lazyjobfinder"]
            else:
                services_to_inspect = ["lazyjobfinder", "ollama"]

            logs_list = []
            for svc_name in services_to_inspect:
                c = _find_compose_container(client, svc_name, current_project)
                if c:
                    try:
                        raw = c.logs(tail=tail).decode("utf-8", errors="replace")
                        logs_list.append(f"--- [Contenedor: {c.name}] ---\n{raw.strip()}")
                    except Exception as ce:
                        logs_list.append(f"--- [Contenedor: {c.name}] ---\n(Error leyendo logs: {ce})")
                else:
                    logs_list.append(f"--- [Servicio Compose: {svc_name}] ---\n(Contenedor no encontrado o detenido)")

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
