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

from ...storage import (
    CONFIG_DIR,
    DATA_DIR,
    PROJECT_ROOT as BASE_DIR,
    SECRETS_FILE,
    SETTINGS_FILE,
    delete_persisted_secret as _delete_persisted_secret,
    get_secret as _get_secret,
    read_persisted_secrets as _read_persisted_secrets,
    save_persisted_secret as _save_persisted_secret,
)


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
    telegram_bot_token: Optional[str] = Field(None, description="Token del Bot de Telegram (@BotFather)")
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
    from ...storage import get_persisted_settings
    return get_persisted_settings()


def _save_settings(data: Dict[str, Any]) -> None:
    from ...storage import save_persisted_settings
    if "fuentes" in data and "infojobs_api" in data["fuentes"]:
        data["fuentes"]["infojobs_api"].pop("client_secret", None)

    try:
        save_persisted_settings(data)
        runner = get_runner()
        if runner:
            runner.reload_settings()
    except Exception as e:
        logger.error("Error guardando configuración en SQLite: %s", e)
        raise HTTPException(status_code=500, detail="No se pudo guardar la configuración.")


@router.get("")
def get_settings() -> Dict[str, Any]:
    """
    Devuelve la configuración del sistema para la interfaz web.
    Garantía de privacidad: JAMÁS expone tokens ni variables de entorno del archivo .env.
    """
    data = _read_settings()

    stored_token = _get_secret("TELEGRAM_BOT_TOKEN", os.getenv("TELEGRAM_BOT_TOKEN", "")).strip()
    is_placeholder = "ABCdefGhIJK" in stored_token or "tu_token" in stored_token.lower() or stored_token.startswith("123456789:")
    telegram_bot_token_present = bool(stored_token) and not is_placeholder
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

    cfg_bot_user = data.get("notificaciones", {}).get("telegram", {}).get("bot_username", "")
    if not cfg_bot_user and telegram_bot_token_present:
        try:
            import urllib.request, json
            req_me = urllib.request.urlopen(f"https://api.telegram.org/bot{stored_token}/getMe", timeout=2)
            me_res = json.loads(req_me.read().decode())
            if me_res.get("ok"):
                cfg_bot_user = me_res["result"].get("username", "")
                if "telegram" not in data["notificaciones"]:
                    data["notificaciones"]["telegram"] = {}
                data["notificaciones"]["telegram"]["bot_username"] = cfg_bot_user
                _save_settings(data)
        except Exception:
            pass

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
            "telegram_bot_username": cfg_bot_user,
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

    if req.telegram_bot_token is not None:
        if "telegram" not in data["notificaciones"]:
            data["notificaciones"]["telegram"] = {}
        clean_token = req.telegram_bot_token.strip()
        if clean_token:
            _save_persisted_secret("TELEGRAM_BOT_TOKEN", clean_token)
            os.environ["TELEGRAM_BOT_TOKEN"] = clean_token
            _update_env_file("TELEGRAM_BOT_TOKEN", clean_token)
            data["notificaciones"]["telegram"]["bot_token"] = clean_token
        else:
            _delete_persisted_secret("TELEGRAM_BOT_TOKEN")
            os.environ.pop("TELEGRAM_BOT_TOKEN", None)
            _update_env_file("TELEGRAM_BOT_TOKEN", "")
            data["notificaciones"]["telegram"].pop("bot_token", None)

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


@router.post("/test-telegram")
async def test_telegram_notification() -> Dict[str, Any]:
    """Envía un mensaje de prueba inmediato a Telegram con diagnóstico detallado."""
    runner = get_runner()
    if not runner or not runner.telegram_bot:
        raise HTTPException(status_code=500, detail="Módulo de Telegram no disponible en el servidor.")

    runner.telegram_bot.reload_credentials()

    if not runner.telegram_bot.token or "ABCdefGhIJK" in runner.telegram_bot.token:
        raise HTTPException(
            status_code=400,
            detail="Falta el Token del Bot de Telegram. Debes crearlo con @BotFather en Telegram y guardarlo en la configuración.",
        )

    if not runner.telegram_bot.allowed_user_id or runner.telegram_bot.allowed_user_id <= 0:
        raise HTTPException(
            status_code=400,
            detail="Falta el ID de usuario de Telegram. Obtén tu ID numérico hablando con @userinfobot en Telegram y guárdalo.",
        )

    test_message = (
        "🔔 <b>¡Conexión de Telegram con lazyJobFinder confirmada!</b>\n\n"
        "Tu bot está correctamente configurado y enlazado. "
        "A partir de ahora recibirás aquí tus alertas de empleo, resúmenes de afinidad y documentos adaptados."
    )

    try:
        success = await runner.telegram_bot.send_message(test_message)
        if success:
            return {"success": True, "message": "¡Mensaje de prueba enviado con éxito a tu Telegram!"}
        else:
            raise HTTPException(status_code=500, detail="El bot no pudo enviar el mensaje. Comprueba las credenciales.")
    except Exception as e:
        err_msg = str(e)
        logger.error("Fallo al enviar mensaje de prueba por Telegram: %s", err_msg)
        bot_username = ""
        try:
            bot = await runner.telegram_bot._get_bot()
            if bot:
                me = await bot.get_me()
                bot_username = me.username or ""
        except Exception:
            pass

        if "chat not found" in err_msg.lower() or "bot was blocked" in err_msg.lower():
            link = f"https://t.me/{bot_username}" if bot_username else "tu bot"
            detail = (
                f"Telegram devolvió 'Chat not found'. Tu ID de usuario está bien puesto, pero Telegram requiere "
                f"que primero abras una conversación con tu bot ({link}) y pulses el botón 'Iniciar' (/start). "
                f"Una vez pulsado Iniciar en Telegram, vuelve a probar."
            )
        elif "unauthorized" in err_msg.lower():
            detail = "Token del Bot no válido. Verifica el token que te dio @BotFather."
        else:
            detail = f"Error comunicando con Telegram: {err_msg}"
        raise HTTPException(status_code=400, detail=detail)


@router.post("/telegram/auto-link")
async def auto_link_telegram_user() -> Dict[str, Any]:
    """
    Inspecciona los mensajes recientes recibidos por el bot para vincular automáticamente
    al usuario que haya pulsado 'Iniciar' (/start), evitando la necesidad de buscar el ID numérico.
    """
    runner = get_runner()
    if not runner or not runner.telegram_bot:
        raise HTTPException(status_code=500, detail="Módulo de Telegram no disponible en el servidor.")

    runner.telegram_bot.reload_credentials()
    bot = await runner.telegram_bot._get_bot()
    if not bot:
        raise HTTPException(status_code=400, detail="Bot de Telegram no configurado o token ausente.")

    me = await bot.get_me()
    updates = await bot.get_updates(limit=10)

    if not updates:
        raise HTTPException(
            status_code=400,
            detail=(
                f"El bot @{me.username} aún no ha recibido ningún mensaje. "
                f"Abre https://t.me/{me.username} en Telegram, pulsa el botón 'Iniciar' (/start) "
                f"y vuelve a pulsar aquí para detectarlo."
            ),
        )

    last_user = None
    for u in reversed(updates):
        if u.effective_user and not u.effective_user.is_bot:
            last_user = u.effective_user
            break

    if not last_user:
        raise HTTPException(status_code=400, detail="No se encontró ningún usuario humano en los mensajes del bot.")

    user_id_str = str(last_user.id)
    _save_persisted_secret("TELEGRAM_ALLOWED_USER_ID", user_id_str)
    os.environ["TELEGRAM_ALLOWED_USER_ID"] = user_id_str
    _update_env_file("TELEGRAM_ALLOWED_USER_ID", user_id_str)

    data = _read_settings()
    if "notificaciones" not in data:
        data["notificaciones"] = {}
    if "telegram" not in data["notificaciones"]:
        data["notificaciones"]["telegram"] = {}
    data["notificaciones"]["telegram"]["allowed_user_id"] = user_id_str
    data["notificaciones"]["telegram"]["bot_username"] = me.username
    _save_settings(data)

    runner.telegram_bot.reload_credentials()

    try:
        await runner.telegram_bot.send_message(
            f"🎉 <b>¡Vinculación completada con éxito!</b>\n\n"
            f"Hola {html.escape(last_user.first_name or 'Roberto')}, tu usuario ha quedado enlazado "
            f"exclusivamente con tu panel local de lazyJobFinder."
        )
    except Exception:
        pass

    return {
        "success": True,
        "user_id": user_id_str,
        "username": last_user.username,
        "first_name": last_user.first_name,
        "message": f"¡Usuario @{last_user.username or last_user.first_name} (ID: {user_id_str}) vinculado y confirmado con éxito!",
    }

