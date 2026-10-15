"""Bot interactivo y sistema de notificaciones de Telegram para lazyJobFinder."""

import asyncio
import html
import logging
import os
import time
from typing import Any, Callable, Dict, List, Optional
from telegram import Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

from ..database import Database
from ..evaluator.ollama_client import OllamaClient

logger = logging.getLogger("lazyJobFinder.telegram_bot")

# Constantes de seguridad de Telegram
MAX_MESSAGE_LENGTH = 4000
MAX_CAPTION_LENGTH = 1000


class TelegramJobBot:
    """Gestiona la interfaz conversacional y el envío diario de alertas y documentos por Telegram."""

    def __init__(
        self,
        db: Database,
        settings: Dict[str, Any],
        ollama_client: Optional[OllamaClient] = None,
        manual_search_callback: Optional[Callable[[], Any]] = None,
        connectors_manager: Optional[Any] = None,
    ):
        self.db = db
        self.settings = settings
        self.ollama = ollama_client or OllamaClient()
        self.manual_search_callback = manual_search_callback
        self.connectors_manager = connectors_manager

        self.token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        raw_user_id = os.getenv("TELEGRAM_ALLOWED_USER_ID", "0").strip()
        try:
            self.allowed_user_id = int(raw_user_id)
        except ValueError:
            self.allowed_user_id = 0

        self.app: Optional[Application] = None
        self.last_manual_search_time: float = 0.0
        self.manual_search_cooldown: int = 300  # 5 minutos de enfriamiento para comandos pesados
        self._is_manual_search_running: bool = False

    def is_configured(self) -> bool:
        """Verifica si las credenciales de Telegram están debidamente establecidas."""
        return bool(self.token and self.allowed_user_id > 0)

    def _is_authorized(self, update: Update) -> bool:
        """
        Asegura que únicamente el usuario autorizado pueda ejecutar comandos o recibir datos.
        Si TELEGRAM_ALLOWED_USER_ID no está configurado, deniega a todos por seguridad.
        """
        if not update.effective_user:
            return False
        user_id = update.effective_user.id
        if not self.allowed_user_id or user_id != self.allowed_user_id:
            logger.warning(
                "Intento de acceso no autorizado o bot sin configurar desde usuario ID %d (@%s)",
                user_id,
                update.effective_user.username if update.effective_user else "desconocido",
            )
            return False
        return True

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando de bienvenida y verificación de acceso."""
        if not self._is_authorized(update):
            await update.message.reply_text("⛔ Acceso denegado. Este bot es de uso estrictamente privado.")
            return

        msg = (
            "👋 <b>¡Hola Roberto! Bienvenido a lazyJobFinder</b>\n\n"
            "Tu sistema local y autónomo de búsqueda de empleo está activo y funcionando.\n\n"
            "📌 <b>Comandos disponibles:</b>\n"
            "• <code>/buscar</code> - Dispara una búsqueda y evaluación manual inmediata.\n"
            "• <code>/estado</code> - Diagnóstico del sistema, Ollama, fuentes y base de datos.\n"
            "• <code>/ultimas</code> - Muestra las mejores ofertas recientes registradas.\n"
            "• <code>/config</code> - Ver los términos y filtros activos.\n"
            "• <code>/ayuda</code> - Muestra este mensaje de ayuda.\n\n"
            "🔔 <i>Recibirás automáticamente un resumen matutino con las ofertas que superen el umbral, "
            "acompañadas de tu CV adaptado y carta de presentación en PDF generados localmente.</i>"
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

    async def _cmd_estado(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Muestra el estado de salud de los servicios, Ollama, fuentes y estadísticas de la base de datos."""
        if not self._is_authorized(update):
            return

        stats = self.db.get_statistics()
        ollama_health = self.ollama.check_health()

        ollama_status = "🟢 En línea" if ollama_health.get("online") else f"🔴 Desconectado ({ollama_health.get('error')})"
        installed_models = ", ".join(ollama_health.get("models", [])) or "Ninguno detectado"

        sources_summary_str = "No disponible"
        if self.connectors_manager:
            statuses = self.connectors_manager.get_source_statuses()
            sources_summary_str = "\n".join(f"  • {k}: {v}" for k, v in statuses.items())

        msg = (
            "📊 <b>Estado del Sistema lazyJobFinder</b>\n\n"
            f"🤖 <b>Ollama en Docker:</b> {ollama_status}\n"
            f"🧠 <b>Modelo configurado:</b> <code>{self.ollama.default_model}</code>\n"
            f"📦 <b>Modelos en volumen:</b> {installed_models}\n\n"
            "🌐 <b>Estado de Fuentes de Empleo:</b>\n"
            f"{sources_summary_str}\n\n"
            "🗄 <b>Estadísticas de la Base de Datos:</b>\n"
            f"• Total ofertas registradas: <b>{stats['total_jobs']}</b>\n"
            f"• Ofertas hoy: <b>{stats['jobs_today']}</b>\n"
            f"• Evaluadas por IA/Reglas: <b>{stats['total_evaluated']}</b>\n"
            f"• Ofertas con alta afinidad (≥65): <b>{stats['high_matches']}</b>\n"
            f"• Última ejecución exitosa: <i>{stats['last_run']}</i>\n\n"
            f"⏰ <b>Horario programado:</b> Todos los días a las {self.settings.get('horario', {}).get('hora', 8):02d}:{self.settings.get('horario', {}).get('minuto', 30):02d}h"
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

    async def _cmd_config(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Muestra los filtros y fuentes configurados."""
        if not self._is_authorized(update):
            return

        busq = self.settings.get("busqueda", {})
        terms = ", ".join(busq.get("terminos", []))
        locs = ", ".join(busq.get("ubicaciones", []))
        excl = ", ".join(busq.get("filtros_exclusion", []))
        umbral = self.settings.get("evaluacion", {}).get("umbral_minimo_puntuacion", 65)

        msg = (
            "⚙️ <b>Configuración Activa de Búsqueda</b>\n\n"
            f"🔍 <b>Términos:</b> {terms}\n"
            f"📍 <b>Ubicaciones:</b> {locs}\n"
            f"🚫 <b>Exclusiones:</b> {excl}\n"
            f"🎯 <b>Umbral mínimo:</b> {umbral} / 100\n"
            f"📄 <b>Generación de documentos:</b> {'Activada' if self.settings.get('evaluacion', {}).get('generar_documentos') else 'Desactivada'}"
        )
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

    async def _cmd_ultimas(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Muestra las mejores ofertas recientes registradas en la base de datos."""
        if not self._is_authorized(update):
            return

        umbral = self.settings.get("evaluacion", {}).get("umbral_minimo_puntuacion", 65)
        top_jobs = self.db.get_top_recent_jobs(limit=5, min_score=umbral)

        if not top_jobs:
            await update.message.reply_text(
                f"ℹ️ No hay ofertas recientes que superen la puntuación mínima ({umbral}/100).\n"
                "Puedes lanzar una nueva búsqueda con <code>/buscar</code>.",
                parse_mode=ParseMode.HTML,
            )
            return

        await update.message.reply_text(
            f"🏆 <b>Top {len(top_jobs)} Ofertas Recientes con Mayor Afinidad:</b>",
            parse_mode=ParseMode.HTML,
        )

        for job in top_jobs:
            score = job.get("score", 0)
            score_bar = "🟢" if score >= 80 else "🟡"
            title = html.escape(str(job.get("title", "")))
            company = html.escape(str(job.get("company", "")))
            location = html.escape(str(job.get("location", "")))
            url = job.get("canonical_url", "")
            reasoning = html.escape(str(job.get("reasoning", "")))

            msg = (
                f"{score_bar} <b>{title}</b>\n"
                f"🏢 <b>Empresa:</b> {company}\n"
                f"📍 <b>Ubicación:</b> {location}\n"
                f"🎯 <b>Afinidad:</b> {score}/100 ({job.get('fit_level', 'BUENO')})\n"
                f"💡 <b>Motivo:</b> {reasoning}\n"
                f"🔗 <a href='{url}'>Ver oferta original</a>"
            )
            await update.message.reply_text(msg, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

    async def _cmd_buscar(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Dispara la búsqueda y evaluación manual bajo demanda utilizando el mismo pipeline con cooldown."""
        if not self._is_authorized(update):
            return

        now = time.time()
        elapsed = now - self.last_manual_search_time

        if self._is_manual_search_running:
            await update.message.reply_text(
                "⏳ <b>Escaneo en curso:</b> Ya se está ejecutando una búsqueda en este momento. "
                "Por favor espera a que finalice.",
                parse_mode=ParseMode.HTML,
            )
            return

        if elapsed < self.manual_search_cooldown:
            remaining = int(self.manual_search_cooldown - elapsed)
            minutes = remaining // 60
            seconds = remaining % 60
            time_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"
            await update.message.reply_text(
                f"⏱️ <b>Límite de frecuencia activo:</b> Para proteger la CPU y memoria del equipo, "
                f"debes esperar <b>{time_str}</b> antes de lanzar otro escaneo manual completo.",
                parse_mode=ParseMode.HTML,
            )
            return

        self._is_manual_search_running = True
        self.last_manual_search_time = now

        await update.message.reply_text(
            "🚀 <b>Iniciando búsqueda y evaluación manual bajo demanda...</b>\n"
            "Esto tomará entre 30 y 90 segundos. Te enviaré los resultados en cuanto finalice.",
            parse_mode=ParseMode.HTML,
        )

        if self.manual_search_callback:
            asyncio.create_task(self._execute_manual_search())
        else:
            self._is_manual_search_running = False
            await update.message.reply_text("⚠️ No se ha definido el callback de ejecución de búsqueda.")

    async def _execute_manual_search(self) -> None:
        """Ejecuta el pipeline síncrono de búsqueda en un executor para no bloquear el bot."""
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self.manual_search_callback)
        except Exception as e:
            logger.error("Error durante búsqueda manual: %s", e)
            await self.send_message(f"❌ <b>Error en la búsqueda manual:</b> {html.escape(str(e))}")
        finally:
            self._is_manual_search_running = False

    async def send_message(self, text: str) -> None:
        """Envía un mensaje proactivo al usuario autorizado asegurando los límites de tamaño."""
        if not self.app or not self.allowed_user_id:
            logger.warning("No se puede enviar mensaje por Telegram: bot no inicializado.")
            return

        chunks = [text[i:i + MAX_MESSAGE_LENGTH] for i in range(0, len(text), MAX_MESSAGE_LENGTH)]
        for chunk in chunks:
            try:
                await self.app.bot.send_message(
                    chat_id=self.allowed_user_id,
                    text=chunk,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                )
            except TelegramError as e:
                logger.error("Error de Telegram al enviar mensaje: %s", e)

    async def send_document(self, file_path: str, caption: str = "") -> None:
        """Envía un archivo PDF o Markdown directamente al chat privado del usuario."""
        if not self.app or not self.allowed_user_id or not os.path.exists(file_path):
            return

        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if file_size_mb > 50:
            logger.error("Archivo %s excede los 50MB (%f MB). No se puede enviar.", file_path, file_size_mb)
            return

        safe_caption = caption[:MAX_CAPTION_LENGTH]

        try:
            with open(file_path, "rb") as doc:
                await self.app.bot.send_document(
                    chat_id=self.allowed_user_id,
                    document=doc,
                    caption=safe_caption,
                    parse_mode=ParseMode.HTML,
                )
        except TelegramError as e:
            logger.error("Error de Telegram al enviar documento %s: %s", file_path, e)

    async def send_job_notification(
        self,
        job: Dict[str, Any],
        eval_result: Dict[str, Any],
        doc_paths: Optional[Dict[str, str]] = None,
    ) -> None:
        """Envía el reporte completo de una oferta relevante con sus documentos adjuntos de forma segura."""
        score = eval_result.get("score", 0)
        score_icon = "🟢" if score >= 80 else ("🟡" if score >= 65 else "⚪")
        fit_level = eval_result.get("fit_level", "BUENO")

        title = html.escape(str(job.get("title", "")))
        company = html.escape(str(job.get("company", "")))
        location = html.escape(str(job.get("location", "España")))
        is_remote_str = " (Remoto)" if job.get("is_remote") else ""
        url = job.get("job_url", "") or job.get("canonical_url", "")
        reasoning = html.escape(str(eval_result.get("reasoning", "")))

        matched = eval_result.get("matched_skills", [])
        missing = eval_result.get("missing_skills", [])

        matched_str = ", ".join(html.escape(str(s)) for s in matched) if matched else "Bases formativas DAM"
        missing_str = ", ".join(html.escape(str(s)) for s in missing) if missing else "Ninguno relevante"

        card = (
            f"{score_icon} <b>NUEVA OFERTA RELEVANTE ({score}/100 - {fit_level})</b>\n\n"
            f"💼 <b>Puesto:</b> {title}\n"
            f"🏢 <b>Empresa:</b> {company}\n"
            f"📍 <b>Ubicación:</b> {location}{is_remote_str}\n"
            f"🌐 <b>Fuente:</b> {str(job.get('source', '')).upper()}\n\n"
            f"✅ <b>Requisitos que cumples:</b>\n<i>{matched_str}</i>\n\n"
            f"⚠️ <b>Requisitos adicionales / Por aprender:</b>\n<i>{missing_str}</i>\n\n"
            f"💡 <b>Análisis de afinidad:</b>\n{reasoning}\n\n"
            f"🔗 <a href='{url}'>Ver y solicitar oferta original</a>"
        )

        await self.send_message(card)

        # Enviar documentos adjuntos si están disponibles
        if doc_paths:
            cv_pdf = doc_paths.get("cv_pdf_path")
            letter_pdf = doc_paths.get("letter_pdf_path")

            if cv_pdf and os.path.exists(cv_pdf):
                await self.send_document(
                    cv_pdf,
                    caption=f"📄 <b>CV Adaptado para {company}</b> (Validado, sin alucinaciones)",
                )

            if letter_pdf and os.path.exists(letter_pdf):
                await self.send_document(
                    letter_pdf,
                    caption=f"✉️ <b>Carta de Presentación para {company}</b>",
                )

    def build_application(self) -> Application:
        """Configura y retorna la instancia de Application de python-telegram-bot."""
        if not self.is_configured():
            logger.warning("Credenciales de Telegram no configuradas. El bot no se conectará.")
            return None

        app = ApplicationBuilder().token(self.token).build()

        app.add_handler(CommandHandler("start", self._cmd_start))
        app.add_handler(CommandHandler("ayuda", self._cmd_start))
        app.add_handler(CommandHandler("estado", self._cmd_estado))
        app.add_handler(CommandHandler("config", self._cmd_config))
        app.add_handler(CommandHandler("ultimas", self._cmd_ultimas))
        app.add_handler(CommandHandler("buscar", self._cmd_buscar))

        self.app = app
        return app
