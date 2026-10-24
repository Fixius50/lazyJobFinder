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


# =============================================================================
# CACHÉ EN DOS NIVELES DE TEXTO DE CV (MEMORIA RAM + TEXTO EN DISCO)
# =============================================================================

# Estructura en memoria: file_path -> (mtime, size_bytes, extracted_text)
_CV_TEXT_CACHE: Dict[str, Tuple[float, int, str]] = {}


def _get_extracted_cache_path(file_path: str) -> str:
    """Devuelve la ruta del archivo de texto plano extraído (.txt) para evitar re-parseos de PDF."""
    dirname = os.path.dirname(os.path.abspath(file_path))
    basename = os.path.basename(file_path)
    return os.path.join(dirname, f".extracted_{basename}.txt")


def invalidate_cv_cache(filename_or_path: Optional[str] = None) -> None:
    """Invalida la caché en memoria y elimina archivos temporales de texto extraído."""
    global _CV_TEXT_CACHE
    if not filename_or_path:
        _CV_TEXT_CACHE.clear()
        logger.debug("Caché de texto de CVs en memoria vaciada por completo.")
        return

    clean_name = os.path.basename(filename_or_path)
    # 1. Limpiar entradas en memoria que coincidan
    keys_to_del = [k for k in _CV_TEXT_CACHE if os.path.basename(k) == clean_name or k == filename_or_path]
    for k in keys_to_del:
        _CV_TEXT_CACHE.pop(k, None)

    # 2. Limpiar archivo de caché en disco si existe
    disk_cache_file = os.path.join(UPLOAD_DIR, f".extracted_{clean_name}.txt")
    if os.path.exists(disk_cache_file):
        try:
            os.remove(disk_cache_file)
            logger.debug("Caché persistente de texto eliminada: %s", disk_cache_file)
        except OSError:
            pass


def extract_cv_text(file_path: str, force_refresh: bool = False) -> str:
    """Extrae y normaliza el texto de cualquier archivo CV admitido (.pdf, .md, .txt).
    
    Implementa caché en dos niveles (memoria RAM y texto plano en disco):
    1. Si ya se extrajo en memoria y el archivo físico no cambió (mtime/size), retorna en 0 ms.
    2. Si el proceso se reinició pero ya existía la extracción previa en disco, lee el .txt directo en <1 ms.
    3. Solo si es la primera vez que se sube o si el archivo fue modificado, parsea el binario PDF con pypdf.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Archivo no encontrado: {file_path}")

    mtime = os.path.getmtime(file_path)
    size = os.path.getsize(file_path)
    cache_path = _get_extracted_cache_path(file_path)

    # Nivel 1: Caché en memoria RAM (ultra-rápido, 0 I/O)
    if not force_refresh and file_path in _CV_TEXT_CACHE:
        cached_mtime, cached_size, cached_text = _CV_TEXT_CACHE[file_path]
        if cached_mtime == mtime and cached_size == size:
            return cached_text

    # Nivel 2: Caché persistente en disco (sin pasar por pypdf)
    if not force_refresh and os.path.exists(cache_path):
        try:
            if os.path.getmtime(cache_path) >= mtime:
                with open(cache_path, "r", encoding="utf-8") as f:
                    text = f.read().strip()
                if text:
                    _CV_TEXT_CACHE[file_path] = (mtime, size, text)
                    return text
        except Exception as read_err:
            logger.debug("Error leyendo caché persistente de CV: %s", read_err)

    # Nivel 3: Extracción real del documento
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
    normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()

    # Guardar en memoria
    _CV_TEXT_CACHE[file_path] = (mtime, size, normalized)

    # Persistir en disco para futuros arranques
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            f.write(normalized)
    except Exception as save_err:
        logger.debug("Error escribiendo caché persistente de CV: %s", save_err)

    return normalized


def get_active_cv_status() -> Dict[str, Any]:
    """Devuelve el estado y metadatos del CV activo sin parsear el archivo (operación ultraligera O(1)).
    
    Usar esta función en endpoints de listado, filtros o comprobaciones de salud para evitar
    el coste innecesario de abrir y procesar archivos PDF en cada interacción.
    """
    pointer = read_active_cv_pointer()
    selected_filename = pointer.get("selected_filename", "none")

    if selected_filename and selected_filename not in ("none", "default"):
        custom_path = os.path.join(UPLOAD_DIR, os.path.basename(selected_filename))
        if os.path.exists(custom_path) and os.path.getsize(custom_path) > 0:
            return {
                "has_cv": True,
                "filename": os.path.basename(custom_path),
                "path": custom_path,
                "search_terms": pointer.get("search_terms", []),
                "primary_role": pointer.get("primary_role", ""),
            }

    return {
        "has_cv": False,
        "filename": "Ninguno",
        "path": "",
        "search_terms": [],
        "primary_role": "",
    }



def _extract_terms_universally_from_text(cv_text: str, filename: Optional[str] = None) -> Dict[str, Any]:
    """Extractor universal de oficios, titulaciones y categorías profesionales directamente del texto del CV."""
    candidates: List[str] = []
    lines = [line.strip() for line in (cv_text or "").splitlines() if line.strip()]

    profile_line_regex = re.compile(
        r"^(?:puesto(?:\s+deseado)?|perfil(?:\s+profesional)?|título(?:\s+profesional)?|"
        r"especialidad|titulaci[oó]n|oficio|categor[ií]a|objetivo(?:\s+profesional)?)\s*[:\-]\s*(.+)$",
        re.IGNORECASE,
    )

    occupational_prefixes = (
        r"t[eé]cnico(?:\s+superior|\s+especialista|\s+en|\s+medio)?|"
        r"oficial(?:\s+de|\s+\d[ªa])?|"
        r"auxiliar(?:\s+de)?|"
        r"responsable(?:\s+de)?|"
        r"coordinador(?:\s+de)?|"
        r"especialista(?:\s+en)?|"
        r"operario(?:\s+de)?|"
        r"conductor(?:\s+de)?|"
        r"ch[oó]fer(?:\s+de)?|"
        r"profesor(?:\s+de)?|"
        r"maestro(?:\s+de)?|"
        r"ingeniero(?:\s+de|\s+en)?|"
        r"licenciado(?:\s+en)?|"
        r"graduado(?:\s+en)?|"
        r"diseñador(?:\s+gr[aá]fico|\s+web|\s+de|\s+industrial)?|"
        r"consultor(?:\s+de|\s+en)?|"
        r"analista(?:\s+de|\s+en)?|"
        r"gestor(?:\s+de)?|"
        r"jefe(?:\s+de)?|"
        r"encargado(?:\s+de)?|"
        r"asistente(?:\s+de)?|"
        r"dependiente(?:\s+de)?|"
        r"ayudante(?:\s+de)?|"
        r"mozo(?:\s+de)?|"
        r"carretillero(?:\s+de)?|"
        r"camarero(?:\s+de)?|"
        r"cocinero(?:\s+de)?|"
        r"m[eé]dico(?:\s+de)?|"
        r"enfermero(?:\s+de)?|"
        r"abogado(?:\s+de)?|"
        r"asesor(?:\s+de)?|"
        r"instalador(?:\s+de)?|"
        r"mec[aá]nico(?:\s+de)?|"
        r"electricista(?:\s+de)?|"
        r"fontanero(?:\s+de)?|"
        r"soldador(?:\s+de)?|"
        r"carpintero(?:\s+de)?|"
        r"pintor(?:\s+de)?|"
        r"albañil(?:\s+de)?|"
        r"vigilante(?:\s+de)?|"
        r"socorrista(?:\s+de)?|"
        r"veterinario(?:\s+de)?|"
        r"farmac[eé]utico(?:\s+de)?|"
        r"contable(?:\s+de)?|"
        r"recepcionista(?:\s+de)?|"
        r"comercial(?:\s+de)?|"
        r"administrativo(?:\s+de)?|"
        r"programador(?:\s+de)?|"
        r"desarrollador(?:\s+de)?"
    )

    role_regex = re.compile(
        rf"\b((?:{occupational_prefixes})\s+[a-záéíóúñA-ZÁÉÍÓÚÑ]+(?:\s+[a-záéíóúñA-ZÁÉÍÓÚÑ]+){{0,3}})\b",
        re.IGNORECASE,
    )

    # 1. Buscar campos explícitos de perfil / objetivo en las primeras líneas
    for line in lines[:30]:
        m = profile_line_regex.match(line)
        if m:
            val = m.group(1).strip()
            val = re.split(r"[\.,;\(\)\-–]", val)[0].strip()
            if 3 <= len(val) <= 45:
                candidates.append(val.title())

    # 2. Buscar roles ocupacionales mediante regex en el texto
    for line in lines[:50]:
        if any(w in line.lower() for w in ("calle", "avda", "teléfono", "telefono", "email", "dni", "código postal", "españa")):
            continue
        matches = role_regex.findall(line)
        for match in matches:
            clean_m = re.sub(r"\s+", " ", match).strip()
            clean_m = re.split(r"[\.,;\(\)\-–]", clean_m)[0].strip()
            clean_m = re.sub(r"\s+(?:de|en|y|o|con|para|del|al)$", "", clean_m, flags=re.IGNORECASE).strip()
            if 4 <= len(clean_m) <= 45:
                candidates.append(clean_m.title())

    # 3. Analizar nombre de archivo solo para términos sectoriales significativos
    if filename:
        clean_fn = re.sub(r"^(?:cv[_\-\s]*|curriculum[_\-\s]*|hoja[_\-\s]*de[_\-\s]*vida[_\-\s]*)", "", filename, flags=re.IGNORECASE)
        clean_fn = re.sub(r"[\._\-]\w+$", "", clean_fn)
        clean_fn = re.sub(r"\d+", "", clean_fn)
        parts = [p.strip() for p in re.split(r"[_\-\s]+", clean_fn) if len(p.strip()) >= 4]
        for part in parts:
            if any(term in part.lower() for term in (
                "fontaner", "electric", "mecanic", "abogad", "sanitar", "enferm",
                "admin", "comerc", "cocin", "camarer", "mozo", "almacen",
                "grafic", "softw", "program", "veterinar", "vigilant"
            )):
                candidates.append(part.title())

    # 4. Deduplicar manteniendo orden
    seen = set()
    unique_candidates = []
    for c in candidates:
        norm = c.lower().strip()
        if norm not in seen and len(norm) >= 4:
            seen.add(norm)
            unique_candidates.append(c)

    # 5. Si aún no hay nada (formato no estándar), tomar el primer encabezado relevante
    if not unique_candidates and lines:
        for line in lines[:10]:
            clean = re.split(r"[\.,;\(\)\-–]", line)[0].strip()
            if 4 <= len(clean) <= 40 and not any(w in clean.lower() for w in ("teléfono", "email", "calle", "curriculum", "contacto")):
                unique_candidates.append(clean.title())
                break

    primary_role = unique_candidates[0] if unique_candidates else "Profesional"
    search_terms = unique_candidates[:4]

    return {
        "search_terms": search_terms,
        "primary_role": primary_role,
    }


def extract_search_terms_from_cv(cv_text: str, filename: Optional[str] = None) -> Dict[str, Any]:
    """
    Analiza el texto de cualquier CV y su nombre de archivo para deducir de forma universal
    entre 2 y 4 términos óptimos de búsqueda en portales de empleo (InfoJobs, Indeed, LinkedIn, etc.),
    válido para cualquier profesión u oficio sin asumir profesiones preconcebidas.
    """
    combined_ctx = f"{filename or ''} {cv_text or ''}".strip()
    if len(combined_ctx) < 10:
        return {
            "search_terms": [],
            "primary_role": "",
        }

    # 1. Intentar inferencia abierta con Ollama si está disponible en Docker
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
                f"TEXTO DEL CV:\n{cv_text[:2000]}"
            )
            raw = ollama.generate(prompt=prompt, format_json=True, timeout=15)
            data = json.loads(raw)
            terms = data.get("search_terms", [])
            if isinstance(terms, list) and len(terms) > 0:
                cleaned_terms = [str(t).strip() for t in terms if str(t).strip()]
                if cleaned_terms:
                    role = str(data.get("primary_role", cleaned_terms[0]))
                    logger.info("Términos de búsqueda extraídos del CV con Ollama: %s (Rol: %s)", cleaned_terms, role)
                    return {
                        "search_terms": cleaned_terms[:4],
                        "primary_role": role,
                    }
    except Exception as e:
        logger.debug("Ollama no disponible para extracción de términos (%s). Usando extractor universal de texto.", e)

    # 2. Extractor universal adaptativo basado en NLP y patrones ocupacionales reales
    fallback = _extract_terms_universally_from_text(cv_text, filename)
    if fallback.get("search_terms"):
        logger.info(
            "Términos universales determinados para CV '%s': %s (Rol: %s)",
            filename or "cv",
            fallback["search_terms"],
            fallback["primary_role"],
        )
        return fallback

    return {
        "search_terms": [],
        "primary_role": "",
    }



def get_active_cv_text_and_meta(force_refresh: bool = False) -> Tuple[str, Dict[str, Any]]:
    """
    Recupera el texto y los metadatos del CV actualmente configurado como activo,
    incluyendo sus términos de búsqueda adaptados universalmente.
    Aprovecha la caché en dos niveles para evitar re-parseos innecesarios.
    """
    pointer = read_active_cv_pointer()
    selected_filename = pointer.get("selected_filename", "none")

    if selected_filename and selected_filename not in ("none", "default"):
        custom_path = os.path.join(UPLOAD_DIR, os.path.basename(selected_filename))
        if os.path.exists(custom_path):
            try:
                text = extract_cv_text(custom_path, force_refresh=force_refresh)
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
