"""Modelos Pydantic V2 canónicos para lazyJobFinder (Fuente Única de Verdad).

Al agregar o modificar un campo en estos modelos:
1. La API FastAPI lo valida y documenta automáticamente.
2. sqlite-utils (con alter=True) actualiza el esquema de SQLite automáticamente.
3. Las conversiones entre tipos nativos de Python (listas, dicts, fechas) y SQLite se gestionan de forma centralizada.
"""

from datetime import datetime
import json
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator


class JobModel(BaseModel):
    """Modelo representativo de una oferta de empleo."""

    id: Optional[int] = None
    url_hash: str
    content_fingerprint: str
    description_hash: Optional[str] = None
    canonical_url: str
    title: str
    company: str
    location: Optional[str] = "España"
    is_remote: int = 0
    source: str = "unknown"
    description: Optional[str] = ""
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: Optional[str] = "EUR"
    date_posted: Optional[str] = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    status: str = "discovered"
    duplicate_of_id: Optional[int] = None
    similarity_score: Optional[float] = None
    alternate_sources: List[Dict[str, Any]] = Field(default_factory=list)
    telegram_notified: int = 0
    ui_saved: int = 1
    contract_type: Optional[str] = None
    schedule: Optional[str] = None
    education_level: Optional[str] = None
    cv_filename: Optional[str] = None

    @field_validator("alternate_sources", mode="before")
    @classmethod
    def parse_alternate_sources(cls, v: Any) -> List[Dict[str, Any]]:
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, list) else []
            except Exception:
                return []
        if isinstance(v, list):
            return v
        return []

    def to_db_dict(self) -> Dict[str, Any]:
        """Convierte el modelo a un diccionario serializado para SQLite."""
        data = self.model_dump(exclude_none=False)
        data["alternate_sources"] = json.dumps(data.get("alternate_sources") or [], ensure_ascii=False)
        return data

    @classmethod
    def from_db_row(cls, row: Any) -> "JobModel":
        """Instancia el modelo a partir de un sqlite3.Row o diccionario de base de datos."""
        return cls.model_validate(dict(row))


class EvaluationModel(BaseModel):
    """Modelo de evaluación de afinidad ATS y análisis generado por IA local."""

    id: Optional[int] = None
    job_id: int
    score: int = Field(default=0, ge=0, le=100)
    fit_level: str = "MODERADO"
    matched_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    gaps: List[str] = Field(default_factory=list)
    reasoning: str = ""
    should_apply: int = 0
    created_at: Optional[str] = None

    @field_validator("matched_skills", "missing_skills", "strengths", "gaps", mode="before")
    @classmethod
    def parse_string_list(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, list) else []
            except Exception:
                return []
        if isinstance(v, list):
            return [str(x) for x in v]
        return []

    def to_db_dict(self) -> Dict[str, Any]:
        """Convierte el modelo a un diccionario serializado para SQLite."""
        data = self.model_dump(exclude_none=False)
        for key in ["matched_skills", "missing_skills", "strengths", "gaps"]:
            data[key] = json.dumps(data.get(key) or [], ensure_ascii=False)
        return data

    @classmethod
    def from_db_row(cls, row: Any) -> "EvaluationModel":
        return cls.model_validate(dict(row))


class GeneratedDocumentModel(BaseModel):
    """Modelo de rutas a documentos adaptados (CV y Carta de Presentación)."""

    id: Optional[int] = None
    job_id: int
    cv_pdf_path: Optional[str] = None
    cv_md_path: Optional[str] = None
    letter_pdf_path: Optional[str] = None
    letter_md_path: Optional[str] = None
    diff_summary: Optional[str] = ""
    created_at: Optional[str] = None

    def to_db_dict(self) -> Dict[str, Any]:
        return self.model_dump(exclude_none=False)

    @classmethod
    def from_db_row(cls, row: Any) -> "GeneratedDocumentModel":
        return cls.model_validate(dict(row))


class PipelineRunModel(BaseModel):
    """Registro de ejecución del ciclo de búsqueda y scoring."""

    id: Optional[int] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    trigger_type: str  # 'scheduled', 'manual', 'catch_up'
    status: str        # 'running', 'completed', 'failed'
    total_found: int = 0
    new_jobs: int = 0
    relevant_jobs: int = 0
    error_message: Optional[str] = None

    def to_db_dict(self) -> Dict[str, Any]:
        return self.model_dump(exclude_none=False)

    @classmethod
    def from_db_row(cls, row: Any) -> "PipelineRunModel":
        return cls.model_validate(dict(row))


class SystemLogModel(BaseModel):
    """Registro de eventos y trazabilidad del sistema."""

    id: Optional[int] = None
    timestamp: Optional[str] = None
    level: str
    source: str
    message: str
    details: Optional[str] = None

    def to_db_dict(self) -> Dict[str, Any]:
        return self.model_dump(exclude_none=False)

    @classmethod
    def from_db_row(cls, row: Any) -> "SystemLogModel":
        return cls.model_validate(dict(row))


class AppStateModel(BaseModel):
    """Estado y configuración persistente clave-valor."""

    key: str
    value: Any
    updated_at: Optional[str] = None

    def to_db_dict(self) -> Dict[str, Any]:
        val = self.value
        val_str = json.dumps(val, ensure_ascii=False) if not isinstance(val, str) else val
        return {
            "key": self.key,
            "value": val_str,
            "updated_at": self.updated_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    @classmethod
    def from_db_row(cls, row: Any) -> "AppStateModel":
        d = dict(row)
        raw_val = d.get("value")
        if isinstance(raw_val, str):
            try:
                d["value"] = json.loads(raw_val)
            except Exception:
                pass
        return cls.model_validate(d)


class CVCacheModel(BaseModel):
    """Caché de análisis y extracción de texto de currículums."""

    filename: str
    file_hash: str
    file_mtime: Optional[float] = None
    file_size: Optional[int] = None
    extracted_text: str = ""
    profile_json: Optional[Union[Dict[str, Any], str]] = None
    created_at: Optional[str] = None

    @field_validator("profile_json", mode="before")
    @classmethod
    def parse_profile_json(cls, v: Any) -> Optional[Union[Dict[str, Any], str]]:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return v
        return v

    def to_db_dict(self) -> Dict[str, Any]:
        data = self.model_dump(exclude_none=False)
        if isinstance(data.get("profile_json"), dict):
            data["profile_json"] = json.dumps(data["profile_json"], ensure_ascii=False)
        return data

    @classmethod
    def from_db_row(cls, row: Any) -> "CVCacheModel":
        return cls.model_validate(dict(row))

