"""Rutas para listado, detalle, filtrado, actualización y descarga segura de documentos de candidaturas."""

import logging
import os
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ...shared_constants import APPLICATION_STATUSES
from ..deps import get_db

logger = logging.getLogger("lazyJobFinder.api.jobs")
router = APIRouter(prefix="/jobs", tags=["Candidaturas y Ofertas"])

from ...storage import DOCUMENTS_DIR, PROJECT_ROOT as BASE_DIR, is_safe_path


class UpdateJobStatusRequest(BaseModel):
    status: str  # e.g., "discovered", "evaluated", "notified", "applied", "interview", "rejected", "archived"


class UpdateJobChannelRequest(BaseModel):
    telegram_notified: Optional[int] = None
    ui_saved: Optional[int] = None


@router.get("")
def list_jobs(
    search: Optional[str] = Query(None, description="Búsqueda por título, empresa o ubicación"),
    location: Optional[str] = Query(None, description="Filtrar por ubicación o país"),
    source: Optional[str] = Query(None, description="Filtrar por portal fuente"),
    status: Optional[str] = Query(None, description="Filtrar por estado de candidatura"),
    min_score: Optional[int] = Query(None, ge=0, le=100, description="Puntuación mínima de afinidad"),
    is_remote: Optional[bool] = Query(None, description="Filtrar por trabajo remoto"),
    modality: Optional[str] = Query(None, description="Filtrar por modalidad: presencial, teletrabajo o hibrido"),
    only_ui_saved: bool = Query(True, description="Mostrar solo ofertas marcadas para interfaz"),
    page: int = Query(1, ge=1, description="Número de página"),
    page_size: int = Query(20, ge=5, le=100, description="Elementos por página"),
    sort_by: str = Query("created_at", regex="^(created_at|score|company|title|date_posted)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
) -> Dict[str, Any]:
    """Lista las ofertas de empleo de SQLite con soporte de filtros, paginación y ordenación."""
    db = get_db()
    return db.get_jobs_paginated(
        search=search,
        location=location,
        source=source,
        status=status,
        min_score=min_score,
        is_remote=is_remote,
        modality=modality,
        only_ui_saved=only_ui_saved,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/{job_id}")
def get_job_detail(job_id: int) -> Dict[str, Any]:
    """Devuelve la ficha detallada de una oferta, su evaluación y sus documentos generados."""
    db = get_db()
    detail = db.get_job_detail(job_id)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Oferta con ID {job_id} no encontrada.",
        )
    return detail


@router.patch("/{job_id}/status")
def update_job_status(job_id: int, req: UpdateJobStatusRequest) -> Dict[str, Any]:
    """Actualiza el estado de la candidatura (ej. postulada, entrevista, archivada)."""
    db = get_db()
    detail = db.get_job_detail(job_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Oferta con ID {job_id} no encontrada.")

    new_status = req.status.strip().lower()
    if new_status not in APPLICATION_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Estado inválido. Opciones válidas: {list(APPLICATION_STATUSES)}",
        )

    db.update_job_status(job_id, new_status)
    db.log_event("INFO", "jobs", f"Estado de oferta ID {job_id} actualizado a '{new_status}'")
    return {"success": True, "job_id": job_id, "status": new_status}


@router.patch("/{job_id}/channel")
def update_job_channel_status(job_id: int, req: UpdateJobChannelRequest) -> Dict[str, Any]:
    """Actualiza los estados de notificación por canal (UI / Telegram) de una oferta concreta."""
    db = get_db()
    detail = db.get_job_detail(job_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Oferta con ID {job_id} no encontrada.")

    db.update_job_channel_status(
        job_id=job_id,
        telegram_notified=req.telegram_notified,
        ui_saved=req.ui_saved,
    )
    return {"success": True, "job_id": job_id}


@router.get("/{job_id}/document/{doc_type}")
def download_job_document(job_id: int, doc_type: str):
    """
    Descarga o previsualiza un documento generado (CV o carta) en PDF o Markdown.
    Tipos permitidos: cv_pdf, cv_md, letter_pdf, letter_md.
    Protección estricta contra Path Traversal: se verifica que la ruta resuelta
    resida exclusivamente dentro del directorio de documentos del proyecto.
    """
    allowed_types = {
        "cv_pdf": ("cv_pdf_path", "application/pdf"),
        "cv_md": ("cv_md_path", "text/markdown"),
        "letter_pdf": ("letter_pdf_path", "application/pdf"),
        "letter_md": ("letter_md_path", "text/markdown"),
    }

    if doc_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de documento inválido. Válidos: {list(allowed_types.keys())}",
        )

    column_name, media_type = allowed_types[doc_type]
    db = get_db()
    detail = db.get_job_detail(job_id)

    if not detail:
        raise HTTPException(status_code=404, detail="Oferta no encontrada.")

    target_path = detail.get(column_name)
    if not target_path or not os.path.exists(target_path):
        raise HTTPException(
            status_code=404,
            detail=f"El documento solicitado ({doc_type}) no existe o no ha sido generado aún.",
        )

    # Verificación de seguridad: Evitar Directory Traversal
    if not is_safe_path(target_path, DOCUMENTS_DIR) and not is_safe_path(target_path, BASE_DIR):
        logger.warning("Intento de path traversal bloqueado: %s", target_path)
        raise HTTPException(status_code=403, detail="Acceso a ruta de archivo no autorizado.")

    canonical_target = os.path.realpath(target_path)

    filename = os.path.basename(canonical_target)
    return FileResponse(
        path=canonical_target,
        media_type=media_type,
        filename=filename,
    )
