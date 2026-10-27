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
    status: str  # e.g., "discovered", "evaluated", "interview", "discarded", "rejected"


class UpdateJobChannelRequest(BaseModel):
    telegram_notified: Optional[int] = None
    ui_saved: Optional[int] = None


@router.get("")
def list_jobs(
    search: Optional[str] = Query(None, description="Búsqueda por título, empresa o ubicación"),
    exclude: Optional[str] = Query(None, description="Términos excluidos separados por comas"),
    location: Optional[str] = Query(None, description="Filtrar por ubicación o país"),
    source: Optional[str] = Query(None, description="Filtrar por portal fuente"),
    status: Optional[str] = Query(None, description="Filtrar por estado de candidatura"),
    min_score: Optional[int] = Query(None, ge=0, le=100, description="Puntuación mínima de afinidad"),
    is_remote: Optional[bool] = Query(None, description="Filtrar por trabajo remoto"),
    modality: Optional[str] = Query(None, description="Filtrar por modalidad única: presencial, teletrabajo o hibrido"),
    modalities: Optional[List[str]] = Query(None, description="Lista de modalidades seleccionadas por checkbox"),
    categories: Optional[List[str]] = Query(None, description="Categorías profesionales seleccionadas"),
    educations: Optional[List[str]] = Query(None, description="Formación mínima seleccionada"),
    min_experience_years: Optional[int] = Query(None, ge=0, le=10, description="Nivel mínimo de experiencia del deslizante"),
    min_salary: Optional[float] = Query(None, ge=0, description="Salario mínimo buscado del deslizante"),
    schedules: Optional[List[str]] = Query(None, description="Tipos de jornada laboral seleccionados"),
    contract_types: Optional[List[str]] = Query(None, description="Tipos de contrato de trabajo seleccionados"),
    geo_lat: Optional[float] = Query(None, description="Latitud central para mapa y radio"),
    geo_lon: Optional[float] = Query(None, description="Longitud central para mapa y radio"),
    geo_radius_km: Optional[float] = Query(None, ge=0, le=1000, description="Radio de distancia en km desde el punto central"),
    only_ui_saved: bool = Query(True, description="Mostrar solo ofertas marcadas para interfaz"),
    time_range: Optional[str] = Query("all", description="Filtro de antigüedad de la oferta: all, 24h, 7d, 30d"),
    page: int = Query(1, ge=1, description="Número de página"),
    page_size: int = Query(50, ge=5, le=500, description="Elementos por página"),
    sort_by: str = Query("created_at", pattern="^(created_at|score|company|title|date_posted)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
) -> Dict[str, Any]:
    """Lista las ofertas de empleo de SQLite con soporte de filtros multicriterio avanzados, mapa y paginación."""
    from ...tailoring.cv_reader import get_active_cv_status
    cv_status = get_active_cv_status()
    has_active_cv = cv_status.get("has_cv", False)

    if not has_active_cv:
        return {
            "items": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
            "total_pages": 1,
            "has_cv": False,
        }

    db = get_db()
    active_filename = cv_status.get("filename")
    result = db.get_jobs_paginated(
        search=search,
        exclude=exclude,
        location=location,
        source=source,
        status=status,
        min_score=min_score,
        is_remote=is_remote,
        modality=modality,
        modalities=modalities,
        categories=categories,
        educations=educations,
        min_experience_years=min_experience_years,
        min_salary=min_salary,
        schedules=schedules,
        contract_types=contract_types,
        geo_lat=geo_lat,
        geo_lon=geo_lon,
        geo_radius_km=geo_radius_km,
        only_ui_saved=only_ui_saved,
        time_range=time_range,
        cv_filename=active_filename,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    result["has_cv"] = True
    return result


@router.get("/facets")
def get_job_filter_facets() -> Dict[str, Any]:
    """
    Devuelve dinámicamente las opciones y conteos reales de filtros (portales, modalidades,
    categorías, formación, salarios, etc.) presentes en las ofertas extraídas de los portales.
    """
    from ...tailoring.cv_reader import get_active_cv_status
    cv_status = get_active_cv_status()
    has_active_cv = cv_status.get("has_cv", False)

    if not has_active_cv:
        return {
            "total_jobs": 0,
            "sources": [],
            "modalities": [],
            "categories": [],
            "educations": [],
            "schedules": [],
            "contract_types": [],
            "max_experience_years": 0,
            "max_salary": 0,
            "has_cv": False,
        }

    db = get_db()
    active_filename = cv_status.get("filename")
    return db.get_filter_facets(cv_filename=active_filename)


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


@router.post("/{job_id}/generate-documents")
async def generate_job_documents_endpoint(job_id: int) -> Dict[str, Any]:
    """Genera bajo demanda el CV adaptado y la carta de presentación para una vacante específica."""
    import asyncio
    import yaml
    from ...tailoring.cv_reader import get_active_profile, get_active_cv_status
    from ...tailoring.cv_tailorer import CVTailorer
    from ...tailoring.cover_letter import CoverLetterGenerator
    from ...tailoring.pdf_renderer import PDFRenderer
    from ...evaluator.ollama_client import OllamaClient

    db = get_db()
    detail = db.get_job_detail(job_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Oferta con ID {job_id} no encontrada.")

    cv_status = get_active_cv_status()
    if not cv_status.get("has_cv"):
        raise HTTPException(
            status_code=400,
            detail="No hay ningún currículum activo configurado. Sube o selecciona un CV primero.",
        )

    profile = get_active_profile()
    if not profile:
        raise HTTPException(
            status_code=400,
            detail="No se pudo extraer el perfil estructurado del CV activo.",
        )

    eval_dict = {
        "score": detail.get("score") or 75,
        "fit_level": detail.get("fit_level") or "BUENO",
        "should_apply": True,
        "matched_skills": detail.get("matched_skills") or [],
        "missing_skills": detail.get("missing_skills") or [],
        "strengths": detail.get("strengths") or [],
        "gaps": detail.get("gaps") or [],
        "reasoning": detail.get("reasoning") or "",
    }

    db.update_job_status(job_id, "generating_docs")
    ollama = OllamaClient()
    tailorer = CVTailorer(profile=profile, ollama_client=ollama)
    letter_gen = CoverLetterGenerator(profile=profile, ollama_client=ollama)
    renderer = PDFRenderer()

    try:
        cv_md, diff_audit = await asyncio.to_thread(tailorer.tailor, detail, eval_dict)
        letter_md = await asyncio.to_thread(letter_gen.generate, detail, eval_dict)

        doc_paths = await asyncio.to_thread(
            renderer.render_cv_and_letter,
            job=detail,
            cv_md=cv_md,
            diff_audit=diff_audit,
            letter_md=letter_md,
        )

        db.save_documents({
            "job_id": job_id,
            "cv_pdf_path": doc_paths["cv_pdf_path"],
            "cv_md_path": doc_paths["cv_md_path"],
            "letter_pdf_path": doc_paths["letter_pdf_path"],
            "letter_md_path": doc_paths["letter_md_path"],
            "diff_summary": yaml.dump(diff_audit, allow_unicode=True),
        })

        db.update_job_status(job_id, "evaluated")
        db.log_event("INFO", "jobs", f"Documentos generados bajo demanda con éxito para oferta ID {job_id}")

        return {
            "success": True,
            "job_id": job_id,
            "has_cv": True,
            "has_letter": True,
            "cv_pdf_url": f"/api/jobs/{job_id}/document/cv_pdf",
            "letter_pdf_url": f"/api/jobs/{job_id}/document/letter_pdf",
            "message": "CV y carta de presentación generados correctamente.",
        }
    except Exception as e:
        db.update_job_status(job_id, "evaluated")
        logger.error("Fallo generando documentos bajo demanda para ID %d: %s", job_id, e)
        raise HTTPException(
            status_code=500,
            detail=f"Error al generar documentos: {str(e)}",
        )

