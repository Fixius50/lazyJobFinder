"""Rutas para lectura y actualización segura de configuraciones del sistema y canales."""

import logging
import os
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
import yaml

from ..deps import get_db, get_runner

logger = logging.getLogger("lazyJobFinder.api.settings")
router = APIRouter(prefix="/settings", tags=["Configuración y Canales"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SETTINGS_FILE = os.path.join(BASE_DIR, "config", "settings.yaml")


class NotificationChannelsUpdate(BaseModel):
    guardar_en_interfaz: bool = Field(..., description="Conservar y consultar en la interfaz web local")
    enviar_telegram: bool = Field(..., description="Enviar notificaciones por bot de Telegram")
    telegram_user_id: Optional[str] = Field(None, description="ID numérico de usuario de Telegram autorizado")
    telegram_adjuntar_docs: Optional[bool] = Field(None, description="Adjuntar PDFs por Telegram")
    umbral_minimo_puntuacion: Optional[int] = Field(None, ge=0, le=100, description="Umbral mínimo de afinidad")


class SearchConfigUpdate(BaseModel):
    terminos: List[str]
    ubicaciones: List[str]
    filtros_exclusion: List[str]
    antiguedad_horas: int = Field(48, ge=1, le=168)
    limite_por_fuente: int = Field(15, ge=1, le=50)


def _read_settings() -> Dict[str, Any]:
    if not os.path.exists(SETTINGS_FILE):
        return {}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.error("Error leyendo settings.yaml: %s", e)
        raise HTTPException(status_code=500, detail="No se pudo leer el archivo de configuración.")


def _save_settings(data: Dict[str, Any]) -> None:
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)
        # Notificar al runner para recargar configuraciones en caliente
        runner = get_runner()
        runner.reload_settings()
    except Exception as e:
        logger.error("Error guardando settings.yaml: %s", e)
        raise HTTPException(status_code=500, detail="No se pudo guardar la configuración.")


@router.get("")
def get_settings() -> Dict[str, Any]:
    """
    Devuelve la configuración del sistema para la interfaz web.
    Garantía de privacidad: JAMÁS expone tokens ni variables de entorno del archivo .env.
    """
    data = _read_settings()

    # Informar estado de configuración de Telegram sin filtrar el token
    telegram_bot_token_present = bool(os.getenv("TELEGRAM_BOT_TOKEN"))
    cfg_user_id = data.get("notificaciones", {}).get("telegram", {}).get("allowed_user_id", "")
    env_user_id = os.getenv("TELEGRAM_ALLOWED_USER_ID", "")
    current_user_id = str(cfg_user_id or env_user_id or "").strip()
    if current_user_id == "0":
        current_user_id = ""

    return {
        "busqueda": data.get("busqueda", {}),
        "fuentes": data.get("fuentes", {}),
        "evaluacion": data.get("evaluacion", {}),
        "notificaciones": data.get("notificaciones", {}),
        "horario": data.get("horario", {}),
        "secrets_status": {
            "telegram_configured": telegram_bot_token_present and bool(current_user_id),
            "telegram_token_present": telegram_bot_token_present,
            "telegram_user_id": current_user_id,
            "infojobs_configured": bool(os.getenv("INFOJOBS_CLIENT_ID")),
        },
        "privacy_notice": {
            "telegram_transmission_note": (
                "ADVERTENCIA DE PRIVACIDAD: La activación de 'enviar_telegram' y el envío de documentos PDF "
                "transmite los archivos del CV y carta de presentación a la infraestructura externa de los servidores "
                "de Telegram. Si desactivas 'enviar_telegram' y mantienes 'guardar_en_interfaz', la totalidad del proceso "
                "y los archivos permanecen 100% locales en tu equipo sin transmisión externa alguna."
            ),
        },
    }


@router.put("/channels")
def update_notification_channels(req: NotificationChannelsUpdate) -> Dict[str, Any]:
    """
    Actualiza de forma atómica y persistente las preferencias independientes de canal:
    - guardar_en_interfaz
    - enviar_telegram
    - telegram_user_id (ID de usuario Telegram)
    - adjuntar documentos
    - umbral mínimo de puntuación
    """
    data = _read_settings()
    if "notificaciones" not in data:
        data["notificaciones"] = {}

    data["notificaciones"]["guardar_en_interfaz"] = req.guardar_en_interfaz
    data["notificaciones"]["enviar_telegram"] = req.enviar_telegram

    if req.telegram_user_id is not None:
        if "telegram" not in data["notificaciones"]:
            data["notificaciones"]["telegram"] = {}
        clean_user_id = req.telegram_user_id.strip()
        data["notificaciones"]["telegram"]["allowed_user_id"] = clean_user_id
        if clean_user_id:
            os.environ["TELEGRAM_ALLOWED_USER_ID"] = clean_user_id

    if req.telegram_adjuntar_docs is not None:
        if "telegram" not in data["notificaciones"]:
            data["notificaciones"]["telegram"] = {}
        data["notificaciones"]["telegram"]["adjuntar_documentos"] = req.telegram_adjuntar_docs

    if req.umbral_minimo_puntuacion is not None:
        if "evaluacion" not in data:
            data["evaluacion"] = {}
        data["evaluacion"]["umbral_minimo_puntuacion"] = req.umbral_minimo_puntuacion

    _save_settings(data)

    db = get_db()
    db.log_event(
        "INFO",
        "settings",
        f"Preferencias de canales actualizadas: interfaz={req.guardar_en_interfaz}, telegram={req.enviar_telegram}",
    )

    return {
        "success": True,
        "message": "Preferencias de notificación guardadas y aplicadas correctamente.",
        "notificaciones": data["notificaciones"],
        "evaluacion": data.get("evaluacion", {}),
    }


@router.put("/search")
def update_search_config(req: SearchConfigUpdate) -> Dict[str, Any]:
    """Actualiza términos de búsqueda, ubicaciones y palabras clave de exclusión."""
    data = _read_settings()
    if "busqueda" not in data:
        data["busqueda"] = {}

    data["busqueda"]["terminos"] = [t.strip() for t in req.terminos if t.strip()]
    data["busqueda"]["ubicaciones"] = [u.strip() for u in req.ubicaciones if u.strip()]
    data["busqueda"]["filtros_exclusion"] = [e.strip() for e in req.filtros_exclusion if e.strip()]
    data["busqueda"]["antiguedad_horas"] = req.antiguedad_horas
    data["busqueda"]["limite_por_fuente"] = req.limite_por_fuente

    _save_settings(data)

    db = get_db()
    db.log_event("INFO", "settings", "Parámetros de búsqueda actualizados.")

    return {
        "success": True,
        "message": "Configuración de búsqueda actualizada.",
        "busqueda": data["busqueda"],
    }
