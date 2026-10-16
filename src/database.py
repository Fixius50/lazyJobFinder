"""Módulo de persistencia local en SQLite con modo WAL y deduplicación avanzada para lazyJobFinder."""

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

DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "lazyjobfinder.db",
)


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

        with self._get_connection() as conn:
            # 1. Comprobar si ya existe por URL exacta
            cursor = conn.execute(
                "SELECT id, description_hash, alternate_sources FROM jobs WHERE url_hash = ?",
                (url_hash,),
            )
            existing = cursor.fetchone()
            if existing:
                existing_id = existing["id"]
                old_desc_hash = existing["description_hash"]
                # Si cambió la descripción, actualizar registro y registrar timestamp
                if old_desc_hash and old_desc_hash != desc_hash:
                    conn.execute(
                        """
                        UPDATE jobs SET 
                            description = ?,
                            description_hash = ?,
                            updated_at = datetime('now', 'localtime')
                        WHERE id = ?
                        """,
                        (description, desc_hash, existing_id),
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
                            duplicate_of_id, similarity_score
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'duplicate', ?, ?)
                        """,
                        (
                            url_hash, content_fingerprint, desc_hash, canonical_url,
                            title, company, location, 1 if job_data.get("is_remote") else 0,
                            source, description, job_data.get("salary_min"),
                            job_data.get("salary_max"), job_data.get("salary_currency", "EUR"),
                            job_data.get("date_posted", ""), cross_dup_id, fuzzy_sim
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
                        salary_min, salary_max, salary_currency, date_posted, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        location: Optional[str] = None,
        source: Optional[str] = None,
        status: Optional[str] = None,
        min_score: Optional[int] = None,
        is_remote: Optional[bool] = None,
        modality: Optional[str] = None,
        only_ui_saved: bool = True,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> Dict[str, Any]:
        """
        Recupera ofertas paginadas con soporte de filtros multicriterio,
        ordenación segura y datos consolidados de evaluación y documentos.
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

        if only_ui_saved:
            where_clauses.append("j.ui_saved = 1")

        if search:
            search_param = f"%{search.strip().lower()}%"
            where_clauses.append("(LOWER(j.title) LIKE ? OR LOWER(j.company) LIKE ? OR LOWER(j.location) LIKE ?)")
            params.extend([search_param, search_param, search_param])

        if location:
            where_clauses.append("LOWER(j.location) LIKE ?")
            params.append(f"%{location.strip().lower()}%")

        if source:
            where_clauses.append("j.source = ?")
            params.append(source)

        if status:
            where_clauses.append("j.status = ?")
            params.append(status)

        if min_score is not None:
            where_clauses.append("e.score >= ?")
            params.append(min_score)

        if modality:
            mod = modality.strip().lower()
            if mod in ("remoto", "teletrabajo"):
                where_clauses.append("(j.is_remote = 1 OR LOWER(j.location) LIKE '%remoto%' OR LOWER(j.location) LIKE '%teletrabajo%' OR LOWER(j.title) LIKE '%remoto%' OR LOWER(j.title) LIKE '%teletrabajo%')")
            elif mod == "hibrido":
                where_clauses.append("(LOWER(j.location) LIKE '%hibrid%' OR LOWER(j.location) LIKE '%híbrid%' OR LOWER(j.title) LIKE '%hibrid%' OR LOWER(j.title) LIKE '%híbrid%' OR LOWER(j.description) LIKE '%híbrido%' OR LOWER(j.description) LIKE '%hibrido%')")
            elif mod == "presencial":
                where_clauses.append("(j.is_remote = 0 AND LOWER(j.location) NOT LIKE '%remoto%' AND LOWER(j.location) NOT LIKE '%teletrabajo%' AND LOWER(j.title) NOT LIKE '%remoto%' AND LOWER(j.title) NOT LIKE '%teletrabajo%' AND LOWER(j.location) NOT LIKE '%hibrid%' AND LOWER(j.location) NOT LIKE '%híbrid%')")
        elif is_remote is not None:
            where_clauses.append("j.is_remote = ?")
            params.append(1 if is_remote else 0)

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
                row_dict = dict(row)
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

            data = dict(row)
            # Decodificar JSON de habilidades y listas
            for field in ("matched_skills", "missing_skills", "strengths", "gaps", "alternate_sources"):
                if data.get(field):
                    try:
                        data[field] = json.loads(data[field])
                    except Exception:
                        pass
                else:
                    data[field] = []

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

    def get_system_logs(
        self,
        limit: int = 150,
        level: Optional[str] = None,
        source: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Recupera los logs del sistema estructurados para la consola web de administración."""
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
