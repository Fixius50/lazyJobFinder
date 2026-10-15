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


@router.post("/down-containers")
def down_containers(req: DownContainersRequest) -> Dict[str, Any]:
    """
    Elimina los contenedores existentes.
    SALVAGUARDA ESTRICTA:
    - Por defecto conserva el 100% de los volúmenes (los modelos descargados y la base de datos sobreviven).
    - Solo si remove_volumes es True Y la frase de confirmación es 'DESTRUIR_VOLUMENES_PERMANENTE',
      se ejecuta con la bandera de volumen -v.
    """
    phrase_destroy = CONFIRMATION_PHRASES["destroy_volumes"]
    phrase_down = CONFIRMATION_PHRASES["down_containers"]

    if req.remove_volumes:
        if req.confirmation_phrase != phrase_destroy:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Para eliminar volúmenes y modelos permanentemente, debes escribir exactamente '{phrase_destroy}'.",
            )
        cmd = ["docker", "compose", "down", "-v"]
        action_msg = "Contenedores Y VOLÚMENES eliminados permanentemente."
    else:
        if req.confirmation_phrase != phrase_down:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Frase de confirmación errónea. Escribe '{phrase_down}'.",
            )
        cmd = ["docker", "compose", "down"]
        action_msg = "Contenedores eliminados. Los volúmenes y datos persistentes se han conservado intactos."

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
