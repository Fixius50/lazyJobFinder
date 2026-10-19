"""Módulo de lectura y extracción de texto de currículums (PDF, Markdown y Texto plano).

Permite que lazyJobFinder lea directamente archivos CV en formato PDF (.pdf), Markdown (.md)
y texto (.txt) cargados por el usuario, extrayendo el contenido textual para contrastarlo
en el motor de evaluación y scoring, sin depender de servicios externos.
"""

import json
import logging
import os
import re
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("lazyJobFinder.tailoring.cv_reader")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UPLOAD_DIR = os.path.join(BASE_DIR, "data", "uploaded_cvs")
BASE_CV_PATH = os.path.join(BASE_DIR, "config", "cv_base.md")
ACTIVE_CV_CONFIG_FILE = os.path.join(BASE_DIR, "data", "active_cv.json")


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extrae el contenido textual de un archivo PDF utilizando pypdf con fallback heurístico."""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Archivo PDF no encontrado: {pdf_path}")

    text_parts = []

    # 1. Intentar con pypdf (librería pura de Python sin dependencias binarias externas)
    try:
        import pypdf
        reader = pypdf.PdfReader(pdf_path)
        for page_num, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text.strip())
        if text_parts:
            logger.info("PDF parseado con pypdf: %d páginas extraídas de %s", len(reader.pages), pdf_path)
            return "\n\n".join(text_parts)
    except ImportError:
        logger.warning("pypdf no está instalado en el entorno. Intentando fallback regex sobre streams PDF...")
    except Exception as e:
        logger.warning("Error extrayendo texto con pypdf de %s: %s", pdf_path, e)

    # 2. Fallback heurístico: buscar bloques de texto (BT ... ET) en streams descompresos del PDF
    try:
        with open(pdf_path, "rb") as f:
            content = f.read()
        # Buscar cadenas de texto entre paréntesis típicas de operadores Tj y TJ en PDF
        matches = re.findall(rb"\(([^\(\)\\]{3,})\)\s*(?:Tj|'|\")", content)
        if matches:
            decoded = [m.decode("latin-1", errors="ignore").strip() for m in matches]
            extracted = " ".join(decoded)
            if len(extracted) > 50:
                logger.info("Texto de PDF recuperado mediante extractor heurístico interno (%d bytes)", len(extracted))
                return extracted
    except Exception as fb_err:
        logger.error("Fallo también en fallback heurístico de PDF: %s", fb_err)

    if not text_parts:
        return "[Aviso: No se pudo extraer texto del PDF. Instala 'pypdf' para soporte completo de lectura de PDF]."
    return "\n\n".join(text_parts)


def extract_cv_text(file_path: str) -> str:
    """Extrae y normaliza el texto de cualquier archivo CV admitido (.pdf, .md, .txt)."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Archivo no encontrado: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        raw_text = extract_text_from_pdf(file_path)
    elif ext in (".md", ".txt"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                raw_text = f.read()
        except UnicodeDecodeError:
            with open(file_path, "r", encoding="latin-1", errors="replace") as f:
                raw_text = f.read()
    else:
        raise ValueError(f"Formato no soportado para extracción de texto: {ext}")

    # Normalizar espacios y saltos de línea excesivos
    normalized = re.sub(r"\r\n|\r", "\n", raw_text)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def get_active_cv_text_and_meta() -> Tuple[str, Dict[str, Any]]:
    """
    Recupera el texto y los metadatos del CV actualmente configurado como activo.
    Si se ha subido y seleccionado un archivo en data/uploaded_cvs/, lee ese archivo.
    Si no hay archivos subidos o está en 'none', devuelve texto vacío con has_cv=False (sin filtrado de CV).
    """
    selected_filename = "none"
    if os.path.exists(ACTIVE_CV_CONFIG_FILE):
        try:
            with open(ACTIVE_CV_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                selected_filename = data.get("selected_filename", "none")
        except Exception:
            selected_filename = "none"

    if selected_filename and selected_filename not in ("none", "default"):
        custom_path = os.path.join(UPLOAD_DIR, os.path.basename(selected_filename))
        if os.path.exists(custom_path):
            try:
                text = extract_cv_text(custom_path)
                return text, {
                    "filename": os.path.basename(custom_path),
                    "path": custom_path,
                    "is_default": False,
                    "type": "custom",
                    "extension": os.path.splitext(custom_path)[1].lower(),
                    "exists": True,
                    "has_cv": True,
                    "char_count": len(text),
                    "word_count": len(text.split()),
                }
            except Exception as e:
                logger.error("Error extrayendo texto del CV activo (%s): %s", custom_path, e)
                return "", {
                    "filename": os.path.basename(custom_path),
                    "path": custom_path,
                    "is_default": False,
                    "type": "custom",
                    "extension": os.path.splitext(custom_path)[1].lower(),
                    "exists": True,
                    "has_cv": False,
                    "error": str(e),
                }

    # Si no hay CV activo configurado:
    return "", {
        "filename": "Ninguno",
        "path": "",
        "is_default": False,
        "type": "none",
        "extension": "",
        "exists": False,
        "has_cv": False,
        "char_count": 0,
        "word_count": 0,
    }
