"""Módulo unificado de persistencia local en SQLite con modo WAL/TRUNCATE, sqlite-utils y modelos Pydantic V2."""

import collections
import contextlib
from datetime import datetime, timedelta
import hashlib
import json
import logging
import os
import re
import sqlite3
import threading
import time
from typing import Any, Dict, Generator, List, Optional, Tuple, Union
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

try:
    from rapidfuzz import fuzz
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False

try:
    import sqlite_utils
except ImportError:
    sqlite_utils = None

from .models import (
    AppStateModel,
    CVCacheModel,
    EvaluationModel,
    GeneratedDocumentModel,
    JobModel,
    PipelineRunModel,
    SystemLogModel,
)
from .storage import DB_PATH as DEFAULT_DB_PATH

logger = logging.getLogger("lazyJobFinder.database")


def canonicalize_url(raw_url: str) -> str:
    """Elimina parámetros de rastreo y normaliza la URL para deduplicación exacta."""
    if not raw_url:
        return ""
    try:
        parsed = urlparse(raw_url.strip())
        tracking_params = {
            "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
            "ref", "refid", "trackingid", "trk", "position", "pagenum",
            "currentjobid", "fbclid", "gclid", "originalsubdomain",
        }
        query_dict = parse_qs(parsed.query)
        cleaned_query = {k: v for k, v in query_dict.items() if k.lower() not in tracking_params}
        new_query = urlencode(cleaned_query, doseq=True)
        return urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            parsed.params,
            new_query,
            "",
        ))
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
    """Calcula una huella semántica normalizada para detectar la misma oferta entre portales."""
    comp_clean = re.sub(r"\b(s\.?l\.?|s\.?a\.?|inc\.?|llc|spain|españa)\b", "", company.lower())
    comp_clean = re.sub(r"[^\w\s]", "", comp_clean).strip()
    comp_clean = re.sub(r"\s+", " ", comp_clean)

    title_clean = re.sub(r"[^\w\s]", "", title.lower()).strip()
    title_clean = re.sub(r"\s+", " ", title_clean)

    loc_clean = re.sub(r"[^\w\s]", "", location.lower()).strip()
    loc_clean = re.sub(r"\s+", " ", loc_clean)

    composite = f"{comp_clean}|{title_clean}|{loc_clean}"
    return hashlib.sha256(composite.encode("utf-8")).hexdigest()


def compute_description_hash(description: str) -> str:
    """Calcula el hash del cuerpo de la descripción para detectar actualizaciones relevantes."""
    clean_desc = re.sub(r"\s+", " ", description.strip().lower())
    return hashlib.sha256(clean_desc.encode("utf-8")).hexdigest()


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


class Database:
    """Gestor unificado de base de datos SQLite con conexión segura, PRAGMAs de alto rendimiento y sqlite-utils."""

    _initialized_paths: set = set()
    _init_lock = threading.Lock()

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.getenv("DB_PATH", DEFAULT_DB_PATH)
        if self.db_path not in Database._initialized_paths:
            with Database._init_lock:
                if self.db_path not in Database._initialized_paths:
                    self.init_db()
                    Database._initialized_paths.add(self.db_path)

    @contextlib.contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Obtiene una conexión sqlite3 segura con PRAGMAs de alto rendimiento y reintentos ante bloqueos."""
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        conn = None
        for attempt in range(5):
            try:
                conn = sqlite3.connect(self.db_path, timeout=30.0)
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA busy_timeout = 30000;")
                conn.execute("PRAGMA foreign_keys = ON;")
                conn.execute("PRAGMA cache_size = -64000;")  # ~64 MB de caché en RAM
                conn.execute("PRAGMA temp_store = MEMORY;")   # Tablas temporales en RAM
                break
            except sqlite3.OperationalError as e:
                if attempt == 4:
                    logger.error("Error al conectar con SQLite tras 5 intentos: %s", e)
                    raise
                time.sleep(0.15 * (attempt + 1))
        try:
            with conn:
                yield conn
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    def get_utils_db(self):
        """Devuelve una instancia de sqlite_utils.Database para operaciones rápidas, FTS5 y alter=True."""
        if sqlite_utils is None:
            return None
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        db = sqlite_utils.Database(self.db_path)
        try:
            db.conn.execute("PRAGMA busy_timeout = 30000;")
            db.conn.execute("PRAGMA foreign_keys = ON;")
            db.conn.execute("PRAGMA cache_size = -64000;")
            db.conn.execute("PRAGMA temp_store = MEMORY;")
        except Exception:
            pass
        return db

    def init_db(self) -> None:
        """Crea o actualiza las tablas e índices necesarios con modo TRUNCATE seguro para Docker."""
        with self._get_connection() as conn:
            try:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                conn.execute("PRAGMA journal_mode=TRUNCATE;")
                conn.execute("PRAGMA synchronous=NORMAL;")
            except sqlite3.OperationalError as j_err:
                logger.warning("Ajustando journal_mode en SQLite: %s", j_err)
                conn.execute("PRAGMA journal_mode=DELETE;")

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
                    ui_saved INTEGER DEFAULT 1,
                    contract_type TEXT,
                    schedule TEXT,
                    education_level TEXT,
                    cv_filename TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_jobs_url_hash ON jobs(url_hash);
                CREATE INDEX IF NOT EXISTS idx_jobs_fingerprint ON jobs(content_fingerprint);
                CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
                CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at);
                CREATE INDEX IF NOT EXISTS idx_jobs_duplicate_of ON jobs(duplicate_of_id);
                CREATE INDEX IF NOT EXISTS idx_jobs_notification_channels ON jobs(telegram_notified, ui_saved);
                CREATE INDEX IF NOT EXISTS idx_jobs_contract_schedule ON jobs(contract_type, schedule);
                CREATE INDEX IF NOT EXISTS idx_jobs_cv_filename ON jobs(cv_filename);

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
                    trigger_type TEXT NOT NULL,
                    status TEXT NOT NULL,
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

                CREATE TABLE IF NOT EXISTS app_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT DEFAULT (datetime('now', 'localtime'))
                );

                CREATE TABLE IF NOT EXISTS cv_cache (
                    filename TEXT PRIMARY KEY,
                    file_hash TEXT NOT NULL,
                    file_mtime REAL,
                    file_size INTEGER,
                    extracted_text TEXT NOT NULL,
                    profile_json TEXT,
                    created_at TEXT DEFAULT (datetime('now', 'localtime')),
                    updated_at TEXT DEFAULT (datetime('now', 'localtime'))
                );

                CREATE INDEX IF NOT EXISTS idx_cv_cache_hash ON cv_cache(file_hash);
                """
            )

            # Auto-migración idempotente de columnas para esquemas previos
            try:
                cols_info = conn.execute("PRAGMA table_info(jobs);").fetchall()
                existing_cols = {col["name"] for col in cols_info}
                for col, col_def in [
                    ("contract_type", "TEXT"),
                    ("schedule", "TEXT"),
                    ("education_level", "TEXT"),
                    ("similarity_score", "REAL"),
                    ("alternate_sources", "TEXT DEFAULT '[]'"),
                    ("telegram_notified", "INTEGER DEFAULT 0"),
                    ("ui_saved", "INTEGER DEFAULT 1"),
                    ("cv_filename", "TEXT"),
                ]:
                    if col not in existing_cols:
                        conn.execute(f"ALTER TABLE jobs ADD COLUMN {col} {col_def};")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_contract_schedule ON jobs(contract_type, schedule);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_cv_filename ON jobs(cv_filename);")
            except Exception as e:
                logger.debug("Comprobación de columnas en jobs completada: %s", e)

        # Habilitación FTS5 sin fallos
        try:
            udb = self.get_utils_db()
            if udb and "jobs" in udb.table_names() and "jobs_fts" not in udb.table_names():
                udb["jobs"].enable_fts(["title", "description", "company"], create_triggers=True, tokenize="porter")
        except Exception:
            pass

    # =========================================================================
    # ESTADO PERSISTENTE (APP STATE)
    # =========================================================================
    def get_app_state(self, key: str, default: Any = None) -> Any:
        """Recupera un valor de configuración persistente desde SQLite."""
        udb = self.get_utils_db()
        if udb:
            try:
                row = udb["app_state"].get(key)
                val = row["value"]
                try:
                    return json.loads(val)
                except Exception:
                    return val
            except Exception:
                return default

        with self._get_connection() as conn:
            cursor = conn.execute("SELECT value FROM app_state WHERE key = ?", (key,))
            row = cursor.fetchone()
            if not row:
                return default
            try:
                return json.loads(row["value"])
            except Exception:
                return row["value"]

    def set_app_state(self, key: str, value: Any) -> None:
        """Guarda o actualiza un valor de estado persistente de manera atómica."""
        val_str = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
        udb = self.get_utils_db()
        if udb:
            try:
                udb["app_state"].upsert(
                    {"key": key, "value": val_str, "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
                    pk="key",
                )
                return
            except Exception as e:
                logger.debug("Fallback de set_app_state a SQL: %s", e)

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO app_state (key, value, updated_at)
                VALUES (?, ?, datetime('now', 'localtime'))
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = datetime('now', 'localtime')
                """,
                (key, val_str),
            )

    def delete_app_state(self, key: str) -> None:
        """Elimina una clave de estado persistente."""
        udb = self.get_utils_db()
        if udb:
            try:
                udb["app_state"].delete(key)
                return
            except Exception:
                pass
        with self._get_connection() as conn:
            conn.execute("DELETE FROM app_state WHERE key = ?", (key,))

    # =========================================================================
    # CACHÉ DE EXTRACCIÓN Y PERFIL DE CV
    # =========================================================================
    def get_cv_cache(
        self,
        filename: str,
        file_mtime: Optional[float] = None,
        file_size: Optional[int] = None,
        file_hash: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Recupera la extracción y perfil en caché para un CV."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM cv_cache WHERE filename = ?", (filename,))
            row = cursor.fetchone()
            if not row:
                return None
            if file_mtime is not None and row["file_mtime"] is not None:
                if abs(float(row["file_mtime"]) - float(file_mtime)) > 1.0:
                    return None
            if file_size is not None and row["file_size"] is not None:
                if int(row["file_size"]) != int(file_size):
                    return None
            if file_hash is not None and row["file_hash"] != file_hash:
                return None

            profile = None
            if row["profile_json"]:
                try:
                    profile = json.loads(row["profile_json"])
                except Exception:
                    pass
            return {
                "filename": row["filename"],
                "file_hash": row["file_hash"],
                "file_mtime": row["file_mtime"],
                "file_size": row["file_size"],
                "extracted_text": row["extracted_text"],
                "profile": profile,
            }

    def save_cv_cache(
        self,
        filename: str,
        file_hash: str,
        file_mtime: float,
        file_size: int,
        extracted_text: str,
        profile_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Almacena o actualiza la extracción y perfil de un CV en SQLite."""
        prof_json = json.dumps(profile_data, ensure_ascii=False) if profile_data else None
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO cv_cache (filename, file_hash, file_mtime, file_size, extracted_text, profile_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
                ON CONFLICT(filename) DO UPDATE SET
                    file_hash = excluded.file_hash,
                    file_mtime = excluded.file_mtime,
                    file_size = excluded.file_size,
                    extracted_text = excluded.extracted_text,
                    profile_json = excluded.profile_json,
                    updated_at = datetime('now', 'localtime')
                """,
                (filename, file_hash, file_mtime, file_size, extracted_text, prof_json),
            )

    def delete_cv_cache(self, filename: str) -> None:
        """Elimina la caché de extracción de un CV específico."""
        udb = self.get_utils_db()
        if udb:
            try:
                udb["cv_cache"].delete(filename)
                return
            except Exception:
                pass
        with self._get_connection() as conn:
            conn.execute("DELETE FROM cv_cache WHERE filename = ?", (filename,))

    def clean_startup_artifacts(self, upload_dir: Optional[str] = None) -> Dict[str, int]:
        """Limpia estados y archivos residuales de arranques o caídas previas."""
        interrupted_runs = self.recover_interrupted_runs()
        reset_jobs = self.reset_evaluating_jobs()

        cleaned_files = 0
        target_dir = upload_dir or os.getenv("UPLOAD_DIR", os.path.join(os.path.dirname(self.db_path), "uploaded_cvs"))
        if os.path.exists(target_dir):
            try:
                for fname in os.listdir(target_dir):
                    if fname.startswith(".extracted_") or (fname.startswith(".") and fname.endswith(".txt")):
                        full_p = os.path.join(target_dir, fname)
                        try:
                            if os.path.isfile(full_p):
                                os.remove(full_p)
                                cleaned_files += 1
                        except OSError:
                            pass
            except Exception as e:
                logger.debug("Error limpiando archivos temporales en %s: %s", target_dir, e)

        stale_cv_entries = 0
        if os.path.exists(target_dir):
            try:
                valid_files = set(os.listdir(target_dir))
                with self._get_connection() as conn:
                    cur = conn.execute("SELECT filename FROM cv_cache")
                    cached_names = [r["filename"] for r in cur.fetchall()]
                    for cn in cached_names:
                        if cn not in valid_files:
                            conn.execute("DELETE FROM cv_cache WHERE filename = ?", (cn,))
                            stale_cv_entries += 1
            except Exception:
                pass

        if interrupted_runs > 0 or reset_jobs > 0 or cleaned_files > 0 or stale_cv_entries > 0:
            logger.info(
                "Limpieza de arranque completada: %d ejecuciones recuperadas, %d ofertas reajustadas, %d archivos residuales eliminados, %d cachés de CV obsoletas depuradas.",
                interrupted_runs, reset_jobs, cleaned_files, stale_cv_entries,
            )

        return {
            "interrupted_runs": interrupted_runs,
            "reset_jobs": reset_jobs,
            "cleaned_files": cleaned_files,
            "stale_cv_entries": stale_cv_entries,
        }

    # =========================================================================
    # GESTIÓN DE OFERTAS (JOBS)
    # =========================================================================
    def job_exists(self, url_hash: str) -> bool:
        """Verifica si ya existe una oferta con este hash de URL."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT 1 FROM jobs WHERE url_hash = ? LIMIT 1", (url_hash,))
            return cursor.fetchone() is not None

    def find_cross_portal_duplicate(self, content_fingerprint: str) -> Optional[int]:
        """Busca el ID canónico de una oferta con idéntica huella de contenido."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, duplicate_of_id FROM jobs
                WHERE content_fingerprint = ?
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (content_fingerprint,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return row["duplicate_of_id"] if row["duplicate_of_id"] else row["id"]

    def find_fuzzy_duplicate(
        self,
        title: str,
        company: str,
        location: str,
        description: str = "",
        threshold: float = 0.88,
    ) -> Optional[Tuple[int, float]]:
        """Deduplicación difusa contra ofertas de los últimos 30 días."""
        if not RAPIDFUZZ_AVAILABLE:
            return None

        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, title, company, location, duplicate_of_id
                FROM jobs
                WHERE duplicate_of_id IS NULL
                  AND created_at >= datetime('now', '-30 days', 'localtime')
                ORDER BY created_at DESC
                LIMIT 500
                """
            )
            candidates = cursor.fetchall()

        best_id: Optional[int] = None
        best_score = 0.0

        for cand in candidates:
            t_score = fuzz.token_sort_ratio(title.lower(), cand["title"].lower()) / 100.0
            c_score = fuzz.token_set_ratio(company.lower(), cand["company"].lower()) / 100.0

            if t_score >= 0.85 and c_score >= 0.80:
                combined = (t_score * 0.6) + (c_score * 0.4)
                if combined > best_score:
                    best_score = combined
                    best_id = cand["duplicate_of_id"] if cand["duplicate_of_id"] else cand["id"]

        if best_id and best_score >= threshold:
            return best_id, best_score
        return None

    def save_job(self, job_data: Dict[str, Any]) -> Tuple[Optional[int], str]:
        """Inserta o actualiza una oferta aplicando deduplicación y auto-migración."""
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
            cursor = conn.execute(
                "SELECT id, description_hash, alternate_sources, cv_filename FROM jobs WHERE url_hash = ?",
                (url_hash,),
            )
            existing = cursor.fetchone()
            if existing:
                existing_id = existing["id"]
                old_desc_hash = existing["description_hash"]
                if cv_filename and not existing["cv_filename"]:
                    conn.execute("UPDATE jobs SET cv_filename = ? WHERE id = ?", (cv_filename, existing_id))
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

            cross_dup_id = self.find_cross_portal_duplicate(content_fingerprint)
            fuzzy_sim = 1.0 if cross_dup_id else None

            if not cross_dup_id:
                fuzzy_match = self.find_fuzzy_duplicate(
                    title=title, company=company, location=location, description=description
                )
                if fuzzy_match:
                    cross_dup_id, fuzzy_sim = fuzzy_match

            if cross_dup_id:
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
                            contract_type, schedule, education_level, cv_filename
                        ),
                    )
                    dup_row_id = cursor.lastrowid

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
                        url_hash, content_fingerprint, desc_hash, canonical_url,
                        title, company, location, 1 if job_data.get("is_remote") else 0,
                        source, description, job_data.get("salary_min"),
                        job_data.get("salary_max"), job_data.get("salary_currency", "EUR"),
                        job_data.get("date_posted", ""), job_data.get("status", "discovered"),
                        contract_type, schedule, education_level, cv_filename,
                    ),
                )
                return cursor.lastrowid, "inserted"
            except sqlite3.IntegrityError:
                return None, "already_exists"

    def update_job_status(self, job_id: int, status: str) -> None:
        """Actualiza el estado del ciclo de vida de la oferta."""
        udb = self.get_utils_db()
        if udb:
            try:
                udb["jobs"].update(
                    job_id,
                    {"status": status, "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
                    alter=True,
                )
                return
            except Exception as e:
                logger.debug("Fallback update_job_status a SQL: %s", e)

        with self._get_connection() as conn:
            conn.execute(
                "UPDATE jobs SET status = ?, updated_at = datetime('now', 'localtime') WHERE id = ?",
                (status, job_id),
            )

    def update_job_channel_status(
        self,
        job_id: int,
        telegram_notified: Optional[int] = None,
        ui_saved: Optional[int] = None,
    ) -> None:
        """Actualiza el estado de notificación en Telegram o guardado visual en la UI."""
        updates = []
        params = []
        if telegram_notified is not None:
            updates.append("telegram_notified = ?")
            params.append(1 if telegram_notified else 0)
        if ui_saved is not None:
            updates.append("ui_saved = ?")
            params.append(1 if ui_saved else 0)

        if not updates:
            return

        updates.append("updated_at = datetime('now', 'localtime')")
        params.append(job_id)

        with self._get_connection() as conn:
            conn.execute(f"UPDATE jobs SET {', '.join(updates)} WHERE id = ?", params)

    def get_job_detail(self, job_id: int) -> Optional[Dict[str, Any]]:
        """Recupera la ficha integral de una vacante, incluyendo análisis de IA y documentos generados."""
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
        time_range: Optional[str] = "all",
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> Dict[str, Any]:
        """Recupera ofertas paginadas con soporte de filtros multicriterio."""
        page = max(1, page)
        page_size = min(max(5, page_size), 500)
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
            pointer = read_active_cv_pointer()
            if isinstance(pointer, dict):
                target_cv = pointer.get("selected_filename", "")
            else:
                target_cv = str(pointer or "")

        clean_target_cv = str(target_cv or "").strip()
        if clean_target_cv and clean_target_cv.lower() not in ("none", "ninguno", "all", "todas", "*", ""):
            where_clauses.append("j.cv_filename = ?")
            params.append(clean_target_cv)
        else:
            where_clauses.append("1=0")

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

        if min_score is not None:
            where_clauses.append("e.score >= ?")
            params.append(min_score)

        active_modalities = [m.lower().strip() for m in (modalities or []) if m and m.lower().strip() not in ("sin_especificar", "todas")]
        if not active_modalities and modality and modality.lower().strip() not in ("sin_especificar", "todas", ""):
            active_modalities = [modality.lower().strip()]

        if active_modalities:
            mod_subclauses = []
            for m in active_modalities:
                if m in ("remoto", "teletrabajo"):
                    mod_subclauses.append("((j.is_remote = 1 OR LOWER(j.location) LIKE '%remot%' OR LOWER(j.location) LIKE '%teletrabaj%' OR LOWER(j.title) LIKE '%remot%' OR LOWER(j.title) LIKE '%teletrabaj%') AND LOWER(j.location) NOT LIKE '%hibrid%' AND LOWER(j.location) NOT LIKE '%hybrid%' AND LOWER(j.title) NOT LIKE '%hibrid%' AND LOWER(j.title) NOT LIKE '%hybrid%')")
                elif m == "hibrido":
                    mod_subclauses.append("(LOWER(j.location) LIKE '%hibrid%' OR LOWER(j.location) LIKE '%hybrid%' OR LOWER(j.location) LIKE '%híbrid%' OR LOWER(j.title) LIKE '%hibrid%' OR LOWER(j.title) LIKE '%hybrid%' OR LOWER(j.title) LIKE '%híbrid%' OR LOWER(j.description) LIKE '%hibrid%' OR LOWER(j.description) LIKE '%hybrid%' OR LOWER(j.description) LIKE '%híbrid%')")
                elif m == "presencial":
                    mod_subclauses.append("(j.is_remote = 0 AND LOWER(j.location) NOT LIKE '%remot%' AND LOWER(j.location) NOT LIKE '%teletrabaj%' AND LOWER(j.title) NOT LIKE '%remot%' AND LOWER(j.title) NOT LIKE '%teletrabaj%' AND LOWER(j.location) NOT LIKE '%hibrid%' AND LOWER(j.location) NOT LIKE '%hybrid%' AND LOWER(j.location) NOT LIKE '%híbrid%' AND LOWER(j.title) NOT LIKE '%hibrid%' AND LOWER(j.title) NOT LIKE '%hybrid%' AND LOWER(j.title) NOT LIKE '%híbrid%' AND LOWER(j.description) NOT LIKE '%hibrid%' AND LOWER(j.description) NOT LIKE '%hybrid%')")
            if mod_subclauses:
                where_clauses.append(f"({' OR '.join(mod_subclauses)})")
        elif is_remote is not None:
            where_clauses.append("j.is_remote = ?")
            params.append(1 if is_remote else 0)

        active_cats = [c.lower().strip() for c in (categories or []) if c and c.lower().strip() not in ("sin_especificar", "todas")]
        if active_cats:
            cat_clauses = []
            for cat in active_cats:
                cat_clauses.append("(LOWER(j.title) LIKE ? OR LOWER(j.description) LIKE ? OR (e.matched_skills IS NOT NULL AND LOWER(e.matched_skills) LIKE ?))")
                params.extend([f"%{cat}%", f"%{cat}%", f"%{cat}%"])
            where_clauses.append(f"({' OR '.join(cat_clauses)})")

        active_edus = [e.lower().strip() for e in (educations or []) if e and e.lower().strip() not in ("sin_especificar", "todas")]
        if active_edus:
            edu_clauses = []
            for edu in active_edus:
                edu_clauses.append("(LOWER(j.education_level) LIKE ? OR LOWER(j.description) LIKE ?)")
                params.extend([f"%{edu}%", f"%{edu}%"])
            where_clauses.append(f"({' OR '.join(edu_clauses)})")

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

        if min_salary and min_salary > 0:
            where_clauses.append(
                "((CASE WHEN j.salary_max <= 100 THEN j.salary_max * 1800 WHEN j.salary_max < 6000 THEN j.salary_max * 12 ELSE j.salary_max END) >= ? "
                "OR (CASE WHEN j.salary_min <= 100 THEN j.salary_min * 1800 WHEN j.salary_min < 6000 THEN j.salary_min * 12 ELSE j.salary_min END) >= ?)"
            )
            params.extend([min_salary, min_salary])

        active_scheds = [s.lower().strip() for s in (schedules or []) if s and s.lower().strip() not in ("sin_especificar", "todas")]
        if active_scheds:
            sched_clauses = []
            for sc in active_scheds:
                sched_clauses.append("(LOWER(j.schedule) LIKE ? OR LOWER(j.description) LIKE ?)")
                params.extend([f"%{sc}%", f"%{sc}%"])
            where_clauses.append(f"({' OR '.join(sched_clauses)})")

        active_contracts = [c.lower().strip() for c in (contract_types or []) if c and c.lower().strip() not in ("sin_especificar", "todas")]
        if active_contracts:
            contract_clauses = []
            for ct in active_contracts:
                contract_clauses.append("(LOWER(j.contract_type) LIKE ? OR LOWER(j.description) LIKE ?)")
                params.extend([f"%{ct}%", f"%{ct}%"])
            where_clauses.append(f"({' OR '.join(contract_clauses)})")

        if location and location.strip() and not any(k in location.lower() for k in ("todos", "all", "cualquiera")):
            loc_val = location.strip()
            where_clauses.append("(LOWER(j.location) LIKE ? OR j.is_remote = 1 OR LOWER(j.location) LIKE '%remot%' OR LOWER(j.location) LIKE '%teletrabaj%')")
            params.append(f"%{loc_val.lower()}%")

        if time_range and str(time_range).strip().lower() not in ("all", "todas", "todos", "cualquiera", ""):
            tr = str(time_range).strip().lower()
            if tr in ("24h", "1d", "hoy", "today"):
                where_clauses.append("(j.created_at >= datetime('now', '-1 day', 'localtime') OR j.date_posted >= date('now', '-1 day', 'localtime'))")
            elif tr in ("7d", "week", "semana", "7_dias"):
                where_clauses.append("(j.created_at >= datetime('now', '-7 days', 'localtime') OR j.date_posted >= date('now', '-7 days', 'localtime'))")
            elif tr in ("30d", "month", "mes", "30_dias"):
                where_clauses.append("(j.created_at >= datetime('now', '-30 days', 'localtime') OR j.date_posted >= date('now', '-30 days', 'localtime'))")

        where_str = " AND ".join(where_clauses)

        with self._get_connection() as conn:
            count_sql = f"""
                SELECT COUNT(*) FROM jobs j
                LEFT JOIN evaluations e ON j.id = e.job_id
                WHERE {where_str}
            """
            total_items = conn.execute(count_sql, params).fetchone()[0]

            query_sql = f"""
                SELECT
                    j.id, j.title, j.company, j.location, j.is_remote, j.source,
                    j.canonical_url, j.salary_min, j.salary_max, j.salary_currency,
                    j.date_posted, j.created_at, j.updated_at, j.status,
                    j.duplicate_of_id, j.similarity_score, j.alternate_sources,
                    j.telegram_notified, j.ui_saved,
                    j.description, j.contract_type, j.schedule, j.education_level,
                    e.score, e.fit_level, e.should_apply, e.matched_skills,
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

    # =========================================================================
    # EVALUACIONES ATS Y DOCUMENTOS GENERADOS
    # =========================================================================
    def save_evaluation(self, eval_data: Dict[str, Any]) -> int:
        """Registra o actualiza la evaluación de afinidad de una oferta de manera atómica."""
        job_id = eval_data["job_id"]
        matched = json.dumps(eval_data.get("matched_skills", []), ensure_ascii=False)
        missing = json.dumps(eval_data.get("missing_skills", []), ensure_ascii=False)
        strengths = json.dumps(eval_data.get("strengths", []), ensure_ascii=False)
        gaps = json.dumps(eval_data.get("gaps", []), ensure_ascii=False)
        score = eval_data.get("score", 0)
        fit_level = eval_data.get("fit_level", "MODERADO")
        reasoning = eval_data.get("reasoning", "")
        should_apply = 1 if eval_data.get("should_apply") else 0

        with self._get_connection() as conn:
            job_exists = conn.execute("SELECT 1 FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if not job_exists:
                logger.warning("Oferta ID %s ya no existe en tabla jobs. Omitiendo guardado de evaluación.", job_id)
                return -1

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
                (job_id, score, fit_level, matched, missing, strengths, gaps, reasoning, should_apply),
            )
            return job_id

    def save_documents(self, doc_data: Dict[str, Any]) -> int:
        """Registra o actualiza las rutas de los archivos PDF y Markdown generados."""
        job_id = doc_data["job_id"]
        cv_pdf_path = doc_data.get("cv_pdf_path")
        cv_md_path = doc_data.get("cv_md_path")
        letter_pdf_path = doc_data.get("letter_pdf_path")
        letter_md_path = doc_data.get("letter_md_path")
        diff_summary = doc_data.get("diff_summary", "")

        with self._get_connection() as conn:
            job_exists = conn.execute("SELECT 1 FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if not job_exists:
                logger.warning("Oferta ID %s ya no existe en tabla jobs. Omitiendo guardado de documentos.", job_id)
                return -1

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
                (job_id, cv_pdf_path, cv_md_path, letter_pdf_path, letter_md_path, diff_summary),
            )
            return cursor.lastrowid

    def get_unevaluated_jobs(self, limit: int = 500, cv_filename: Optional[str] = None) -> List[Dict[str, Any]]:
        """Recupera ofertas pendientes de evaluación."""
        with self._get_connection() as conn:
            if cv_filename and cv_filename not in ("none", "Ninguno", ""):
                query = """
                    SELECT j.* FROM jobs j
                    LEFT JOIN evaluations e ON j.id = e.job_id
                    WHERE e.id IS NULL
                      AND j.status NOT IN ('evaluated', 'discarded', 'rejected')
                      AND (j.cv_filename = ? OR j.cv_filename IS NULL OR j.cv_filename = '')
                    ORDER BY j.id ASC
                    LIMIT ?
                """
                cursor = conn.execute(query, (cv_filename, limit))
            else:
                query = """
                    SELECT j.* FROM jobs j
                    LEFT JOIN evaluations e ON j.id = e.job_id
                    WHERE e.id IS NULL AND j.status NOT IN ('evaluated', 'discarded', 'rejected')
                    ORDER BY j.id ASC
                    LIMIT ?
                """
                cursor = conn.execute(query, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_all_jobs_for_scoring(self, limit: int = 200, cv_filename: Optional[str] = None) -> List[Dict[str, Any]]:
        """Recupera todas las ofertas activas registradas para contrastar afinidad."""
        with self._get_connection() as conn:
            if cv_filename and cv_filename not in ("none", "Ninguno", ""):
                query = """
                    SELECT id, title, company, location, is_remote, description, source, created_at
                    FROM jobs
                    WHERE ui_saved = 1 AND cv_filename = ?
                    ORDER BY id DESC
                    LIMIT ?
                """
                cursor = conn.execute(query, (cv_filename, limit))
            else:
                query = """
                    SELECT id, title, company, location, is_remote, description, source, created_at
                    FROM jobs
                    WHERE ui_saved = 1
                    ORDER BY id DESC
                    LIMIT ?
                """
                cursor = conn.execute(query, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_evaluated_jobs_needing_docs(
        self, min_score: int = 50, cv_filename: Optional[str] = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Recupera ofertas evaluadas con score >= min_score que aún no tienen documentos generados."""
        with self._get_connection() as conn:
            where = ["e.score >= ?", "d.id IS NULL", "j.ui_saved = 1"]
            params: List[Any] = [min_score]
            if cv_filename and cv_filename not in ("none", "Ninguno", ""):
                where.append("j.cv_filename = ?")
                params.append(cv_filename)

            sql = f"""
                SELECT
                    j.id, j.title, j.company, j.location, j.is_remote, j.description, j.source,
                    e.score, e.fit_level, e.should_apply, e.matched_skills, e.missing_skills,
                    e.strengths, e.gaps, e.reasoning
                FROM jobs j
                JOIN evaluations e ON j.id = e.job_id
                LEFT JOIN generated_documents d ON j.id = d.job_id
                WHERE {' AND '.join(where)}
                ORDER BY e.score DESC, j.id DESC
                LIMIT ?
            """
            cursor = conn.execute(sql, params + [limit])
            items = []
            for row in cursor.fetchall():
                items.append(_decode_row_json_fields(dict(row)))
            return items

    def reset_evaluating_jobs(self) -> int:
        """Reinicia a 'discovered' cualquier vacante bloqueada en 'evaluating'."""
        with self._get_connection() as conn:
            cursor = conn.execute("UPDATE jobs SET status = 'discovered' WHERE status = 'evaluating'")
            return cursor.rowcount

    # =========================================================================
    # EJECUCIONES DEL PIPELINE
    # =========================================================================
    def start_pipeline_run(self, trigger_type: str) -> int:
        """Registra el inicio de una ejecución en pipeline_runs."""
        udb = self.get_utils_db()
        if udb:
            try:
                pk = udb["pipeline_runs"].insert({"trigger_type": trigger_type, "status": "running"}).last_pk
                return int(pk) if pk is not None else 0
            except Exception:
                pass

        with self._get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO pipeline_runs (trigger_type, status) VALUES (?, 'running')",
                (trigger_type,),
            )
            return int(cursor.lastrowid or 0)

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
        data = {
            "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": status,
            "total_found": total_found,
            "new_jobs": new_jobs,
            "relevant_jobs": relevant_jobs,
            "error_message": error_message,
        }
        udb = self.get_utils_db()
        if udb:
            try:
                udb["pipeline_runs"].update(run_id, data)
                return
            except Exception:
                pass

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
        """Comprueba si ya se completó con éxito una ejecución en el día actual."""
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
        for attempt in range(4):
            try:
                with self._get_connection() as conn:
                    cursor = conn.execute(
                        "SELECT * FROM pipeline_runs WHERE status = 'completed' ORDER BY id DESC LIMIT 1"
                    )
                    row = cursor.fetchone()
                    return dict(row) if row else None
            except sqlite3.OperationalError as e:
                if attempt == 3:
                    logger.warning("Fallo recuperando get_last_completed_run tras 4 intentos: %s", e)
                    return None
                time.sleep(0.1 * (attempt + 1))
        return None

    def get_recent_pipeline_runs(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Recupera el historial cronológico reciente de ejecuciones."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM pipeline_runs ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def recover_interrupted_runs(self) -> int:
        """Detecta ejecuciones en estado 'running' tras caídas y las marca como 'interrupted'."""
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
        """Registra como 'skipped' los días en los que el sistema estuvo apagado."""
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

    # =========================================================================
    # ESTADÍSTICAS Y FACETAS DE FILTROS
    # =========================================================================
    def get_statistics(self) -> Dict[str, Any]:
        """Recupera estadísticas globales para el diagnóstico por Telegram e interfaz."""
        default_stats = {
            "total_jobs": 0,
            "jobs_today": 0,
            "total_evaluated": 0,
            "high_matches": 0,
            "last_run": "Sin ejecuciones previas",
        }
        for attempt in range(4):
            try:
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
            except sqlite3.OperationalError as e:
                if attempt == 3:
                    logger.warning("Fallo recuperando get_statistics tras 4 intentos: %s", e)
                    return default_stats
                time.sleep(0.1 * (attempt + 1))
        return default_stats

    def get_top_recent_jobs(
        self, limit: int = 10, min_score: int = 65, cv_filename: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Devuelve las mejores ofertas recientes que superan el umbral."""
        with self._get_connection() as conn:
            if cv_filename and cv_filename not in ("none", "Ninguno", ""):
                query = """
                    SELECT j.id, j.title, j.company, j.location, j.canonical_url, j.source, j.created_at,
                           e.score, e.fit_level, e.reasoning, e.matched_skills, e.missing_skills,
                           d.cv_pdf_path, d.letter_pdf_path
                    FROM jobs j
                    INNER JOIN evaluations e ON j.id = e.job_id
                    LEFT JOIN generated_documents d ON j.id = d.job_id
                    WHERE e.score >= ? AND j.cv_filename = ?
                    ORDER BY e.score DESC, j.created_at DESC
                    LIMIT ?
                """
                cursor = conn.execute(query, (min_score, cv_filename, limit))
            else:
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

    def get_filter_facets(self, cv_filename: Optional[str] = None) -> Dict[str, Any]:
        """Calcula los contadores dinámicos para los filtros laterales en base al CV activo."""
        target_cv = cv_filename
        if target_cv is None:
            from .storage import read_active_cv_pointer
            pointer = read_active_cv_pointer()
            if isinstance(pointer, dict):
                target_cv = pointer.get("selected_filename", "")
            else:
                target_cv = str(pointer or "")

        with self._get_connection() as conn:
            base_from = "jobs j LEFT JOIN evaluations e ON j.id = e.job_id"
            base_where = "j.ui_saved = 1"

            clean_target_cv = str(target_cv or "").strip()
            if clean_target_cv and clean_target_cv.lower() not in ("none", "ninguno", "all", "todas", "*", ""):
                safe_cv = clean_target_cv.replace("'", "''")
                base_where += f" AND j.cv_filename = '{safe_cv}'"
            else:
                base_where += " AND 1=0"

            # 1. Portales de origen
            source_rows = conn.execute(
                f"SELECT j.source, COUNT(*) as c FROM {base_from} WHERE {base_where} GROUP BY j.source ORDER BY c DESC"
            ).fetchall()
            sources = [{"id": r["source"], "label": r["source"].capitalize(), "count": r["c"]} for r in source_rows]

            # 2. Modalidades de trabajo
            modalities = []
            remote_count = conn.execute(
                f"SELECT COUNT(*) FROM {base_from} WHERE {base_where} AND ((j.is_remote = 1 OR LOWER(j.location) LIKE '%remot%' OR LOWER(j.location) LIKE '%teletrabaj%' OR LOWER(j.title) LIKE '%remot%' OR LOWER(j.title) LIKE '%teletrabaj%') AND LOWER(j.location) NOT LIKE '%hibrid%' AND LOWER(j.location) NOT LIKE '%hybrid%' AND LOWER(j.title) NOT LIKE '%hibrid%' AND LOWER(j.title) NOT LIKE '%hybrid%')"
            ).fetchone()[0]
            if remote_count > 0:
                modalities.append({"id": "remoto", "label": "Remoto", "count": remote_count})

            hybrid_count = conn.execute(
                f"SELECT COUNT(*) FROM {base_from} WHERE {base_where} AND (LOWER(j.location) LIKE '%hibrid%' OR LOWER(j.location) LIKE '%hybrid%' OR LOWER(j.location) LIKE '%híbrid%' OR LOWER(j.title) LIKE '%hibrid%' OR LOWER(j.title) LIKE '%hybrid%' OR LOWER(j.title) LIKE '%híbrid%' OR LOWER(j.description) LIKE '%hibrid%' OR LOWER(j.description) LIKE '%hybrid%' OR LOWER(j.description) LIKE '%híbrid%')"
            ).fetchone()[0]
            if hybrid_count > 0:
                modalities.append({"id": "hibrido", "label": "Híbrido", "count": hybrid_count})

            onsite_count = conn.execute(
                f"SELECT COUNT(*) FROM {base_from} WHERE {base_where} AND (j.is_remote = 0 AND LOWER(j.location) NOT LIKE '%remot%' AND LOWER(j.location) NOT LIKE '%teletrabaj%' AND LOWER(j.title) NOT LIKE '%remot%' AND LOWER(j.title) NOT LIKE '%teletrabaj%' AND LOWER(j.location) NOT LIKE '%hibrid%' AND LOWER(j.location) NOT LIKE '%hybrid%' AND LOWER(j.location) NOT LIKE '%híbrid%' AND LOWER(j.title) NOT LIKE '%hibrid%' AND LOWER(j.title) NOT LIKE '%hybrid%' AND LOWER(j.title) NOT LIKE '%híbrid%' AND LOWER(j.description) NOT LIKE '%hibrid%' AND LOWER(j.description) NOT LIKE '%hybrid%')"
            ).fetchone()[0]
            if onsite_count > 0:
                modalities.append({"id": "presencial", "label": "Presencial", "count": onsite_count})

            # 3. Niveles de ajuste IA
            fit_rows = conn.execute(
                f"SELECT e.fit_level, COUNT(*) as c FROM {base_from} WHERE {base_where} AND e.fit_level IS NOT NULL GROUP BY e.fit_level ORDER BY c DESC"
            ).fetchall()
            fit_levels = [{"id": r["fit_level"], "label": r["fit_level"].capitalize(), "count": r["c"]} for r in fit_rows]

            # 4. Habilidades y categorías agregadas
            skill_counter: collections.Counter = collections.Counter()
            missing_counter: collections.Counter = collections.Counter()
            strength_counter: collections.Counter = collections.Counter()
            gap_counter: collections.Counter = collections.Counter()

            eval_rows = conn.execute(
                f"SELECT e.matched_skills, e.missing_skills, e.strengths, e.gaps FROM {base_from} WHERE {base_where} AND (e.matched_skills IS NOT NULL OR e.strengths IS NOT NULL)"
            ).fetchall()
            for er in eval_rows:
                for field_key, counter in [
                    ("matched_skills", skill_counter),
                    ("missing_skills", missing_counter),
                    ("strengths", strength_counter),
                    ("gaps", gap_counter),
                ]:
                    raw = er[field_key]
                    if raw:
                        try:
                            parsed = json.loads(raw) if isinstance(raw, str) else raw
                            if isinstance(parsed, list):
                                for item in parsed:
                                    c_item = str(item).strip()
                                    if c_item:
                                        counter[c_item] += 1
                        except Exception:
                            pass

            categories = [
                {"id": name, "label": name, "count": count}
                for name, count in skill_counter.most_common(12)
            ]

            # 5. Formación mínima
            raw_edu_rows = conn.execute(
                f"SELECT j.education_level, COUNT(*) as c FROM {base_from} WHERE {base_where} AND j.education_level IS NOT NULL AND TRIM(j.education_level) != '' GROUP BY j.education_level ORDER BY c DESC"
            ).fetchall()
            educations = [{"id": r["education_level"], "label": r["education_level"], "count": r["c"]} for r in raw_edu_rows]

            # 6. Jornada laboral
            sched_rows = conn.execute(
                f"SELECT j.schedule, COUNT(*) as c FROM {base_from} WHERE {base_where} AND j.schedule IS NOT NULL AND TRIM(j.schedule) != '' GROUP BY j.schedule ORDER BY c DESC"
            ).fetchall()
            schedules = [{"id": r["schedule"], "label": r["schedule"], "count": r["c"]} for r in sched_rows]

            # 7. Tipo de contrato
            contract_rows = conn.execute(
                f"SELECT j.contract_type, COUNT(*) as c FROM {base_from} WHERE {base_where} AND j.contract_type IS NOT NULL AND TRIM(j.contract_type) != '' GROUP BY j.contract_type ORDER BY c DESC"
            ).fetchall()
            contract_types = [{"id": r["contract_type"], "label": r["contract_type"], "count": r["c"]} for r in contract_rows]

            # 8. Rangos salariales
            salary_row = conn.execute(
                f"""
                SELECT
                    MIN(CASE WHEN j.salary_min <= 100 THEN j.salary_min * 1800 WHEN j.salary_min < 6000 THEN j.salary_min * 12 ELSE j.salary_min END) as min_val,
                    MAX(CASE WHEN j.salary_max <= 100 THEN j.salary_max * 1800 WHEN j.salary_max < 6000 THEN j.salary_max * 12 ELSE j.salary_max END) as max_val
                FROM {base_from}
                WHERE {base_where} AND (j.salary_min > 0 OR j.salary_max > 0)
                """
            ).fetchone()
            salary_min = float(salary_row["min_val"] or 15000.0)
            salary_max = float(salary_row["max_val"] or 100000.0)

            # 9. Puntuaciones mínimas y máximas
            score_row = conn.execute(
                f"SELECT MIN(e.score) as min_score, MAX(e.score) as max_score FROM {base_from} WHERE {base_where} AND e.score IS NOT NULL"
            ).fetchone()
            min_score = int(score_row["min_score"] or 0)
            max_score = int(score_row["max_score"] or 100)

            total_jobs = conn.execute(f"SELECT COUNT(*) FROM {base_from} WHERE {base_where}").fetchone()[0]

            return {
                "total_jobs": total_jobs,
                "sources": sources,
                "modalities": modalities,
                "fit_levels": fit_levels,
                "categories": categories,
                "educations": educations,
                "schedules": schedules,
                "contract_types": contract_types,
                "salary_range": {"min": salary_min, "max": salary_max},
                "score_range": {"min": min_score, "max": max_score},
                "skills": [{"id": name, "label": name, "count": count} for name, count in skill_counter.most_common(20)],
                "missing_skills": [{"id": name, "label": name, "count": count} for name, count in missing_counter.most_common(20)],
                "strengths": [{"id": name, "label": name, "count": count} for name, count in strength_counter.most_common(20)],
                "gaps": [{"id": name, "label": name, "count": count} for name, count in gap_counter.most_common(20)],
            }

    # =========================================================================
    # LOGS DEL SISTEMA Y AUDITORÍA
    # =========================================================================
    def log_event(self, level: str, source: str, message: str, details: Optional[str] = None) -> None:
        """Registra un evento o error del sistema de forma persistente."""
        try:
            udb = self.get_utils_db()
            if udb:
                udb["system_logs"].insert({
                    "level": level.upper(),
                    "source": source,
                    "message": message,
                    "details": details or "",
                })
                return

            with self._get_connection() as conn:
                conn.execute(
                    "INSERT INTO system_logs (level, source, message, details) VALUES (?, ?, ?, ?)",
                    (level.upper(), source, message, details or ""),
                )
        except Exception as e:
            logger.error("Fallo al escribir en system_logs: %s", e)

    def get_system_logs(
        self,
        limit: int = 100,
        level: Optional[str] = None,
        source: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Recupera los logs más recientes con filtros opcionales."""
        where = ["1=1"]
        params: List[Any] = []
        if level:
            where.append("level = ?")
            params.append(level.upper())
        if source:
            where.append("source = ?")
            params.append(source)

        query = f"""
            SELECT * FROM system_logs
            WHERE {' AND '.join(where)}
            ORDER BY id DESC
            LIMIT ?
        """
        params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def prune_old_system_logs(self, days_to_keep: int = 30) -> int:
        """Elimina logs con una antigüedad superior a days_to_keep días."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM system_logs WHERE timestamp < datetime('now', ? || ' days', 'localtime')",
                (f"-{days_to_keep}",),
            )
            return cursor.rowcount

    def clear_system_logs(self) -> int:
        """Vacía completamente el registro de eventos del sistema."""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM system_logs")
            return cursor.rowcount

    # =========================================================================
    # MANTENIMIENTO, DOCUMENTOS Y PURGAS
    # =========================================================================
    def delete_selected_documents(self, job_ids: List[int]) -> int:
        """Elimina de disco y de base de datos los archivos de las ofertas indicadas."""
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
        """Elimina el historial completo de ofertas, evaluaciones y documentos generados."""
        udb = self.get_utils_db()
        if udb:
            try:
                jobs_count = udb["jobs"].count
                evals_count = udb["evaluations"].count
                docs_count = udb["generated_documents"].count
                udb["generated_documents"].delete_where()
                udb["evaluations"].delete_where()
                udb["jobs"].delete_where()
                udb["pipeline_runs"].delete_where()
                return {
                    "jobs_deleted": jobs_count,
                    "evaluations_deleted": evals_count,
                    "documents_deleted": docs_count,
                }
            except Exception:
                pass

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
        cleaned = str(cv_filename).strip()
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM jobs WHERE cv_filename = ?", (cleaned,))
            deleted = int(cursor.rowcount)
            conn.commit()
            logger.info("Eliminadas %d ofertas asociadas al CV '%s'", deleted, cv_filename)
            return deleted
