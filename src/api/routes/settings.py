import copy
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
SECRETS_FILE = os.path.join(BASE_DIR, "data", "secrets.json")


def _read_persisted_secrets() -> Dict[str, str]:
    """Lee las credenciales privadas almacenadas en el volumen persistente /app/data/."""
    if not os.path.exists(SECRETS_FILE):
        return {}
    try:
        import json
        with open(SECRETS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("No se pudo leer data/secrets.json: %s", e)
        return {}


def _save_persisted_secret(key: str, value: str) -> None:
    """Guarda un secreto en data/secrets.json (persistente ante recreación de Docker)."""
    import json
    data = _read_persisted_secrets()
    data[key] = value
    os.makedirs(os.path.dirname(SECRETS_FILE), exist_ok=True)
    try:
        with open(SECRETS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error("No se pudo escribir en data/secrets.json: %s", e)


def _delete_persisted_secret(key: str) -> None:
    """Elimina un secreto de data/secrets.json."""
    import json
    data = _read_persisted_secrets()
    if key in data:
        data.pop(key, None)
        try:
            with open(SECRETS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error("No se pudo actualizar data/secrets.json al eliminar: %s", e)


def _get_secret(key: str, default: str = "") -> str:
    """Recupera un secreto con orden de precedencia: 1) data/secrets.json, 2) os.environ."""
    persisted = _read_persisted_secrets()
    if key in persisted and persisted[key]:
        return str(persisted[key]).strip()
    return str(os.getenv(key, default)).strip()


def _update_env_file(key: str, value: str) -> None:
    """Actualiza una variable en el archivo local .env sin tocar otros valores."""
    env_path = os.path.join(BASE_DIR, ".env")
    lines = []
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception as e:
            logger.warning("No se pudo leer .env para actualizar %s: %s", key, e)
            return

    new_lines = []
    found = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"{key}=") or stripped.startswith(f"#{key}="):
            new_lines.append(f"{key}={value}\n")
            found = True
        else:
            new_lines.append(line)

    if not found and value:
        new_lines.append(f"{key}={value}\n")

    try:
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
    except Exception as e:
        logger.warning("No se pudo escribir en .env: %s", e)



class NotificationChannelsUpdate(BaseModel):
    guardar_en_interfaz: Optional[bool] = Field(True, description="Conservar y consultar en la interfaz web local (obligatorio)")
    enviar_telegram: bool = Field(..., description="Enviar notificaciones por bot de Telegram")
    telegram_user_id: Optional[str] = Field(None, description="ID numérico de usuario de Telegram autorizado")
    telegram_adjuntar_docs: Optional[bool] = Field(True, description="Adjuntar PDFs por Telegram (obligatorio si Telegram activo)")
    umbral_minimo_puntuacion: Optional[int] = Field(None, ge=0, le=100, description="Umbral mínimo de afinidad")
    infojobs_client_id: Optional[str] = Field(None, description="Client ID de la API oficial de InfoJobs")
    infojobs_client_secret: Optional[str] = Field(None, description="Client Secret de la API oficial de InfoJobs")


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
    # NUNCA persistir client_secret en settings.yaml (archivo versionado en git)
    if "fuentes" in data and "infojobs_api" in data["fuentes"]:
        data["fuentes"]["infojobs_api"].pop("client_secret", None)

    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)
        # Notificar al runner para recargar configuraciones en caliente
        runner = get_runner()
        if runner:
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

    # Informar estado de configuración de Telegram e InfoJobs sin filtrar tokens secretos
    telegram_bot_token_present = bool(os.getenv("TELEGRAM_BOT_TOKEN"))
    cfg_user_id = data.get("notificaciones", {}).get("telegram", {}).get("allowed_user_id", "")
    current_user_id = _get_secret("TELEGRAM_ALLOWED_USER_ID", str(cfg_user_id or ""))
    if current_user_id == "0":
        current_user_id = ""

    cfg_ij_id = data.get("fuentes", {}).get("infojobs_api", {}).get("client_id", "")
    current_ij_id = _get_secret("INFOJOBS_CLIENT_ID", str(cfg_ij_id or ""))

    cfg_ij_secret = data.get("fuentes", {}).get("infojobs_api", {}).get("client_secret", "")
    current_ij_secret = _get_secret("INFOJOBS_CLIENT_SECRET", str(cfg_ij_secret or ""))

    # Sanitizar fuentes para que NUNCA exponga client_secret
    fuentes_sanitized = copy.deepcopy(data.get("fuentes", {}))
    if "infojobs_api" in fuentes_sanitized:
        fuentes_sanitized["infojobs_api"].pop("client_secret", None)

    return {
        "busqueda": data.get("busqueda", {}),
        "fuentes": fuentes_sanitized,
        "evaluacion": data.get("evaluacion", {}),
        "notificaciones": data.get("notificaciones", {}),
        "horario": data.get("horario", {}),
        "secrets_status": {
            "telegram_configured": telegram_bot_token_present and bool(current_user_id),
            "telegram_token_present": telegram_bot_token_present,
            "telegram_user_id": current_user_id,
            "infojobs_configured": bool(current_ij_id and current_ij_secret),
            "infojobs_client_id": current_ij_id,
            "infojobs_secret_present": bool(current_ij_secret),
        },
        "privacy_notice": {
            "telegram_transmission_note": (
                "ADVERTENCIA DE PRIVACIDAD: La activación de 'enviar_telegram' transmite los archivos "
                "del CV y carta de presentación a la infraestructura externa de los servidores de Telegram."
            ),
        },
    }


@router.put("/channels")
def update_notification_channels(req: NotificationChannelsUpdate) -> Dict[str, Any]:
    """
    Actualiza de forma atómica y persistente las preferencias de canal y claves API:
    - guardar_en_interfaz: siempre activo (soberano)
    - enviar_telegram: activable/desactivable
    - telegram_user_id: ID de usuario Telegram
    - adjuntar documentos: configurable (True por defecto si Telegram activo)
    - umbral mínimo de puntuación
    - credenciales InfoJobs (Client ID y Client Secret persistidos en /app/data/secrets.json)
    """
    data = _read_settings()
    if "notificaciones" not in data:
        data["notificaciones"] = {}

    # Guardar en interfaz es obligatorio por política del sistema
    data["notificaciones"]["guardar_en_interfaz"] = True
    data["notificaciones"]["enviar_telegram"] = req.enviar_telegram

    if req.telegram_user_id is not None:
        if "telegram" not in data["notificaciones"]:
            data["notificaciones"]["telegram"] = {}
        clean_user_id = req.telegram_user_id.strip()
        if clean_user_id:
            if not clean_user_id.isdigit():
                raise HTTPException(
                    status_code=400,
                    detail="El ID de usuario de Telegram debe ser puramente numérico (ej: 123456789).",
                )
            data["notificaciones"]["telegram"]["allowed_user_id"] = clean_user_id
            os.environ["TELEGRAM_ALLOWED_USER_ID"] = clean_user_id
            _save_persisted_secret("TELEGRAM_ALLOWED_USER_ID", clean_user_id)
            _update_env_file("TELEGRAM_ALLOWED_USER_ID", clean_user_id)
        else:
            # Borrado explícito
            data["notificaciones"]["telegram"]["allowed_user_id"] = ""
            os.environ.pop("TELEGRAM_ALLOWED_USER_ID", None)
            _delete_persisted_secret("TELEGRAM_ALLOWED_USER_ID")
            _update_env_file("TELEGRAM_ALLOWED_USER_ID", "")

    # Adjuntar documentos configurable (por defecto activo)
    if "telegram" not in data["notificaciones"]:
        data["notificaciones"]["telegram"] = {}
    data["notificaciones"]["telegram"]["adjuntar_documentos"] = (
        req.telegram_adjuntar_docs if req.telegram_adjuntar_docs is not None else True
    )

    if req.umbral_minimo_puntuacion is not None:
        if "evaluacion" not in data:
            data["evaluacion"] = {}
        data["evaluacion"]["umbral_minimo_puntuacion"] = req.umbral_minimo_puntuacion

    # Guardar credenciales de InfoJobs API de forma persistente en /app/data/secrets.json
    if req.infojobs_client_id is not None or req.infojobs_client_secret is not None:
        if "fuentes" not in data:
            data["fuentes"] = {}
        if "infojobs_api" not in data["fuentes"]:
            data["fuentes"]["infojobs_api"] = {}

        if req.infojobs_client_id is not None:
            clean_ij_id = req.infojobs_client_id.strip()
            data["fuentes"]["infojobs_api"]["client_id"] = clean_ij_id
            os.environ["INFOJOBS_CLIENT_ID"] = clean_ij_id
            if clean_ij_id:
                _save_persisted_secret("INFOJOBS_CLIENT_ID", clean_ij_id)
            else:
                _delete_persisted_secret("INFOJOBS_CLIENT_ID")
            _update_env_file("INFOJOBS_CLIENT_ID", clean_ij_id)

        if req.infojobs_client_secret is not None:
            clean_ij_sec = req.infojobs_client_secret.strip()
            if clean_ij_sec:
                os.environ["INFOJOBS_CLIENT_SECRET"] = clean_ij_sec
                _save_persisted_secret("INFOJOBS_CLIENT_SECRET", clean_ij_sec)
                _update_env_file("INFOJOBS_CLIENT_SECRET", clean_ij_sec)
            else:
                os.environ.pop("INFOJOBS_CLIENT_SECRET", None)
                _delete_persisted_secret("INFOJOBS_CLIENT_SECRET")
                _update_env_file("INFOJOBS_CLIENT_SECRET", "")
            data["fuentes"]["infojobs_api"].pop("client_secret", None)

    _save_settings(data)

    db = get_db()
    db.log_event(
        "INFO",
        "settings",
        f"Preferencias de canales actualizadas: interfaz=True, telegram={req.enviar_telegram}",
    )

    return {
        "success": True,
        "message": "Preferencias de notificación y claves API guardadas correctamente.",
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
