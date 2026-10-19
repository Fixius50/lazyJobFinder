"""Rutas de mantenimiento, apagado y borrado selectivo con confirmación explícita."""

import logging
import os
import subprocess
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from ...shared_constants import CONFIRMATION_PHRASES
from ..deps import get_db

logger = logging.getLogger("lazyJobFinder.api.maintenance")
router = APIRouter(prefix="/maintenance", tags=["Mantenimiento y Ciclo de Vida"])


class CleanDocumentsRequest(BaseModel):
    job_ids: List[int] = Field(..., description="IDs de ofertas cuyos documentos se eliminarán")
    confirmation: bool = Field(..., description="Debe ser True para confirmar la eliminación física")


class ClearHistoryRequest(BaseModel):
    confirmation_phrase: str = Field(..., description="Debe coincidir exactamente con 'BORRAR_HISTORIAL'")


class DownContainersRequest(BaseModel):
    remove_volumes: bool = Field(False, description="Si es True, destruye volúmenes y modelos. PELIGRO.")
    confirmation_phrase: str = Field(..., description="Debe coincidir con 'ELIMINAR_CONTENEDORES'")


@router.post("/stop")
def stop_services() -> Dict[str, Any]:
    """
    Apagado ordinario: detiene los contenedores de forma ordenada sin destruir nada.
    Conserva contenedores, imágenes y volúmenes intactos.
    """
    import shutil
    from .system import _get_docker_client

    client = _get_docker_client()
    output_msgs = []

    if client:
        success = True
        try:
            ollama_c = client.containers.get("lazyjob_ollama")
            ollama_c.stop(timeout=10)
            output_msgs.append("lazyjob_ollama detenido con éxito.")
        except Exception as e:
            output_msgs.append(f"Ollama: {e}")
            success = False
        
        db = get_db()
        db.log_event(
            "INFO" if success else "ERROR",
            "maintenance",
            "Servicios de fondo (Ollama) gestionados ordenadamente mediante Docker SDK.",
        )
        return {
            "success": success,
            "message": "Servicios de fondo detenidos limpiamente vía Docker SDK." if success else "Error deteniendo lazyjob_ollama.",
            "output": "\n".join(output_msgs),
        }

    # Fallback si el binario docker está disponible en PATH (ej. host local)
    if shutil.which("docker"):
        cmd = ["docker", "compose", "stop"]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=25, check=False)
            db = get_db()
            db.log_event("INFO", "maintenance", "Servicios detenidos ordenadamente mediante docker compose stop.")
            return {
                "success": res.returncode == 0,
                "message": "Servicios detenidos limpiamente.",
                "output": res.stdout or res.stderr,
            }
        except Exception as e:
            logger.error("Error al detener servicios: %s", e)
            raise HTTPException(status_code=500, detail=f"Fallo al detener servicios: {str(e)}")

    return {
        "success": False,
        "message": "No se detectó CLI docker ni socket directo para detener contenedores. Utiliza start.bat en el host.",
        "output": "No-op",
    }


@router.post("/down-containers")
def down_containers(req: DownContainersRequest) -> Dict[str, Any]:
    """
    Elimina los contenedores existentes.
    SALVAGUARDA ESTRICTA:
    - Por defecto conserva el 100% de los volúmenes (los modelos descargados y la base de datos sobreviven).
    - Solo si remove_volumes es True Y la frase de confirmación es 'DESTRUIR_VOLUMENES_PERMANENTE',
      se destruye el volumen de modelos (lazyjob_ollama_models).
    - Los datos de SQLite (/app/data) NUNCA se destruyen aquí para evitar pérdidas accidentales de historial.
    """
    import shutil
    from .system import _get_docker_client

    phrase_destroy = CONFIRMATION_PHRASES["destroy_volumes"]
    phrase_down = CONFIRMATION_PHRASES["down_containers"]

    if req.remove_volumes:
        if req.confirmation_phrase != phrase_destroy:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Para eliminar volúmenes y modelos permanentemente, debes escribir exactamente '{phrase_destroy}'.",
            )
        action_msg = "Contenedores Y VOLÚMENES de modelos eliminados permanentemente."
    else:
        if req.confirmation_phrase != phrase_down:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Frase de confirmación errónea. Escribe '{phrase_down}'.",
            )
        action_msg = "Contenedores eliminados. Los volúmenes y datos persistentes se han conservado intactos."

    # Si docker CLI está presente (ej. en el host o contenedor con docker-cli)
    if shutil.which("docker"):
        cmd = ["docker", "compose", "down", "-v"] if req.remove_volumes else ["docker", "compose", "down"]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=35, check=False)
            db = get_db()
            db.log_event("WARNING", "maintenance", action_msg)
            return {
                "success": res.returncode == 0,
                "message": action_msg,
                "output": res.stdout or res.stderr,
                "volumes_removed": req.remove_volumes,
            }
        except Exception as e:
            logger.error("Error en down_containers: %s", e)
            raise HTTPException(status_code=500, detail=f"Fallo en operación Docker: {str(e)}")

    # Si se ejecuta dentro del contenedor sin Docker CLI
    client = _get_docker_client()
    if client:
        try:
            c = client.containers.get("lazyjob_ollama")
            c.stop(timeout=10)
            c.remove(v=req.remove_volumes)
            
            vol_msg = "Volumen con nombre de modelos preservado."
            if req.remove_volumes:
                try:
                    vol = client.volumes.get("lazyjob_ollama_models")
                    vol.remove(force=True)
                    vol_msg = "Volumen con nombre 'lazyjob_ollama_models' eliminado permanentemente."
                except Exception as ve:
                    vol_msg = f"Volumen 'lazyjob_ollama_models' no eliminado o no hallado: {ve}"

            db = get_db()
            db.log_event(
                "WARNING",
                "maintenance",
                f"Contenedor lazyjob_ollama eliminado vía Docker SDK ({vol_msg}). Datos de SQLite conservados intactos.",
            )
            return {
                "success": True,
                "message": f"Contenedor Ollama eliminado vía Docker SDK. {vol_msg}. Los datos SQLite y de la aplicación se conservan intactos.",
                "output": f"lazyjob_ollama eliminado con éxito.\n{vol_msg}",
                "volumes_removed": req.remove_volumes,
            }
        except Exception as ce:
            logger.error("Fallo al eliminar contenedor vía SDK: %s", ce)
            raise HTTPException(status_code=500, detail=f"Fallo al gestionar contenedor vía SDK: {str(ce)}")

    raise HTTPException(
        status_code=503,
        detail="El entorno dentro del contenedor no dispone de Docker CLI ni socket accesible para eliminar la infraestructura. Ejecuta 'docker compose down' desde la consola del host.",
    )


@router.post("/clean-documents")
def clean_selected_documents(req: CleanDocumentsRequest) -> Dict[str, Any]:
    """
    Elimina físicamente los documentos generados (PDFs/MDs) de las ofertas seleccionadas.
    No borra las ofertas ni las evaluaciones de la base de datos.
    """
    if not req.confirmation:
        raise HTTPException(status_code=400, detail="Debes confirmar explícitamente la eliminación.")

    db = get_db()
    deleted = db.delete_selected_documents(req.job_ids)
    db.log_event("INFO", "maintenance", f"Eliminados documentos físicos de {deleted} ofertas.")

    return {
        "success": True,
        "deleted_count": deleted,
        "message": f"Se eliminaron con éxito los documentos generados de {deleted} ofertas.",
    }


@router.post("/clear-history")
def clear_applications_history(req: ClearHistoryRequest) -> Dict[str, Any]:
    """
    Borra todo el historial de ofertas, evaluaciones, documentos generados y ejecuciones pasadas.
    Conserva la estructura SQLite y los registros de auditoría en system_logs.
    Requiere confirmación explícita con la frase 'BORRAR_HISTORIAL'.
    """
    phrase_clear = CONFIRMATION_PHRASES["clear_history"]
    if req.confirmation_phrase != phrase_clear:
        raise HTTPException(
            status_code=400,
            detail=f"Frase de confirmación incorrecta. Debe ser '{phrase_clear}'.",
        )

    db = get_db()
    stats = db.clear_applications_history()
    db.log_event("WARNING", "maintenance", f"Historial de candidaturas purgado: {stats}")

    return {
        "success": True,
        "message": "Historial de candidaturas y ejecuciones eliminado por completo.",
        "details": stats,
    }
