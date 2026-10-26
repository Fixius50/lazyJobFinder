"""Rutas de gestión de CV: validación estricta, subida local y control del CV activo."""

import hashlib
import logging
import os
import re
import shutil
import time
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from ...shared_constants import CV_LIMITS
from ..deps import get_db

logger = logging.getLogger("lazyJobFinder.api.cv")
router = APIRouter(prefix="/cv", tags=["CV y Perfil"])

from ...storage import (
    ACTIVE_CV_FILE as ACTIVE_CV_CONFIG_FILE,
    BASE_CV_FILE as BASE_CV_PATH,
    PROJECT_ROOT as BASE_DIR,
    UPLOAD_DIR,
    ensure_storage_dirs,
    read_active_cv_pointer,
    write_active_cv_pointer,
)

ALLOWED_EXTENSIONS = set(CV_LIMITS.get("allowed_extensions", [".pdf", ".md", ".txt"]))
MAX_FILE_SIZE_BYTES = CV_LIMITS.get("max_size_bytes", 5 * 1024 * 1024)


class SelectCVRequest(BaseModel):
    filename: str  # "default" o nombre exacto del archivo en data/uploaded_cvs/


def _ensure_upload_dir():
    ensure_storage_dirs()


def _get_active_cv_info() -> Dict[str, Any]:
    """Recupera la información del CV actualmente seleccionado sin enviar datos a la IA."""
    _ensure_upload_dir()
    pointer = read_active_cv_pointer()
    selected_filename = pointer.get("selected_filename", "none")

    if selected_filename and selected_filename not in ("none", "default"):
        target_path = os.path.join(UPLOAD_DIR, os.path.basename(selected_filename))
        if os.path.exists(target_path):
            stat = os.stat(target_path)
            return {
                "type": "custom",
                "filename": os.path.basename(target_path),
                "path": f"data/uploaded_cvs/{os.path.basename(target_path)}",
                "size_bytes": stat.st_size,
                "modified_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
                "is_default": False,
                "description": "CV personalizado cargado localmente.",
                "search_terms": pointer.get("search_terms", []),
                "primary_role": pointer.get("primary_role", ""),
            }

    # Si no hay CV cargado o seleccionado:
    return {
        "type": "none",
        "filename": "Ninguno",
        "path": "",
        "size_bytes": 0,
        "modified_at": "n/a",
        "is_default": False,
        "description": "Sin CV activo. Las ofertas se conservarán sin filtrar por currículum.",
        "search_terms": [],
        "primary_role": "",
    }


def _sync_terms_and_update_settings(filename: str, file_path: Optional[str] = None) -> Dict[str, Any]:
    """Analiza el CV, extrae términos de búsqueda universales y los sincroniza en SQLite con caché instantánea (O(1))."""
    from ...tailoring.cv_reader import extract_cv_text, _extract_terms_universally_from_text, extract_search_terms_from_cv
    from ...storage import write_active_cv_pointer

    if filename in ("none", "Ninguno", "", "default") or not file_path or not os.path.exists(file_path):
        write_active_cv_pointer("none", search_terms=[], primary_role="")
        return {"search_terms": [], "primary_role": ""}

    db = get_db()
    mtime = os.path.getmtime(file_path)
    size = os.path.getsize(file_path)

    # 1. Caché persistente SQLite: Si ya fue extraído previamente, responder en < 2 ms sin invocar IA
    cached = db.get_cv_cache(filename, file_mtime=mtime, file_size=size)
    if cached and cached.get("profile"):
        prof = cached["profile"]
        terms = prof.get("search_terms", [])
        primary_role = prof.get("primary_role", "")
        if terms:
            write_active_cv_pointer(filename, search_terms=terms, primary_role=primary_role)
            return prof

    # 2. Extracción de texto con caché en memoria / SQLite (0 ms si no cambió el archivo)
    text = extract_cv_text(file_path, db=db)

    # 3. Extracción universal ultrarrápida NLP/ocupaciones (2 ms, sin bloquear con IA en CPU)
    terms_info = _extract_terms_universally_from_text(text, filename=filename)
    terms = terms_info.get("search_terms", [])
    primary_role = terms_info.get("primary_role", "")

    # Solo si el extractor universal no detectó términos, intentar con extract_search_terms_from_cv
    if not terms:
        profile_info = extract_search_terms_from_cv(text, filename=filename)
        terms = profile_info.get("search_terms", [])
        primary_role = profile_info.get("primary_role", "")

    # 4. Guardar en cv_cache de SQLite para garantizar O(1) en cualquier selección posterior
    try:
        import hashlib
        file_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        existing_profile = (cached.get("profile") if cached else None) or {}
        existing_profile["search_terms"] = terms
        existing_profile["primary_role"] = primary_role
        db.save_cv_cache(
            filename=filename,
            file_hash=file_hash,
            file_mtime=mtime,
            file_size=size,
            extracted_text=text,
            profile_data=existing_profile,
        )
    except Exception as save_err:
        logger.debug("Error persistiendo search_terms en cv_cache: %s", save_err)

    write_active_cv_pointer(
        filename,
        search_terms=terms,
        primary_role=primary_role,
    )
    print(f"[CV Auto-Config] Sincronizados términos para '{filename}': {terms}", flush=True)

    return {"search_terms": terms, "primary_role": primary_role}


@router.get("/active")
def get_active_cv() -> Dict[str, Any]:
    """Devuelve el estado del CV activo actual."""
    return _get_active_cv_info()


@router.get("/preview")
def preview_cv(filename: Optional[str] = None) -> Dict[str, Any]:
    """
    Extrae y devuelve el texto plano del CV activo o del archivo indicado por filename,
    permitiendo al usuario validar cómo se lee su archivo (PDF, Markdown o texto).
    """
    from ...tailoring.cv_reader import get_active_cv_text_and_meta, extract_cv_text

    if filename and filename not in ("none", "default"):
        target_path = os.path.join(UPLOAD_DIR, os.path.basename(filename))
        if os.path.exists(target_path):
            try:
                text = extract_cv_text(target_path)
                return {
                    "filename": os.path.basename(target_path),
                    "type": "custom",
                    "extension": os.path.splitext(target_path)[1].lower(),
                    "char_count": len(text),
                    "word_count": len(text.split()),
                    "text_preview": text[:5000],
                    "full_text_length": len(text),
                    "is_default": False,
                    "error": None,
                }
            except Exception as e:
                return {
                    "filename": os.path.basename(target_path),
                    "type": "custom",
                    "extension": os.path.splitext(target_path)[1].lower(),
                    "char_count": 0,
                    "word_count": 0,
                    "text_preview": "",
                    "full_text_length": 0,
                    "is_default": False,
                    "error": str(e),
                }

    text, meta = get_active_cv_text_and_meta()
    return {
        "filename": meta.get("filename"),
        "type": meta.get("type"),
        "extension": meta.get("extension"),
        "char_count": meta.get("char_count", len(text)),
        "word_count": meta.get("word_count", len(text.split())),
        "text_preview": text[:5000],  # Primeros 5000 caracteres para vista previa rápida
        "full_text_length": len(text),
        "is_default": meta.get("is_default", True),
        "error": meta.get("error"),
    }


@router.get("/list")
def list_uploaded_cvs() -> List[Dict[str, Any]]:
    """Lista los archivos CV disponibles en el repositorio local sin leer su contenido."""
    _ensure_upload_dir()
    cvs = []

    # Solo archivos CV subidos a data/uploaded_cvs/
    if os.path.exists(UPLOAD_DIR):
        for entry in os.scandir(UPLOAD_DIR):
            if entry.is_file():
                if entry.name.startswith(".") or "extracted" in entry.name.lower():
                    continue
                ext = os.path.splitext(entry.name)[1].lower()
                if ext in ALLOWED_EXTENSIONS:
                    stat = entry.stat()
                    cvs.append({
                        "filename": entry.name,
                        "id": entry.name,
                        "is_default": False,
                        "size_bytes": stat.st_size,
                        "modified_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
                    })

    return cvs


@router.post("/upload")
async def upload_cv_file(file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    Sube un archivo CV con validación estricta de formato y tamaño.
    Garantías de seguridad y privacidad:
    - Se almacena exclusivamente en data/uploaded_cvs/.
    - JAMÁS sobrescribe ni modifica config/cv_base.md ni config/profile.yaml.
    - No se envía a ninguna API externa ni servicio de IA durante la subida.
    """
    _ensure_upload_dir()

    # Validar extensión
    filename = file.filename or "cv_upload"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato no permitido: '{ext}'. Formatos admitidos: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Sanitizar nombre de archivo (solo alfanumérico, guiones y punto)
    safe_base = re.sub(r"[^\w\-]", "_", os.path.splitext(filename)[0])
    safe_base = safe_base[:50]  # Limitar longitud
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    safe_filename = f"{safe_base}_{timestamp}{ext}"
    target_path = os.path.join(UPLOAD_DIR, safe_filename)

    # Validar tamaño leyendo por bloques
    total_bytes = 0
    try:
        with open(target_path, "wb") as dest:
            while chunk := await file.read(64 * 1024):  # 64 KB por bloque
                total_bytes += len(chunk)
                if total_bytes > MAX_FILE_SIZE_BYTES:
                    dest.close()
                    if os.path.exists(target_path):
                        os.remove(target_path)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"El archivo excede el tamaño máximo permitido de {MAX_FILE_SIZE_BYTES // (1024*1024)} MB.",
                    )
                dest.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        if os.path.exists(target_path):
            os.remove(target_path)
        logger.error("Error guardando archivo CV: %s", e)
        raise HTTPException(status_code=500, detail=f"Error al guardar el archivo: {str(e)}")

    # Auto-activar el archivo CV subido de forma inmediata y sincronizar términos de búsqueda
    profile_info = _sync_terms_and_update_settings(safe_filename, target_path)

    # Registrar en base de datos para auditoría
    db = get_db()
    db.log_event("INFO", "cv", f"Archivo CV subido y activado: {safe_filename} ({total_bytes} bytes)")

    # Disparar automáticamente la búsqueda de empleo en los portales con los nuevos términos
    try:
        from ..deps import get_runner
        import asyncio
        runner = get_runner()
        if not runner.is_running():
            asyncio.create_task(runner.run_pipeline(is_manual=True, trigger_label="cv_upload"))
            print(f"\n[CV Auto-Discovery] Iniciando escaneo en portales para '{safe_filename}' con términos {profile_info.get('search_terms')}...", flush=True)
    except Exception as run_err:
        logger.error("No se pudo iniciar auto-discovery: %s", run_err)

    return {
        "success": True,
        "filename": safe_filename,
        "original_name": filename,
        "size_bytes": total_bytes,
        "type": ext.lstrip(".").upper(),
        "re_evaluated_jobs": 0,
        "active_info": _get_active_cv_info(),
        "message": f"CV '{safe_filename}' subido y activado. Búsqueda en portales iniciada.",
    }


def _reevaluate_jobs_with_active_cv(db: Any) -> int:
    """Reevalúa las ofertas registradas adaptándolas al CV activo."""
    try:
        from ...evaluator.scoring_engine import ScoringEngine
        import yaml
        import threading
        settings_path = os.path.join(BASE_DIR, "config", "settings.yaml")
        profile_path = os.path.join(BASE_DIR, "config", "profile.yaml")
        settings = {}
        if os.path.exists(settings_path):
            with open(settings_path, "r", encoding="utf-8") as f:
                settings = yaml.safe_load(f) or {}
        engine = ScoringEngine(db, profile_path, settings)
        count = engine.reevaluate_all_jobs(max_jobs=150)

        # Si Ollama está disponible, procesar con IA en segundo plano mostrando progreso en la terminal
        def _bg_ollama_evaluation():
            try:
                health = engine.ollama.check_health()
                if not health.get("online"):
                    print("[IA / Ollama] Ollama no está online; se mantiene la evaluación algorítmica rápida.", flush=True)
                    return
                print(f"[IA / Ollama] >>> Iniciando reevaluación profunda con IA ({engine.ollama.default_model})...", flush=True)
                promising_jobs = db.get_jobs_paginated(page_size=20)["items"]
                for pj in promising_jobs:
                    engine.evaluate(pj)
                print(f"[IA / Ollama] >>> Reevaluación profunda con IA completada para {len(promising_jobs)} ofertas.", flush=True)
            except Exception as ex:
                logger.debug("Error en bg ollama evaluation: %s", ex)

        threading.Thread(target=_bg_ollama_evaluation, daemon=True).start()
        return count
    except Exception as e:
        logger.warning("Fallo al reevaluar ofertas con el CV activo: %s", e)
        return 0


@router.post("/select")
def select_active_cv(req: SelectCVRequest) -> Dict[str, Any]:
    """Selecciona qué CV actúa como referencia activa en la interfaz y readapta las ofertas."""
    _ensure_upload_dir()
    choice = req.filename.strip()

    if choice in ("none", "Ninguno", "", "default"):
        choice = "none"
        full_cv_path = None
    else:
        # Evitar directory traversal
        clean_name = os.path.basename(choice)
        full_path = os.path.join(UPLOAD_DIR, clean_name)
        if not os.path.exists(full_path):
            raise HTTPException(status_code=404, detail="El archivo CV seleccionado no existe.")
        choice = clean_name
        full_cv_path = full_path

    profile_info = _sync_terms_and_update_settings(choice, full_cv_path)

    db = get_db()
    db.log_event("INFO", "cv", f"CV activo actualizado a: {choice}")

    # Retorno instantáneo: el cambio de CV filtra localmente las ofertas ya almacenadas (Regla 12)
    return {
        "success": True,
        "selected": choice,
        "active_info": _get_active_cv_info(),
        "re_evaluated_jobs": 0,
        "message": f"CV activo actualizado a '{choice}'.",
    }


@router.post("/reevaluate")
def reevaluate_cv_jobs() -> Dict[str, Any]:
    """Reevalúa manualmente las ofertas guardadas contra el CV activo."""
    db = get_db()
    re_evaluated = _reevaluate_jobs_with_active_cv(db)
    return {
        "success": True,
        "re_evaluated_jobs": re_evaluated,
        "active_info": _get_active_cv_info(),
        "message": f"Se han adaptado y reevaluado {re_evaluated} ofertas con el CV activo.",
    }


@router.delete("/{filename}")
def delete_uploaded_cv(filename: str) -> Dict[str, Any]:
    """
    Elimina un archivo CV personalizado subido previamente en data/uploaded_cvs/.
    Elimina en cascada todas las ofertas vinculadas a este CV en la base de datos.
    Si el archivo eliminado era el CV activo, restablece la configuración a 'none' (sin filtrado).
    """
    _ensure_upload_dir()
    clean_name = os.path.basename(filename.strip())

    if not clean_name or clean_name in ("none", "Ninguno"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nombre de archivo inválido para eliminación.",
        )

    target_path = os.path.join(UPLOAD_DIR, clean_name)
    if not os.path.exists(target_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El archivo CV '{clean_name}' no existe en el almacenamiento local.",
        )

    # 1. Eliminar ofertas asociadas a este CV en SQLite
    db = get_db()
    deleted_jobs = db.delete_jobs_by_cv_filename(clean_name)
    logger.info("Eliminadas %d ofertas asociadas al CV '%s'", deleted_jobs, clean_name)

    # 2. Eliminar el archivo físico del disco y su caché
    try:
        os.remove(target_path)
    except Exception as e:
        logger.error("Error al eliminar archivo CV '%s': %s", clean_name, e)
        raise HTTPException(status_code=500, detail=f"No se pudo eliminar el archivo: {str(e)}")

    try:
        from ...tailoring.cv_reader import invalidate_cv_cache
        invalidate_cv_cache(clean_name)
    except Exception as inv_err:
        logger.debug("Error invalidando cache de CV: %s", inv_err)

    # 3. Si era el CV activo seleccionado, volver a 'none'
    reverted_to_none = False
    current_pointer = read_active_cv_pointer()
    if current_pointer.get("selected_filename") == clean_name:
        try:
            write_active_cv_pointer("none")
            reverted_to_none = True
        except Exception as e:
            logger.warning("Error restableciendo active_cv.json tras borrado: %s", e)

    db.log_event("INFO", "cv", f"Archivo CV eliminado: {clean_name} ({deleted_jobs} ofertas eliminadas, restaurado a sin CV: {reverted_to_none})")

    if reverted_to_none:
        _reevaluate_jobs_with_active_cv(db)

    return {
        "success": True,
        "message": f"Currículum '{clean_name}' y sus {deleted_jobs} ofertas asociadas eliminados correctamente.",
        "deleted_jobs": deleted_jobs,
        "reverted_to_none": reverted_to_none,
        "active_info": _get_active_cv_info(),
    }


@router.post("/cache/clear")
def clear_cv_cache() -> Dict[str, Any]:
    """Invalida todas las cachés de CV (memoria RAM y SQLite cv_cache) y recalcula los términos del CV activo."""
    from ...tailoring.cv_reader import invalidate_cv_cache, get_active_cv_text_and_meta, extract_search_terms_from_cv
    invalidate_cv_cache(None)

    pointer = read_active_cv_pointer()
    sel_name = pointer.get("selected_filename", "none")
    recalculated = False

    if sel_name and sel_name not in ("none", "default"):
        try:
            cv_text, _ = get_active_cv_text_and_meta(force_refresh=True)
            new_info = extract_search_terms_from_cv(cv_text, sel_name)
            write_active_cv_pointer(
                sel_name,
                search_terms=new_info.get("search_terms", []),
                primary_role=new_info.get("primary_role", ""),
            )
            recalculated = True
        except Exception as e:
            logger.warning("Error recalculando términos de CV tras limpiar caché: %s", e)

    db = get_db()
    db.log_event("INFO", "cv", "Caché de currículums invalidada y términos sincronizados.")

    return {
        "success": True,
        "message": "Caché de CVs eliminada y términos del perfil re-sincronizados correctamente.",
        "recalculated": recalculated,
        "active_info": _get_active_cv_info(),
    }


