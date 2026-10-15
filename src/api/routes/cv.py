"""Rutas de gestión de CV: validación estricta, subida local y control del CV activo."""

import hashlib
import logging
import os
import re
import shutil
import time
from typing import Any, Dict, List
from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from ...shared_constants import CV_LIMITS
from ..deps import get_db

logger = logging.getLogger("lazyJobFinder.api.cv")
router = APIRouter(prefix="/cv", tags=["CV y Perfil"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
UPLOAD_DIR = os.path.join(BASE_DIR, "data", "uploaded_cvs")
BASE_CV_PATH = os.path.join(BASE_DIR, "config", "cv_base.md")
ACTIVE_CV_CONFIG_FILE = os.path.join(BASE_DIR, "data", "active_cv.json")

ALLOWED_EXTENSIONS = set(CV_LIMITS.get("allowed_extensions", [".pdf", ".md", ".txt"]))
MAX_FILE_SIZE_BYTES = CV_LIMITS.get("max_size_bytes", 5 * 1024 * 1024)


class SelectCVRequest(BaseModel):
    filename: str  # "default" o nombre exacto del archivo en data/uploaded_cvs/


def _ensure_upload_dir():
    os.makedirs(UPLOAD_DIR, exist_ok=True)


def _get_active_cv_info() -> Dict[str, Any]:
    """Recupera la información del CV actualmente seleccionado sin enviar datos a la IA."""
    _ensure_upload_dir()
    selected_filename = "default"
    if os.path.exists(ACTIVE_CV_CONFIG_FILE):
        try:
            import json
            with open(ACTIVE_CV_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                selected_filename = data.get("selected_filename", "default")
        except Exception:
            selected_filename = "default"

    if selected_filename == "default" or not os.path.exists(os.path.join(UPLOAD_DIR, selected_filename)):
        # CV Base Canónico
        if os.path.exists(BASE_CV_PATH):
            stat = os.stat(BASE_CV_PATH)
            return {
                "type": "canonical",
                "filename": "cv_base.md",
                "path": "config/cv_base.md",
                "size_bytes": stat.st_size,
                "modified_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
                "is_default": True,
                "description": "Perfil maestro canónico verificado (config/cv_base.md).",
            }
        return {
            "type": "none",
            "filename": "Ninguno",
            "size_bytes": 0,
            "modified_at": "n/a",
            "is_default": True,
            "description": "No se encontró el CV base.",
        }

    # Archivo subido activo
    target_path = os.path.join(UPLOAD_DIR, selected_filename)
    stat = os.stat(target_path)
    return {
        "type": "custom",
        "filename": selected_filename,
        "path": f"data/uploaded_cvs/{selected_filename}",
        "size_bytes": stat.st_size,
        "modified_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
        "is_default": False,
        "description": "CV personalizado cargado localmente.",
    }


@router.get("/active")
def get_active_cv() -> Dict[str, Any]:
    """Devuelve el estado del CV activo actual."""
    return _get_active_cv_info()


@router.get("/list")
def list_uploaded_cvs() -> List[Dict[str, Any]]:
    """Lista los archivos CV disponibles en el repositorio local sin leer su contenido."""
    _ensure_upload_dir()
    cvs = []

    # 1. Base canónico siempre presente
    if os.path.exists(BASE_CV_PATH):
        stat = os.stat(BASE_CV_PATH)
        cvs.append({
            "filename": "cv_base.md",
            "id": "default",
            "is_default": True,
            "size_bytes": stat.st_size,
            "modified_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
        })

    # 2. Subidos a data/uploaded_cvs/
    if os.path.exists(UPLOAD_DIR):
        for entry in os.scandir(UPLOAD_DIR):
            if entry.is_file():
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

    # Registrar en base de datos para auditoría
    db = get_db()
    db.log_event("INFO", "cv", f"Archivo CV subido correctamente: {safe_filename} ({total_bytes} bytes)")

    return {
        "success": True,
        "filename": safe_filename,
        "original_name": filename,
        "size_bytes": total_bytes,
        "message": "Archivo CV subido y almacenado de forma segura en almacenamiento local.",
    }


@router.post("/select")
def select_active_cv(req: SelectCVRequest) -> Dict[str, Any]:
    """Selecciona qué CV actúa como referencia activa en la interfaz."""
    _ensure_upload_dir()
    choice = req.filename.strip()

    if choice != "default":
        # Evitar directory traversal
        clean_name = os.path.basename(choice)
        full_path = os.path.join(UPLOAD_DIR, clean_name)
        if not os.path.exists(full_path):
            raise HTTPException(status_code=404, detail="El archivo CV seleccionado no existe.")
        choice = clean_name

    import json
    with open(ACTIVE_CV_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"selected_filename": choice, "updated_at": time.time()}, f)

    db = get_db()
    db.log_event("INFO", "cv", f"CV activo actualizado a: {choice}")

    return {
        "success": True,
        "selected": choice,
        "active_info": _get_active_cv_info(),
    }
