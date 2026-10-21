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

from ..storage import (
    ACTIVE_CV_FILE as ACTIVE_CV_CONFIG_FILE,
    BASE_CV_FILE as BASE_CV_PATH,
    PROJECT_ROOT as BASE_DIR,
    UPLOAD_DIR,
    read_active_cv_pointer,
)


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


def extract_search_terms_from_cv(cv_text: str) -> Dict[str, Any]:
    """
    Analiza el texto de cualquier CV para deducir de forma universal y sin plantillas
    entre 2 y 4 términos óptimos de búsqueda en portales de empleo (InfoJobs, Indeed, LinkedIn, etc.),
    válido para cualquier profesión (mozo de almacén, fontanero, sanitario, administrativo, etc.).
    """
    if not cv_text or len(cv_text.strip()) < 20:
        return {
            "search_terms": [],
            "primary_role": "",
        }

    # 1. Intentar inferencia abierta con Ollama adaptada estrictamente al texto del CV
    try:
        from ..evaluator.ollama_client import OllamaClient
        ollama = OllamaClient()
        health = ollama.check_health()
        if health.get("online"):
            prompt = (
                "Analiza el siguiente texto de currículum o certificación laboral.\n"
                "Identifica qué oficio, profesión o puesto de trabajo real busca o domina el candidato según su contenido.\n"
                "Devuelve ÚNICAMENTE un JSON con este formato:\n"
                "{\n"
                '  "search_terms": ["Puesto 1", "Puesto 2", "Puesto 3"],\n'
                '  "primary_role": "Nombre de la profesión principal"\n'
                "}\n\n"
                "REGLAS OBLIGATORIAS:\n"
                "- 'search_terms' debe contener de 2 a 4 títulos de búsqueda de empleo habituales en España que encajen estrictamente con este CV.\n"
                "- Basa los títulos ÚNICAMENTE en la experiencia, formación o competencias descritas en el CV. No inventes oficios de otros sectores.\n\n"
                f"TEXTO DEL CV:\n{cv_text[:3000]}"
            )
            raw = ollama.generate(prompt=prompt, format_json=True, timeout=25)
            data = json.loads(raw)
            terms = data.get("search_terms", [])
            if isinstance(terms, list) and len(terms) > 0:
                cleaned_terms = [str(t).strip() for t in terms if str(t).strip()]
                if cleaned_terms:
                    logger.info("Términos de búsqueda extraídos del CV con Ollama: %s", cleaned_terms)
                    return {
                        "search_terms": cleaned_terms[:4],
                        "primary_role": str(data.get("primary_role", cleaned_terms[0])),
                    }
    except Exception as e:
        logger.debug("Ollama no disponible para extracción de términos (%s), usando heurística directa", e)

    # 2. Extracción semántica directa basada en palabras clave del propio texto
    text_low = cv_text.lower()
    terms = []

    if any(k in text_low for k in ("carretill", "traspaleta", "almacén", "almacen", "logística", "logistica", "picking", "pedidos")):
        terms = ["Mozo de almacén", "Carretillero", "Operario de logística"]
    elif any(k in text_low for k in ("camarer", "cociner", "hostelería", "hosteleria", "barista")):
        terms = ["Camarero", "Ayudante de cocina", "Personal de hostelería"]
    elif any(k in text_low for k in ("administrativ", "contab", "facturac", "recepcionista", "oficinista")):
        terms = ["Auxiliar administrativo", "Administrativo contable", "Recepcionista"]
    elif any(k in text_low for k in ("enferm", "sanitar", "auxiliar de enfermería", "tcae", "médic", "medic")):
        terms = ["Enfermero", "Auxiliar de enfermería", "Personal sanitario"]
    elif any(k in text_low for k in ("electricis", "instalador", "fontaner", "climatizac", "mantenimiento industrial")):
        terms = ["Electricista", "Técnico instalador", "Oficial de mantenimiento"]
    elif any(k in text_low for k in ("dependient", "cajer", "ventas", "comercial", "atención al cliente")):
        terms = ["Dependiente", "Comercial de ventas", "Atención al cliente"]
    elif any(k in text_low for k in ("programad", "desarroll", "software", "full stack", "frontend", "backend")):
        terms = ["Desarrollador Software", "Programador", "Desarrollador Web"]

    if terms:
        return {
            "search_terms": terms[:4],
            "primary_role": terms[0],
        }

    return {
        "search_terms": [],
        "primary_role": "",
    }


def get_active_cv_text_and_meta() -> Tuple[str, Dict[str, Any]]:
    """
    Recupera el texto y los metadatos del CV actualmente configurado como activo,
    incluyendo sus términos de búsqueda adaptados universalmente.
    Si se ha subido y seleccionado un archivo en data/uploaded_cvs/, lee ese archivo.
    Si no hay archivos subidos o está en 'none', devuelve texto vacío con has_cv=False (sin filtrado de CV).
    """
    pointer = read_active_cv_pointer()
    selected_filename = pointer.get("selected_filename", "none")

    if selected_filename and selected_filename not in ("none", "default"):
        custom_path = os.path.join(UPLOAD_DIR, os.path.basename(selected_filename))
        if os.path.exists(custom_path):
            try:
                text = extract_cv_text(custom_path)
                cached_terms = pointer.get("search_terms") or []
                primary_role = pointer.get("primary_role", "")

                # Si no estaban calculados los términos en el puntero, extraerlos ahora
                if not cached_terms or not primary_role:
                    profile_info = extract_search_terms_from_cv(text)
                    cached_terms = profile_info.get("search_terms", [])
                    primary_role = profile_info.get("primary_role", "")
                    try:
                        from ..storage import write_active_cv_pointer
                        write_active_cv_pointer(
                            selected_filename,
                            search_terms=cached_terms,
                            primary_role=primary_role,
                        )
                    except Exception as w_err:
                        logger.debug("Error persistiendo terminos de busqueda en pointer: %s", w_err)

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
                    "search_terms": cached_terms,
                    "primary_role": primary_role,
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
                    "search_terms": [],
                    "primary_role": "",
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
        "search_terms": [],
        "primary_role": "",
        "char_count": 0,
        "word_count": 0,
    }
