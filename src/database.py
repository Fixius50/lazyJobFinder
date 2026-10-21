"""Módulo de persistencia local en SQLite con modo WAL y deduplicación avanzada para lazyJobFinder."""

import collections
import hashlib
import json
import logging
import os
import re
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from .migrations.migrator import DatabaseMigrator

try:
    from rapidfuzz import fuzz
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False

logger = logging.getLogger("lazyJobFinder.database")

from .storage import DB_PATH as DEFAULT_DB_PATH, CONSTANTS_FILE


def _load_shared_constants() -> Dict[str, Any]:
    """Carga dinámicamente las constantes y definiciones de filtros desde shared_constants.json sin hardcodeos."""
    try:
        if os.path.exists(CONSTANTS_FILE):
            with open(CONSTANTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.debug("No se pudo cargar shared_constants.json: %s", e)
    return {}


def _decode_row_json_fields(row_data: Dict[str, Any]) -> Dict[str, Any]:
    """Decodifica dinámicamente cualquier campo serializado en JSON (listas o diccionarios)."""
    for key, val in list(row_data.items()):
        if isinstance(val, str) and len(val) >= 2:
            first, last = val[0], val[-1]
            if (first == "[" and last == "]") or (first == "{" and last == "}"):
                try:
                    row_data[key] = json.loads(val)
                except Exception:
                    pass
    return row_data



def canonicalize_url(raw_url: str) -> str:
    """Elimina parámetros de rastreo y normaliza la URL para deduplicación exacta."""
    if not raw_url:
        return ""
    try:
        parsed = urlparse(raw_url.strip())
        tracking_params = {
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "utm_term",
            "utm_content",
            "ref",
            "refid",
            "trackingid",
            "trk",
            "position",
            "pagenum",
            "currentjobid",
            "fbclid",
            "gclid",
            "originalsubdomain",
        }
        query_dict = parse_qs(parsed.query)
        cleaned_query = {k: v for k, v in query_dict.items() if k.lower() not in tracking_params}
        new_query = urlencode(cleaned_query, doseq=True)
        canonical = urlunparse(
            (
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                parsed.path.rstrip("/"),
                parsed.params,
                new_query,
                "",
            )
        )
        return canonical
    except Exception as e:
        logger.debug("Error normalizando URL %s: %s", raw_url, e)
        return raw_url.strip()


def compute_url_hash(url: str, title: str = "", company: str = "") -> str:
    """Calcula un hash SHA-256 canónico de la URL."""
    canon_url = canonicalize_url(url)
    if canon_url:
        return hashlib.sha256(canon_url.encode("utf-8")).hexdigest()
    fallback_key = f"{title.lower().strip()}_{company.lower().strip()}"
    return hashlib.sha256(fallback_key.encode("utf-8")).hexdigest()


def compute_content_fingerprint(title: str, company: str, location: str) -> str:
    """
    Calcula una huella semántica normalizada para detectar la misma oferta
    publicada simultáneamente en diferentes portales (ej. Indeed y LinkedIn).
    """
    # Normalizar empresa (quitar s.l., s.a., inc., etc.)
    comp_clean = re.sub(r"\b(s\.?l\.?|s\.?a\.?|inc\.?|llc|spain|españa)\b", "", company.lower())
    comp_clean = re.sub(r"[^\w\s]", "", comp_clean).strip()
    comp_clean = re.sub(r"\s+", " ", comp_clean)

    # Normalizar título (quitar puntuación y espacios extras)
    title_clean = re.sub(r"[^\w\s]", "", title.lower()).strip()
    title_clean = re.sub(r"\s+", " ", title_clean)

    # Normalizar ubicación
    loc_clean = re.sub(r"[^\w\s]", "", location.lower()).strip()
    loc_clean = re.sub(r"\s+", " ", loc_clean)

    composite = f"{comp_clean}|{title_clean}|{loc_clean}"
    return hashlib.sha256(composite.encode("utf-8")).hexdigest()


def compute_description_hash(description: str) -> str:
    """Calcula el hash del cuerpo de la descripción para detectar actualizaciones relevantes."""
    clean_desc = re.sub(r"\s+", " ", description.strip().lower())
    return hashlib.sha256(clean_desc.encode("utf-8")).hexdigest()


class Database:
    """Gestor de base de datos SQLite con conexión segura y soporte WAL."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.getenv("DATABASE_PATH", DEFAULT_DB_PATH)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def init_db(self) -> None:
        """Crea o actualiza las tablas e índices necesarios."""
        with self._get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url_hash TEXT UNIQUE NOT NULL,
                    content_fingerprint TEXT NOT NULL,
                    description_hash TEXT,
                    canonical_url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    company TEXT NOT NULL,
                    location TEXT,
                    is_remote INTEGER DEFAULT 0,
                    source TEXT NOT NULL,
                    description TEXT,
                    salary_min REAL,
                    salary_max REAL,
                    salary_currency TEXT,
                    date_posted TEXT,
                    created_at TEXT DEFAULT (datetime('now', 'localtime')),
                    updated_at TEXT DEFAULT (datetime('now', 'localtime')),
                    status TEXT DEFAULT 'discovered',
                    duplicate_of_id INTEGER REFERENCES jobs(id) ON DELETE SET NULL,
                    similarity_score REAL,
                    alternate_sources TEXT DEFAULT '[]',
                    telegram_notified INTEGER DEFAULT 0,
                    ui_saved INTEGER DEFAULT 1
                );

                CREATE INDEX IF NOT EXISTS idx_jobs_url_hash ON jobs(url_hash);
                CREATE INDEX IF NOT EXISTS idx_jobs_fingerprint ON jobs(content_fingerprint);
                CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
                CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at);
                CREATE INDEX IF NOT EXISTS idx_jobs_duplicate_of ON jobs(duplicate_of_id);
                CREATE INDEX IF NOT EXISTS idx_jobs_notification_channels ON jobs(telegram_notified, ui_saved);

                CREATE TABLE IF NOT EXISTS evaluations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                    score INTEGER NOT NULL,
                    fit_level TEXT NOT NULL,
                    matched_skills TEXT,
                    missing_skills TEXT,
                    strengths TEXT,
                    gaps TEXT,
                    reasoning TEXT NOT NULL,
                    should_apply INTEGER NOT NULL,
                    created_at TEXT DEFAULT (datetime('now', 'localtime')),
                    UNIQUE(job_id)
                );

                CREATE INDEX IF NOT EXISTS idx_evaluations_score ON evaluations(score);

                CREATE TABLE IF NOT EXISTS generated_documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                    cv_pdf_path TEXT,
                    cv_md_path TEXT,
                    letter_pdf_path TEXT,
                    letter_md_path TEXT,
                    diff_summary TEXT,
                    created_at TEXT DEFAULT (datetime('now', 'localtime')),
                    UNIQUE(job_id)
                );

                CREATE TABLE IF NOT EXISTS pipeline_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT DEFAULT (datetime('now', 'localtime')),
                    finished_at TEXT,
                    trigger_type TEXT NOT NULL, -- 'scheduled', 'manual', 'catch_up'
                    status TEXT NOT NULL,       -- 'running', 'completed', 'failed'
                    total_found INTEGER DEFAULT 0,
                    new_jobs INTEGER DEFAULT 0,
                    relevant_jobs INTEGER DEFAULT 0,
                    error_message TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started ON pipeline_runs(started_at);

                CREATE TABLE IF NOT EXISTS system_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT DEFAULT (datetime('now', 'localtime')),
                    level TEXT NOT NULL,
                    source TEXT NOT NULL,
                    message TEXT NOT NULL,
                    details TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_system_logs_timestamp ON system_logs(timestamp);
                """
            )
        # Ejecutar migraciones incrementales no destructivas para bases de datos existentes
        try:
            migrator = DatabaseMigrator(self.db_path)
            migrator.run_migrations_safely()
        except Exception as e:
            logger.error("Error aplicando migraciones no destructivas: %s", e)

        # Recuperar ejecuciones interrumpidas en el último reinicio
        self.recover_interrupted_runs()
        self.prune_old_system_logs()

        logger.info("Base de datos inicializada correctamente en %s", self.db_path)

    def job_exists(self, url_hash: str) -> bool:
        """Comprueba si una oferta con este hash de URL ya existe."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT 1 FROM jobs WHERE url_hash = ? LIMIT 1", (url_hash,))
            return cursor.fetchone() is not None

    def find_cross_portal_duplicate(self, content_fingerprint: str, days_window: int = 14) -> Optional[int]:
        """
        Detecta si la misma vacante ya fue registrada a través de otro portal
        en los últimos `days_window` días. Resuelve siempre la raíz canónica
        para evitar cadenas de referencias (A -> B -> C).
        """
        with self._get_connection() as conn:
            query = """
                SELECT id, duplicate_of_id FROM jobs 
                WHERE content_fingerprint = ? 
                  AND date(created_at) >= date('now', '-' || ? || ' days', 'localtime')
                ORDER BY id ASC LIMIT 1
            """
            cursor = conn.execute(query, (content_fingerprint, days_window))
            row = cursor.fetchone()
            if not row:
                return None
            return row["duplicate_of_id"] if row["duplicate_of_id"] else row["id"]

    def recover_interrupted_runs(self) -> int:
        """Detecta ejecuciones en estado 'running' tras caídas o reinicios y las marca como 'interrupted'."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE pipeline_runs 
                SET status = 'interrupted',
                    finished_at = datetime('now', 'localtime'),
                    error_message = 'Interrumpido por reinicio o detención del contenedor'
                WHERE status = 'running'
                """
            )
            count = cursor.rowcount
            if count > 0:
                logger.warning("Recuperadas %d ejecuciones interrumpidas en pipeline_runs.", count)
            return count

    def record_skipped_days(self) -> int:
        """
        Inspecciona el histórico de pipeline_runs y registra formalmente como 'skipped'
        los días en los que el sistema estuvo completamente apagado, garantizando que
        no se ejecuten búsquedas múltiples atrasadas en ráfaga.
        """
        last_run = self.get_last_completed_run()
        if not last_run or not last_run.get("started_at"):
            return 0

        last_date_str = str(last_run["started_at"]).split()[0]
        try:
            last_date = datetime.strptime(last_date_str, "%Y-%m-%d").date()
            today = datetime.now().date()
            delta_days = (today - last_date).days
        except Exception as e:
            logger.debug("Error calculando días omitidos: %s", e)
            return 0

        if delta_days <= 1:
            return 0

        skipped_count = 0
        with self._get_connection() as conn:
            for d in range(1, delta_days):
                skipped_date = last_date + timedelta(days=d)
                date_str = skipped_date.strftime("%Y-%m-%d")

                # Comprobar si ya existe algún registro para esa fecha
                existing = conn.execute(
                    "SELECT 1 FROM pipeline_runs WHERE date(started_at) = ? LIMIT 1",
                    (date_str,),
                ).fetchone()

                if not existing:
                    conn.execute(
                        """
                        INSERT INTO pipeline_runs (
                            started_at, finished_at, trigger_type, status,
                            total_found, new_jobs, relevant_jobs, error_message
                        ) VALUES (?, ?, 'scheduled_skipped', 'skipped', 0, 0, 0, ?)
                        """,
                        (
                            f"{date_str} 08:30:00",
                            f"{date_str} 08:30:00",
                            "Día omitido deliberadamente por apagado prolongado del equipo; se previene saturación en ráfaga.",
                        ),
                    )
                    skipped_count += 1

        if skipped_count > 0:
            logger.info("Registrados formalmente %d días omitidos en pipeline_runs por apagado del equipo.", skipped_count)
        return skipped_count

    def find_fuzzy_duplicate(
        self,
        title: str,
        company: str,
        location: str = "",
        description: str = "",
        days_window: int = 14,
        min_similarity: float = 0.85,
    ) -> Optional[Tuple[int, float]]:
        """
        Detecta si existe una oferta similar usando RapidFuzz combinando similitud
        de empresa, puesto, ubicación y descripción en los últimos `days_window` días.
        Retorna (canonical_id, similarity_score) o None.
        Garantiza que el candidato sea una raíz canónica (duplicate_of_id IS NULL).
        """
        if not RAPIDFUZZ_AVAILABLE or not title or not company:
            return None

        target_comp = re.sub(r"\b(s\.?l\.?|s\.?a\.?|inc\.?|llc|spain|españa)\b", "", company.lower())
        target_comp = re.sub(r"[^\w\s]", "", target_comp).strip()
        target_title = re.sub(r"[^\w\s]", "", title.lower()).strip()
        target_loc = re.sub(r"[^\w\s]", "", location.lower()).strip()
        target_desc_sample = re.sub(r"\s+", " ", description[:500].lower()).strip()

        with self._get_connection() as conn:
            # Consultar exclusivamente raíces canónicas para impedir cadenas de referencias
            cursor = conn.execute(
                """
                SELECT id, title, company, location, description 
                FROM jobs 
                WHERE duplicate_of_id IS NULL
                  AND date(created_at) >= date('now', '-' || ? || ' days', 'localtime')
                ORDER BY id DESC
                """,
                (days_window,),
            )
            candidates = cursor.fetchall()

        for cand in candidates:
            cand_id = cand["id"]
            cand_comp = re.sub(r"\b(s\.?l\.?|s\.?a\.?|inc\.?|llc|spain|españa)\b", "", cand["company"].lower())
            cand_comp = re.sub(r"[^\w\s]", "", cand_comp).strip()
            cand_title = re.sub(r"[^\w\s]", "", cand["title"].lower()).strip()
            cand_loc = re.sub(r"[^\w\s]", "", (cand["location"] or "").lower()).strip()

            # Similitud de empresa (token_set_ratio tolera variaciones de razón social)
            comp_sim = fuzz.token_set_ratio(target_comp, cand_comp) / 100.0
            if comp_sim < 0.75:
                continue

            # Similitud de título
            title_sim = max(
                fuzz.token_sort_ratio(target_title, cand_title) / 100.0,
                fuzz.token_set_ratio(target_title, cand_title) / 100.0,
            )
            if title_sim < 0.70:
                continue

            # Similitud de ubicación y descripción
            loc_sim = fuzz.token_set_ratio(target_loc, cand_loc) / 100.0 if (target_loc and cand_loc) else 0.85
            desc_sim = 0.85
            cand_desc = cand["description"] or ""
            if len(cand_desc) > 80 and len(description) > 80:
                cand_desc_sample = re.sub(r"\s+", " ", cand_desc[:500].lower()).strip()
                desc_sim = fuzz.token_set_ratio(target_desc_sample, cand_desc_sample) / 100.0

            # Puntuación compuesta ponderada (Heurística calibrada)
            composite = (title_sim * 0.40) + (comp_sim * 0.35) + (desc_sim * 0.15) + (loc_sim * 0.10)
            if composite >= min_similarity:
                logger.info(
                    "RapidFuzz: Oferta '%s' (%s) detectada como duplicado de ID canónico %d ('%s', %s) [Similitud: %.2f]",
                    title, company, cand_id, cand["title"], cand["company"], composite
                )
                return cand_id, round(composite, 3)
            elif composite >= 0.75:
                logger.debug(
                    "RapidFuzz caso borderline (no enlazado para evitar falsos positivos): '%.2f' entre '%s' y candidato ID %d",
                    composite, title, cand_id
                )

        return None

    def save_job(self, job_data: Dict[str, Any]) -> Tuple[Optional[int], str]:
        """
        Inserta o actualiza una oferta aplicando deduplicación por URL, huella SHA-256
        y similitud difusa (RapidFuzz), conservando trazabilidad e historial completos.
        
        Retorna (job_id, status_code):
        - status_code: 'inserted' (nueva canónica), 'cross_portal_duplicate' (duplicado enlazado),
          'description_updated' (actualizada), 'already_exists' (idéntica)
        """
        raw_url = job_data.get("job_url", "")
        title = job_data.get("title", "")
        company = job_data.get("company", "")
        location = job_data.get("location", "España")
        description = job_data.get("description", "")
        source = job_data.get("source", "unknown")

        url_hash = compute_url_hash(raw_url, title, company)
        content_fingerprint = compute_content_fingerprint(title, company, location)
        desc_hash = compute_description_hash(description)
        canonical_url = canonicalize_url(raw_url)

        contract_type = job_data.get("contract_type")
        schedule = job_data.get("schedule")
        education_level = job_data.get("education_level")

        # Fallback de normalización desde el texto del portal si no vino estructurado
        if not contract_type and description:
            dl = description.lower()
            if "indefinid" in dl:
                contract_type = "Indefinido"
            elif "temporal" in dl or "duración determinada" in dl:
                contract_type = "Temporal"
            elif "práctica" in dl or "practica" in dl or "beca" in dl:
                contract_type = "Prácticas / Beca"
            elif "freelance" in dl or "autónom" in dl or "autonom" in dl:
                contract_type = "Autónomo / Freelance"

        if not schedule and description:
            dl = description.lower()
            if "completa" in dl or "full-time" in dl or "full time" in dl:
                schedule = "Jornada Completa"
            elif "parcial" in dl or "media jornada" in dl or "part-time" in dl:
                schedule = "Media Jornada"
            elif "flexible" in dl:
                schedule = "Horario Flexible"

        if not education_level and description:
            dl = description.lower()
            if any(k in dl for k in ["grado", "ingenier", "universit", "licenciat"]):
                education_level = "Grado / Universidad"
            elif any(k in dl for k in ["fp", "ciclo formativo", "módulo", "formación profesional"]):
                education_level = "FP / Ciclo Formativo"
            elif any(k in dl for k in ["master", "máster", "postgrado"]):
                education_level = "Máster / Postgrado"

        from .storage import read_active_cv_pointer
        cv_filename = job_data.get("cv_filename") or read_active_cv_pointer()
        if cv_filename in ("none", "Ninguno", ""):
            cv_filename = None

        with self._get_connection() as conn:
            # 1. Comprobar si ya existe por URL exacta
            cursor = conn.execute(
                "SELECT id, description_hash, alternate_sources, cv_filename FROM jobs WHERE url_hash = ?",
                (url_hash,),
            )
            existing = cursor.fetchone()
            if existing:
                existing_id = existing["id"]
                old_desc_hash = existing["description_hash"]
                if cv_filename and not existing.get("cv_filename"):
                    conn.execute("UPDATE jobs SET cv_filename = ? WHERE id = ?", (cv_filename, existing_id))
                # Si cambió la descripción, actualizar registro y registrar timestamp
                if old_desc_hash and old_desc_hash != desc_hash:
                    conn.execute(
                        """
                        UPDATE jobs SET 
                            description = ?,
                            description_hash = ?,
                            contract_type = COALESCE(?, contract_type),
                            schedule = COALESCE(?, schedule),
                            education_level = COALESCE(?, education_level),
                            updated_at = datetime('now', 'localtime')
                        WHERE id = ?
                        """,
                        (description, desc_hash, contract_type, schedule, education_level, existing_id),
                    )
                    logger.info("Descripción actualizada para oferta existente ID %d (%s).", existing_id, title)
                    return existing_id, "description_updated"
                return None, "already_exists"

            # 2. Comprobar deduplicación exacta entre portales por fingerprint
            cross_dup_id = self.find_cross_portal_duplicate(content_fingerprint)
            fuzzy_sim = 1.0 if cross_dup_id else None

            # 3. Comprobar deduplicación difusa (RapidFuzz) si no hubo match exacto
            if not cross_dup_id:
                fuzzy_match = self.find_fuzzy_duplicate(
                    title=title,
                    company=company,
                    location=location,
                    description=description,
                )
                if fuzzy_match:
                    cross_dup_id, fuzzy_sim = fuzzy_match

            # Si es duplicado (exacto o fuzzy), guardar registro enlazado sin descartar historial
            if cross_dup_id:
                # Blindaje anti-cadenas: asegurar que siempre se enlace a la raíz canónica
                canon_root = conn.execute(
                    "SELECT id, duplicate_of_id FROM jobs WHERE id = ?", (cross_dup_id,)
                ).fetchone()
                if canon_root and canon_root["duplicate_of_id"]:
                    cross_dup_id = canon_root["duplicate_of_id"]

                try:
                    cursor = conn.execute(
                        """
                        INSERT INTO jobs (
                            url_hash, content_fingerprint, description_hash, canonical_url,
                            title, company, location, is_remote, source, description,
                            salary_min, salary_max, salary_currency, date_posted, status,
                            duplicate_of_id, similarity_score, contract_type, schedule, education_level,
                            cv_filename
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'duplicate', ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            url_hash, content_fingerprint, desc_hash, canonical_url,
                            title, company, location, 1 if job_data.get("is_remote") else 0,
                            source, description, job_data.get("salary_min"),
                            job_data.get("salary_max"), job_data.get("salary_currency", "EUR"),
                            job_data.get("date_posted", ""), cross_dup_id, fuzzy_sim,
                            contract_type, schedule, education_level,
                            cv_filename
                        ),
                    )
                    dup_row_id = cursor.lastrowid
                    
                    # Actualizar fuentes alternativas en la oferta canónica
                    canon_row = conn.execute("SELECT alternate_sources FROM jobs WHERE id = ?", (cross_dup_id,)).fetchone()
                    alt_sources = []
                    if canon_row and canon_row["alternate_sources"]:
                        try:
                            alt_sources = json.loads(canon_row["alternate_sources"])
                        except Exception:
                            alt_sources = []
                    
                    alt_entry = {"source": source, "url": canonical_url, "date": job_data.get("date_posted", "")}
                    if not any(s.get("url") == canonical_url for s in alt_sources):
                        alt_sources.append(alt_entry)
                        conn.execute(
                            "UPDATE jobs SET alternate_sources = ?, updated_at = datetime('now', 'localtime') WHERE id = ?",
                            (json.dumps(alt_sources, ensure_ascii=False), cross_dup_id)
                        )

                    logger.debug("Oferta '%s' guardada como duplicado enlazado a ID %d (nuevo ID: %d).", title, cross_dup_id, dup_row_id)
                    return dup_row_id, "cross_portal_duplicate"
                except sqlite3.IntegrityError:
                    return None, "already_exists"

            # 4. Inserción de oferta canónica completamente nueva
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO jobs (
                        url_hash, content_fingerprint, description_hash, canonical_url,
                        title, company, location, is_remote, source, description,
                        salary_min, salary_max, salary_currency, date_posted, status,
                        contract_type, schedule, education_level, cv_filename
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        url_hash,
                        content_fingerprint,
                        desc_hash,
                        canonical_url,
                        title,
                        company,
                        location,
                        1 if job_data.get("is_remote") else 0,
                        source,
                        description,
                        job_data.get("salary_min"),
                        job_data.get("salary_max"),
                        job_data.get("salary_currency", "EUR"),
                        job_data.get("date_posted", ""),
                        job_data.get("status", "discovered"),
                        contract_type,
                        schedule,
                        education_level,
                        cv_filename,
                    ),
                )
                return cursor.lastrowid, "inserted"
            except sqlite3.IntegrityError:
                return None, "already_exists"


    def update_job_status(self, job_id: int, status: str) -> None:
        """Actualiza el estado del ciclo de vida de la oferta."""
        with self._get_connection() as conn:
            conn.execute("UPDATE jobs SET status = ?, updated_at = datetime('now', 'localtime') WHERE id = ?", (status, job_id))

    def save_evaluation(self, eval_data: Dict[str, Any]) -> int:
        """Registra o actualiza la evaluación de afinidad de una oferta sin perder historial."""
        job_id = eval_data["job_id"]
        matched = json.dumps(eval_data.get("matched_skills", []), ensure_ascii=False)
        missing = json.dumps(eval_data.get("missing_skills", []), ensure_ascii=False)
        strengths = json.dumps(eval_data.get("strengths", []), ensure_ascii=False)
        gaps = json.dumps(eval_data.get("gaps", []), ensure_ascii=False)

        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO evaluations (
                    job_id, score, fit_level, matched_skills, missing_skills,
                    strengths, gaps, reasoning, should_apply
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    score = excluded.score,
                    fit_level = excluded.fit_level,
                    matched_skills = excluded.matched_skills,
                    missing_skills = excluded.missing_skills,
                    strengths = excluded.strengths,
                    gaps = excluded.gaps,
                    reasoning = excluded.reasoning,
                    should_apply = excluded.should_apply,
                    created_at = datetime('now', 'localtime')
                """,
                (
                    job_id,
                    eval_data.get("score", 0),
                    eval_data.get("fit_level", "MODERADO"),
                    matched,
                    missing,
                    strengths,
                    gaps,
                    eval_data.get("reasoning", ""),
                    1 if eval_data.get("should_apply") else 0,
                ),
            )
            return cursor.lastrowid

    def save_documents(self, doc_data: Dict[str, Any]) -> int:
        """Registra o actualiza las rutas de los archivos PDF y Markdown generados."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO generated_documents (
                    job_id, cv_pdf_path, cv_md_path, letter_pdf_path,
                    letter_md_path, diff_summary
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    cv_pdf_path = excluded.cv_pdf_path,
                    cv_md_path = excluded.cv_md_path,
                    letter_pdf_path = excluded.letter_pdf_path,
                    letter_md_path = excluded.letter_md_path,
                    diff_summary = excluded.diff_summary,
                    created_at = datetime('now', 'localtime')
                """,
                (
                    doc_data["job_id"],
                    doc_data.get("cv_pdf_path"),
                    doc_data.get("cv_md_path"),
                    doc_data.get("letter_pdf_path"),
                    doc_data.get("letter_md_path"),
                    doc_data.get("diff_summary", ""),
                ),
            )
            return cursor.lastrowid

    def start_pipeline_run(self, trigger_type: str) -> int:
        """Registra el inicio de una ejecución en la tabla persistente pipeline_runs."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO pipeline_runs (trigger_type, status) VALUES (?, 'running')",
                (trigger_type,),
            )
            return cursor.lastrowid

    def finish_pipeline_run(
        self,
        run_id: int,
        status: str,
        total_found: int = 0,
        new_jobs: int = 0,
        relevant_jobs: int = 0,
        error_message: Optional[str] = None,
    ) -> None:
        """Registra la finalización de una ejecución con sus métricas."""
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE pipeline_runs SET 
                    finished_at = datetime('now', 'localtime'),
                    status = ?,
                    total_found = ?,
                    new_jobs = ?,
                    relevant_jobs = ?,
                    error_message = ?
                WHERE id = ?
                """,
                (status, total_found, new_jobs, relevant_jobs, error_message, run_id),
            )

    def has_run_today(self) -> bool:
        """Comprueba si ya se completó con éxito una ejecución en el día natural actual."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT 1 FROM pipeline_runs 
                WHERE status = 'completed' 
                  AND date(started_at) = date('now', 'localtime')
                LIMIT 1
                """
            )
            return cursor.fetchone() is not None

    def get_last_completed_run(self) -> Optional[Dict[str, Any]]:
        """Recupera los datos de la última ejecución exitosa."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM pipeline_runs WHERE status = 'completed' ORDER BY id DESC LIMIT 1"
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_statistics(self) -> Dict[str, Any]:
        """Recupera estadísticas globales para el diagnóstico por Telegram."""
        with self._get_connection() as conn:
            total_jobs = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
            jobs_today = conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE date(created_at) = date('now', 'localtime')"
            ).fetchone()[0]
            total_evaluated = conn.execute("SELECT COUNT(*) FROM evaluations").fetchone()[0]
            high_matches = conn.execute(
                "SELECT COUNT(*) FROM evaluations WHERE score >= 65"
            ).fetchone()[0]
            last_run_row = conn.execute(
                "SELECT finished_at FROM pipeline_runs WHERE status = 'completed' ORDER BY id DESC LIMIT 1"
            ).fetchone()

            return {
                "total_jobs": total_jobs,
                "jobs_today": jobs_today,
                "total_evaluated": total_evaluated,
                "high_matches": high_matches,
                "last_run": last_run_row[0] if last_run_row and last_run_row[0] else "Sin ejecuciones previas",
            }

    def get_top_recent_jobs(self, limit: int = 10, min_score: int = 65) -> List[Dict[str, Any]]:
        """Devuelve las mejores ofertas recientes que superan el umbral."""
        with self._get_connection() as conn:
            query = """
                SELECT j.id, j.title, j.company, j.location, j.canonical_url, j.source, j.created_at,
                       e.score, e.fit_level, e.reasoning, e.matched_skills, e.missing_skills,
                       d.cv_pdf_path, d.letter_pdf_path
                FROM jobs j
                INNER JOIN evaluations e ON j.id = e.job_id
                LEFT JOIN generated_documents d ON j.id = d.job_id
                WHERE e.score >= ?
                ORDER BY e.score DESC, j.created_at DESC
                LIMIT ?
            """
            cursor = conn.execute(query, (min_score, limit))
            results = []
            for row in cursor.fetchall():
                item = dict(row)
                for k in ("matched_skills", "missing_skills"):
                    if item.get(k):
                        try:
                            item[k] = json.loads(item[k])
                        except Exception:
                            pass
                results.append(item)
            return results

    def get_unevaluated_jobs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Recupera ofertas descubiertas pendientes de evaluación o sin registro de evaluación."""
        with self._get_connection() as conn:
            query = """
                SELECT j.* FROM jobs j
                LEFT JOIN evaluations e ON j.id = e.job_id
                WHERE e.id IS NULL OR j.status = 'discovered'
                ORDER BY j.created_at DESC
                LIMIT ?
            """
            cursor = conn.execute(query, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_all_jobs_for_scoring(self, limit: int = 200) -> List[Dict[str, Any]]:
        """Recupera todas las ofertas activas registradas para contrastar afinidad con el CV activo."""
        with self._get_connection() as conn:
            query = """
                SELECT id, title, company, location, is_remote, description, source, created_at
                FROM jobs
                WHERE ui_saved = 1
                ORDER BY id DESC
                LIMIT ?
            """
            cursor = conn.execute(query, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def log_event(self, level: str, source: str, message: str, details: Optional[str] = None) -> None:
        """Registra un evento o error del sistema de forma persistente."""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    "INSERT INTO system_logs (level, source, message, details) VALUES (?, ?, ?, ?)",
                    (level.upper(), source, message, details or ""),
                )
        except Exception as e:
            logger.error("Fallo al escribir en system_logs: %s", e)

    def get_jobs_paginated(
        self,
        search: Optional[str] = None,
        exclude: Optional[str] = None,
        location: Optional[str] = None,
        source: Optional[str] = None,
        status: Optional[str] = None,
        min_score: Optional[int] = None,
        is_remote: Optional[bool] = None,
        modality: Optional[str] = None,
        modalities: Optional[List[str]] = None,
        categories: Optional[List[str]] = None,
        educations: Optional[List[str]] = None,
        min_experience_years: Optional[int] = None,
        min_salary: Optional[float] = None,
        schedules: Optional[List[str]] = None,
        contract_types: Optional[List[str]] = None,
        geo_lat: Optional[float] = None,
        geo_lon: Optional[float] = None,
        geo_radius_km: Optional[float] = None,
        only_ui_saved: bool = True,
        cv_filename: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> Dict[str, Any]:
        """
        Recupera ofertas paginadas con soporte de filtros multicriterio,
        ordenación segura y datos consolidados de evaluación y documentos.
        Por defecto, oculta visualmente ofertas descartadas o que no coinciden con el CV.
        """
        page = max(1, page)
        page_size = min(max(5, page_size), 100)
        offset = (page - 1) * page_size

        allowed_sort_fields = {
            "created_at": "j.created_at",
            "score": "e.score",
            "company": "j.company",
            "title": "j.title",
            "date_posted": "j.date_posted",
        }
        sort_col = allowed_sort_fields.get(sort_by, "j.created_at")
        sort_dir = "ASC" if str(sort_order).lower() == "asc" else "DESC"

        where_clauses = ["1=1"]
        params: List[Any] = []

        from .storage import read_active_cv_pointer
        target_cv = cv_filename
        if target_cv is None:
            target_cv = read_active_cv_pointer()

        if target_cv in ("none", "Ninguno", "") or not target_cv:
            where_clauses.append("1=0")
        else:
            where_clauses.append("(j.cv_filename = ? OR j.cv_filename IS NULL)")
            params.append(str(target_cv).strip())

        if only_ui_saved:
            where_clauses.append("j.ui_saved = 1")

        if search:
            search_param = f"%{search.strip().lower()}%"
            where_clauses.append("(LOWER(j.title) LIKE ? OR LOWER(j.company) LIKE ? OR LOWER(j.location) LIKE ?)")
            params.extend([search_param, search_param, search_param])

        if exclude:
            exclude_terms = [t.strip().lower() for t in exclude.split(",") if t.strip()]
            for term in exclude_terms:
                where_clauses.append("(LOWER(j.title) NOT LIKE ? AND LOWER(j.description) NOT LIKE ?)")
                params.extend([f"%{term}%", f"%{term}%"])

        if source:
            src = str(source).strip().lower()
            if src in ("tecnoempleo", "tecnoempleo_rss"):
                where_clauses.append("j.source IN ('tecnoempleo', 'tecnoempleo_rss')")
            elif src in ("infojobs", "infojobs_api"):
                where_clauses.append("j.source IN ('infojobs', 'infojobs_api')")
            elif src == "jobspy":
                where_clauses.append("j.source IN ('indeed', 'linkedin', 'glassdoor', 'google', 'jobspy')")
            else:
                where_clauses.append("LOWER(j.source) = ?")
                params.append(src)

        if status:
            where_clauses.append("j.status = ?")
            params.append(status)
        else:
            # Por defecto, ocultar visualmente ofertas que no coinciden con el CV aportado (descartadas)
            where_clauses.append("(j.status != 'discarded' AND (e.fit_level IS NULL OR e.fit_level != 'DESCARTADO'))")

        if min_score is not None:
            where_clauses.append("e.score >= ?")
            params.append(min_score)

        # 1. Filtro de modalidades múltiples (Checkboxes)
        active_modalities = [m.lower().strip() for m in (modalities or []) if m and m.lower().strip() not in ("sin_especificar", "todas")]
        if not active_modalities and modality and modality.lower().strip() not in ("sin_especificar", "todas", ""):
            active_modalities = [modality.lower().strip()]

        if active_modalities:
            mod_subclauses = []
            for m in active_modalities:
                if m in ("remoto", "teletrabajo"):
                    mod_subclauses.append("(j.is_remote = 1 OR LOWER(j.location) LIKE '%remoto%' OR LOWER(j.location) LIKE '%teletrabajo%' OR LOWER(j.title) LIKE '%remoto%' OR LOWER(j.title) LIKE '%teletrabajo%')")
                elif m == "hibrido":
                    mod_subclauses.append("(LOWER(j.location) LIKE '%hibrid%' OR LOWER(j.location) LIKE '%híbrid%' OR LOWER(j.title) LIKE '%hibrid%' OR LOWER(j.title) LIKE '%híbrid%' OR LOWER(j.description) LIKE '%híbrido%' OR LOWER(j.description) LIKE '%hibrido%')")
                elif m == "presencial":
                    mod_subclauses.append("(j.is_remote = 0 AND LOWER(j.location) NOT LIKE '%remoto%' AND LOWER(j.location) NOT LIKE '%teletrabajo%' AND LOWER(j.title) NOT LIKE '%remoto%' AND LOWER(j.title) NOT LIKE '%teletrabajo%' AND LOWER(j.location) NOT LIKE '%hibrid%' AND LOWER(j.location) NOT LIKE '%híbrid%')")
            if mod_subclauses:
                where_clauses.append(f"({' OR '.join(mod_subclauses)})")
        elif is_remote is not None:
            where_clauses.append("j.is_remote = ?")
            params.append(1 if is_remote else 0)

        # 2. Filtro de Categoría / Competencias profesionales (Checkboxes) - Extraídas dinámicamente de ofertas
        active_cats = [c.lower().strip() for c in (categories or []) if c and c.lower().strip() not in ("sin_especificar", "todas")]
        if active_cats:
            cat_clauses = []
            for cat in active_cats:
                cat_clauses.append("(LOWER(j.title) LIKE ? OR LOWER(j.description) LIKE ? OR (e.matched_skills IS NOT NULL AND LOWER(e.matched_skills) LIKE ?))")
                params.extend([f"%{cat}%", f"%{cat}%", f"%{cat}%"])
            where_clauses.append(f"({' OR '.join(cat_clauses)})")

        # 3. Filtro de Formación mínima (Checkboxes) - Columna real y descripción
        active_edus = [e.lower().strip() for e in (educations or []) if e and e.lower().strip() not in ("sin_especificar", "todas")]
        if active_edus:
            edu_clauses = []
            for edu in active_edus:
                edu_clauses.append("(LOWER(j.education_level) LIKE ? OR LOWER(j.description) LIKE ?)")
                params.extend([f"%{edu}%", f"%{edu}%"])
            where_clauses.append(f"({' OR '.join(edu_clauses)})")

        # 4. Filtro de Experiencia (Deslizante / Slider)
        # 0=Sin especificar, 1=Junior/Sin experiencia, 2=1+ año, 3=2+ años, 4=3+ años, 5=5+ años
        if min_experience_years and min_experience_years > 0:
            if min_experience_years == 1:
                where_clauses.append("(LOWER(j.title) LIKE '%junior%' OR LOWER(j.title) LIKE '%jr%' OR LOWER(j.title) LIKE '%prácticas%' OR LOWER(j.title) LIKE '%beca%' OR LOWER(j.description) LIKE '%sin experiencia%' OR LOWER(j.description) LIKE '%recién titulado%' OR LOWER(j.description) LIKE '%reciente titulado%' OR LOWER(j.description) LIKE '%0-1 año%' OR LOWER(j.description) LIKE '%sin experiencia requerida%')")
            elif min_experience_years == 2:
                where_clauses.append("(LOWER(j.description) LIKE '%1 año%' OR LOWER(j.description) LIKE '%1+ año%' OR LOWER(j.description) LIKE '%al menos 1 año%' OR LOWER(j.description) LIKE '%mínimo 1 año%')")
            elif min_experience_years == 3:
                where_clauses.append("(LOWER(j.description) LIKE '%2 año%' OR LOWER(j.description) LIKE '%2+ año%' OR LOWER(j.description) LIKE '%al menos 2 año%' OR LOWER(j.description) LIKE '%mínimo 2 año%')")
            elif min_experience_years == 4:
                where_clauses.append("(LOWER(j.description) LIKE '%3 año%' OR LOWER(j.description) LIKE '%3+ año%' OR LOWER(j.description) LIKE '%al menos 3 año%' OR LOWER(j.description) LIKE '%mínimo 3 año%')")
            elif min_experience_years >= 5:
                where_clauses.append("(LOWER(j.description) LIKE '%5 año%' OR LOWER(j.description) LIKE '%5+ año%' OR LOWER(j.description) LIKE '%al menos 5 año%' OR LOWER(j.title) LIKE '%senior%' OR LOWER(j.title) LIKE '%lead%')")

        # 5. Filtro de Salario mínimo (Deslizante / Slider)
        if min_salary and min_salary > 0:
            where_clauses.append("(j.salary_max >= ? OR j.salary_min >= ?)")
            params.extend([min_salary, min_salary])

        # 6. Filtro de Jornada laboral (Checkboxes) - Columna real y descripción
        active_scheds = [s.lower().strip() for s in (schedules or []) if s and s.lower().strip() not in ("sin_especificar", "todas")]
        if active_scheds:
            sched_clauses = []
            for sc in active_scheds:
                sched_clauses.append("(LOWER(j.schedule) LIKE ? OR LOWER(j.description) LIKE ?)")
                params.extend([f"%{sc}%", f"%{sc}%"])
            where_clauses.append(f"({' OR '.join(sched_clauses)})")

        # 7. Filtro de Tipo de contrato (Checkboxes) - Columna real y descripción
        active_contracts = [c.lower().strip() for c in (contract_types or []) if c and c.lower().strip() not in ("sin_especificar", "todas")]
        if active_contracts:
            contract_clauses = []
            for ct in active_contracts:
                contract_clauses.append("(LOWER(j.contract_type) LIKE ? OR LOWER(j.description) LIKE ?)")
                params.extend([f"%{ct}%", f"%{ct}%"])
            where_clauses.append(f"({' OR '.join(contract_clauses)})")

        # 8. Filtro Geográfico y de Área recibido desde el mapa del Frontend
        if location and location.strip() and not any(k in location.lower() for k in ("todos", "all", "cualquiera")):
            loc_val = location.strip()
            where_clauses.append("(LOWER(j.location) LIKE ? OR j.is_remote = 1 OR LOWER(j.location) LIKE '%remot%' OR LOWER(j.location) LIKE '%teletrabaj%')")
            params.append(f"%{loc_val.lower()}%")

        where_str = " AND ".join(where_clauses)

        with self._get_connection() as conn:
            # Conteo total para paginación
            count_sql = f"""
                SELECT COUNT(*) FROM jobs j
                LEFT JOIN evaluations e ON j.id = e.job_id
                WHERE {where_str}
            """
            total_items = conn.execute(count_sql, params).fetchone()[0]

            # Consulta paginada
            query_sql = f"""
                SELECT 
                    j.id, j.title, j.company, j.location, j.is_remote, j.source,
                    j.canonical_url, j.salary_min, j.salary_max, j.salary_currency,
                    j.date_posted, j.created_at, j.updated_at, j.status,
                    j.duplicate_of_id, j.similarity_score, j.alternate_sources,
                    j.telegram_notified, j.ui_saved,
                    e.score, e.fit_level, e.should_apply,
                    d.cv_pdf_path, d.cv_md_path, d.letter_pdf_path, d.letter_md_path
                FROM jobs j
                LEFT JOIN evaluations e ON j.id = e.job_id
                LEFT JOIN generated_documents d ON j.id = d.job_id
                WHERE {where_str}
                ORDER BY {sort_col} {sort_dir}
                LIMIT ? OFFSET ?
            """
            cursor = conn.execute(query_sql, params + [page_size, offset])
            items = []
            for row in cursor.fetchall():
                row_dict = _decode_row_json_fields(dict(row))
                row_dict["has_cv"] = bool(row_dict.get("cv_pdf_path") or row_dict.get("cv_md_path"))
                row_dict["has_letter"] = bool(row_dict.get("letter_pdf_path") or row_dict.get("letter_md_path"))
                items.append(row_dict)

            total_pages = (total_items + page_size - 1) // page_size if total_items > 0 else 1

            return {
                "items": items,
                "total": total_items,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
            }

    def get_job_detail(self, job_id: int) -> Optional[Dict[str, Any]]:
        """Recupera la ficha integral de una vacante, incluyendo análisis de IA y auditoría de documentos."""
        with self._get_connection() as conn:
            query = """
                SELECT 
                    j.*,
                    e.score, e.fit_level, e.matched_skills, e.missing_skills,
                    e.strengths, e.gaps, e.reasoning, e.should_apply,
                    e.created_at AS evaluated_at,
                    d.cv_pdf_path, d.cv_md_path, d.letter_pdf_path, d.letter_md_path,
                    d.diff_summary, d.created_at AS documents_generated_at
                FROM jobs j
                LEFT JOIN evaluations e ON j.id = e.job_id
                LEFT JOIN generated_documents d ON j.id = d.job_id
                WHERE j.id = ?
            """
            cursor = conn.execute(query, (job_id,))
            row = cursor.fetchone()
            if not row:
                return None

            data = _decode_row_json_fields(dict(row))
            for list_field in ("matched_skills", "missing_skills", "strengths", "gaps", "alternate_sources"):
                if not data.get(list_field):
                    data[list_field] = []

            data["has_cv"] = bool(data.get("cv_pdf_path") or data.get("cv_md_path"))
            data["has_letter"] = bool(data.get("letter_pdf_path") or data.get("letter_md_path"))
            return data

    def update_job_channel_status(
        self,
        job_id: int,
        telegram_notified: Optional[int] = None,
        ui_saved: Optional[int] = None,
    ) -> None:
        """Actualiza independientemente los estados de canal de una oferta."""
        updates = []
        params: List[Any] = []
        if telegram_notified is not None:
            updates.append("telegram_notified = ?")
            params.append(telegram_notified)
        if ui_saved is not None:
            updates.append("ui_saved = ?")
            params.append(ui_saved)

        if updates:
            updates.append("updated_at = datetime('now', 'localtime')")
            params.append(job_id)
            sql = f"UPDATE jobs SET {', '.join(updates)} WHERE id = ?"
            with self._get_connection() as conn:
                conn.execute(sql, params)

    def prune_old_system_logs(self, max_entries: int = 150, retention_hours: int = 24) -> int:
        """
        Elimina los logs antiguos conservando únicamente los registros recientes (últimas 24h).
        Garantiza que la consola web y los registros solo muestren eventos nuevos.
        """
        try:
            with self._get_connection() as conn:
                # 1. Eliminar logs con más de retention_hours de antigüedad
                cursor1 = conn.execute(
                    "DELETE FROM system_logs WHERE timestamp < datetime('now', '-' || ? || ' hours', 'localtime')",
                    (retention_hours,),
                )
                deleted_by_time = cursor1.rowcount

                # 2. Asegurar que nunca exceda max_entries manteniendo los IDs más recientes
                cursor2 = conn.execute(
                    """
                    DELETE FROM system_logs 
                    WHERE id NOT IN (
                        SELECT id FROM system_logs ORDER BY id DESC LIMIT ?
                    )
                    """,
                    (max_entries,),
                )
                deleted_by_limit = cursor2.rowcount
                return deleted_by_time + deleted_by_limit
        except Exception as e:
            logger.error("Error purgando logs antiguos: %s", e)
            return 0

    def clear_system_logs(self) -> int:
        """Elimina todos los logs del sistema para reiniciar la consola con registros limpios."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("DELETE FROM system_logs")
                return cursor.rowcount
        except Exception as e:
            logger.error("Error vaciando system_logs: %s", e)
            return 0

    def get_system_logs(
        self,
        limit: int = 150,
        level: Optional[str] = None,
        source: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Recupera los logs del sistema estructurados para la consola web de administración."""
        self.prune_old_system_logs(max_entries=limit, retention_hours=24)
        where = ["1=1"]
        params: List[Any] = []
        if level:
            where.append("level = ?")
            params.append(level.upper())
        if source:
            where.append("source = ?")
            params.append(source.lower())

        sql = f"""
            SELECT id, timestamp, level, source, message, details
            FROM system_logs
            WHERE {' AND '.join(where)}
            ORDER BY id DESC
            LIMIT ?
        """
        with self._get_connection() as conn:
            cursor = conn.execute(sql, params + [limit])
            return [dict(r) for r in cursor.fetchall()]

    def get_recent_pipeline_runs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Recupera el historial de ejecuciones del pipeline."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM pipeline_runs ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            return [dict(r) for r in cursor.fetchall()]

    def delete_selected_documents(self, job_ids: List[int]) -> int:
        """
        Elimina de disco y de base de datos los archivos PDF/MD generados para las ofertas indicadas.
        No elimina la oferta ni la evaluación de la base de datos.
        """
        if not job_ids:
            return 0

        placeholders = ",".join("?" for _ in job_ids)
        deleted_count = 0

        with self._get_connection() as conn:
            cursor = conn.execute(
                f"SELECT id, cv_pdf_path, cv_md_path, letter_pdf_path, letter_md_path FROM generated_documents WHERE job_id IN ({placeholders})",
                job_ids,
            )
            rows = cursor.fetchall()
            for r in rows:
                for path_key in ("cv_pdf_path", "cv_md_path", "letter_pdf_path", "letter_md_path"):
                    file_path = r[path_key]
                    if file_path and os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                        except Exception as e:
                            logger.warning("No se pudo eliminar archivo físico %s: %s", file_path, e)
                deleted_count += 1

            conn.execute(
                f"DELETE FROM generated_documents WHERE job_id IN ({placeholders})",
                job_ids,
            )
        return deleted_count

    def clear_applications_history(self) -> Dict[str, int]:
        """
        Elimina el historial completo de ofertas, evaluaciones y documentos generados.
        Conserva la estructura de tablas y los registros de system_logs para auditoría.
        """
        with self._get_connection() as conn:
            jobs_count = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
            evals_count = conn.execute("SELECT COUNT(*) FROM evaluations").fetchone()[0]
            docs_count = conn.execute("SELECT COUNT(*) FROM generated_documents").fetchone()[0]

            conn.execute("DELETE FROM generated_documents;")
            conn.execute("DELETE FROM evaluations;")
            conn.execute("DELETE FROM jobs;")
            conn.execute("DELETE FROM pipeline_runs;")

        return {
            "jobs_deleted": jobs_count,
            "evaluations_deleted": evals_count,
            "documents_deleted": docs_count,
        }

    def delete_jobs_by_cv_filename(self, cv_filename: str) -> int:
        """Elimina todas las ofertas asociadas a un archivo CV específico."""
        if not cv_filename or cv_filename in ("none", "Ninguno"):
            return 0
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM jobs WHERE cv_filename = ?", (str(cv_filename).strip(),))
            deleted = cursor.rowcount
            conn.commit()
            logger.info("Eliminadas %d ofertas asociadas al CV '%s'", deleted, cv_filename)
            return deleted

    def get_filter_facets(self, cv_filename: Optional[str] = None) -> Dict[str, Any]:
        """
        Escanea las ofertas reales registradas en SQLite procedentes de los portales
        y extrae dinámicamente las facetas y opciones de filtro disponibles con sus conteos reales.
        Se adapta a las ofertas visibles vinculadas al CV activo (no descartadas).
        """
        from .storage import read_active_cv_pointer
        target_cv = cv_filename
        if target_cv is None:
            target_cv = read_active_cv_pointer()

        with self._get_connection() as conn:
            has_evals = conn.execute("SELECT 1 FROM evaluations LIMIT 1").fetchone() is not None
            if has_evals:
                base_from = "jobs j LEFT JOIN evaluations e ON j.id = e.job_id"
                base_where = "j.ui_saved = 1 AND j.status != 'discarded' AND (e.fit_level IS NULL OR e.fit_level != 'DESCARTADO')"
            else:
                base_from = "jobs j"
                base_where = "j.ui_saved = 1 AND j.status != 'discarded'"

            if target_cv in ("none", "Ninguno", "") or not target_cv:
                base_where += " AND 1=0"
            else:
                escaped_cv = str(target_cv).strip().replace("'", "''")
                base_where += f" AND (j.cv_filename = '{escaped_cv}' OR j.cv_filename IS NULL)"

            constants = _load_shared_constants()
            portal_sources = constants.get("portal_sources", {})
            # 1. Portales / Fuentes encontradas en las ofertas visibles
            source_rows = conn.execute(
                f"SELECT j.source, COUNT(*) as c FROM {base_from} WHERE {base_where} GROUP BY j.source ORDER BY c DESC"
            ).fetchall()
            sources = [
                {
                    "id": r["source"],
                    "label": portal_sources.get(r["source"].lower(), {}).get("label") or r["source"].capitalize(),
                    "count": r["c"],
                }
                for r in source_rows
            ]

            # 2. Modalidades encontradas en las ofertas visibles
            remote_count = conn.execute(
                f"""SELECT COUNT(*) FROM {base_from} WHERE {base_where} AND (
                    j.is_remote = 1 OR LOWER(j.location) LIKE '%remot%' OR LOWER(j.title) LIKE '%remot%' 
                    OR LOWER(j.description) LIKE '%remot%' OR LOWER(j.description) LIKE '%teletrabaj%'
                )"""
            ).fetchone()[0]

            hybrid_count = conn.execute(
                f"""SELECT COUNT(*) FROM {base_from} WHERE {base_where} AND (
                    LOWER(j.location) LIKE '%hibrid%' OR LOWER(j.location) LIKE '%hybrid%' 
                    OR LOWER(j.title) LIKE '%hibrid%' OR LOWER(j.description) LIKE '%hibrid%' 
                    OR LOWER(j.description) LIKE '%hybrid%'
                )"""
            ).fetchone()[0]

            onsite_count = conn.execute(
                f"""SELECT COUNT(*) FROM {base_from} WHERE {base_where} AND j.is_remote = 0 AND NOT (
                    LOWER(j.location) LIKE '%remot%' OR LOWER(j.location) LIKE '%hibrid%' 
                    OR LOWER(j.location) LIKE '%hybrid%'
                )"""
            ).fetchone()[0]

            modalities = []
            if remote_count > 0:
                modalities.append({"id": "teletrabajo", "label": "Remote / Teletrabajo", "count": remote_count})
            if hybrid_count > 0:
                modalities.append({"id": "hibrido", "label": "Hybrid / Híbrido", "count": hybrid_count})
            if onsite_count > 0:
                modalities.append({"id": "presencial", "label": "On-site / Presencial", "count": onsite_count})

            # 3. Categorías y competencias profesionales extraídas directamente de las ofertas visibles
            skill_counter: collections.Counter = collections.Counter()
            offer_rows = conn.execute(
                f"SELECT j.title, j.description, {'e.matched_skills' if has_evals else 'NULL as matched_skills'} FROM {base_from} WHERE {base_where}"
            ).fetchall()

            geo_stop_words = {"spain", "españa", "espana", "remoto", "remote", "hibrido", "hybrid", "madrid", "barcelona", "sevilla", "valencia", "málaga", "malaga", "bilbao", "zaragoza", "coruña"}
            for off in offer_rows:
                raw_skills = off["matched_skills"]
                if raw_skills:
                    try:
                        skills = json.loads(raw_skills) if isinstance(raw_skills, str) else raw_skills
                        if isinstance(skills, list):
                            for s in skills:
                                clean_s = str(s).strip()
                                if clean_s and len(clean_s) > 1 and clean_s.lower() not in geo_stop_words:
                                    skill_counter[clean_s] += 1
                    except Exception:
                        pass

            categories = [
                {"id": name.lower(), "label": name, "count": count}
                for name, count in skill_counter.most_common(25)
            ]

            # 4. Formaciones mínimas extraídas directamente de las ofertas registradas
            edu_rows = conn.execute(
                f"SELECT j.education_level, COUNT(*) as c FROM {base_from} WHERE {base_where} AND j.education_level IS NOT NULL AND j.education_level != '' GROUP BY j.education_level ORDER BY c DESC"
            ).fetchall()
            educations = [{"id": r["education_level"].lower(), "label": r["education_level"], "count": r["c"]} for r in edu_rows]

            # 5. Jornada laboral extraída directamente de las ofertas registradas
            sch_rows = conn.execute(
                f"SELECT j.schedule, COUNT(*) as c FROM {base_from} WHERE {base_where} AND j.schedule IS NOT NULL AND j.schedule != '' GROUP BY j.schedule ORDER BY c DESC"
            ).fetchall()
            schedules = [{"id": r["schedule"].lower(), "label": r["schedule"], "count": r["c"]} for r in sch_rows]

            # 6. Tipos de contrato extraídos directamente de las ofertas registradas
            ct_rows = conn.execute(
                f"SELECT j.contract_type, COUNT(*) as c FROM {base_from} WHERE {base_where} AND j.contract_type IS NOT NULL AND j.contract_type != '' GROUP BY j.contract_type ORDER BY c DESC"
            ).fetchall()
            contract_types = [{"id": r["contract_type"].lower(), "label": r["contract_type"], "count": r["c"]} for r in ct_rows]

            # 7. Estadísticas salariales reales de ofertas visibles
            sal_row = conn.execute(
                f"SELECT MIN(j.salary_min) as min_sal, MAX(j.salary_max) as max_sal, j.salary_currency FROM {base_from} WHERE {base_where} AND j.salary_min > 0"
            ).fetchone()
            salary_stats = {
                "min": sal_row["min_sal"] if sal_row and sal_row["min_sal"] else 15000,
                "max": sal_row["max_sal"] if sal_row and sal_row["max_sal"] else 80000,
                "currency": sal_row["salary_currency"] if sal_row and sal_row["salary_currency"] else "EUR",
            }

            # 8. Top ubicaciones reales encontradas en ofertas visibles
            loc_rows = conn.execute(
                f"SELECT j.location, COUNT(*) as c FROM {base_from} WHERE {base_where} AND j.location IS NOT NULL AND j.location != '' GROUP BY j.location ORDER BY c DESC LIMIT 15"
            ).fetchall()
            top_locations = [{"name": r["location"], "count": r["c"]} for r in loc_rows]

            total_visible = conn.execute(f"SELECT COUNT(*) FROM {base_from} WHERE {base_where}").fetchone()[0]

            return {
                "sources": sources,
                "modalities": modalities,
                "categories": categories,
                "educations": educations,
                "schedules": schedules,
                "contract_types": contract_types,
                "salary_stats": salary_stats,
                "top_locations": top_locations,
                "total_jobs": total_visible,
            }
