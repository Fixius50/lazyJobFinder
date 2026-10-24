"""Orquestador completo del pipeline y planificador de ejecución periódica con APScheduler."""

import asyncio
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import yaml

from ..connectors.manager import ConnectorManager
from ..database import Database
from ..evaluator.ollama_client import OllamaClient
from ..evaluator.scoring_engine import ScoringEngine
from ..tailoring.cover_letter import CoverLetterGenerator
from ..tailoring.cv_tailorer import CVTailorer
from ..tailoring.pdf_renderer import PDFRenderer
from ..telegram_bot.bot import TelegramJobBot

logger = logging.getLogger("lazyJobFinder.scheduler.runner")


class JobPipelineRunner:
    """Orquesta todo el flujo: Descubrimiento -> Deduplicación -> Scoring -> Documentos -> Telegram."""

    def __init__(
        self,
        config_dir: Optional[str] = None,
        db_path: Optional[str] = None,
    ):
        from ..storage import CONFIG_DIR
        self.config_dir = config_dir or CONFIG_DIR

        # 1. Cargar configuraciones
        self.settings = self._load_yaml(os.path.join(self.config_dir, "settings.yaml"))
        self.profile_path = os.path.join(self.config_dir, "profile.yaml")
        self.profile = self._load_yaml(self.profile_path)

        # 2. Inicializar persistencia y clientes
        self.db = Database(db_path=db_path)
        self.ollama = OllamaClient()
        self.connectors_mgr = ConnectorManager(db=self.db, settings=self.settings)
        self.scoring_engine = ScoringEngine(
            db=self.db,
            profile_path=self.profile_path,
            settings=self.settings,
            ollama_client=self.ollama,
        )
        self.cv_tailorer = CVTailorer(profile=self.profile, ollama_client=self.ollama)
        self.letter_generator = CoverLetterGenerator(profile=self.profile, ollama_client=self.ollama)
        self.pdf_renderer = PDFRenderer()

        # 3. Inicializar Bot de Telegram pasando referencia al gestor de conectores para diagnóstico
        self.telegram_bot = TelegramJobBot(
            db=self.db,
            settings=self.settings,
            ollama_client=self.ollama,
            manual_search_callback=self.run_pipeline_sync,
            connectors_manager=self.connectors_mgr,
        )

        # 4. Planificador con control explícito de concurrencia y reinicios
        self.scheduler = AsyncIOScheduler()
        self._async_lock: Optional[asyncio.Lock] = None

    def _load_yaml(self, path: str) -> Dict[str, Any]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error("Error cargando configuración YAML desde %s: %s", path, e)
            return {}

    def run_pipeline_sync(self) -> None:
        """Punto de entrada síncrono para llamadas desde hilos de Telegram."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.run_pipeline(is_manual=True))
            else:
                loop.run_until_complete(self.run_pipeline(is_manual=True))
        except RuntimeError:
            asyncio.run(self.run_pipeline(is_manual=True))

    async def run_pipeline(self, is_manual: bool = False, trigger_label: Optional[str] = None) -> None:
        """
        Ejecuta el ciclo de búsqueda y evaluación con bloqueo asíncrono estricto.
        Garantiza que una búsqueda manual y una programada nunca se solapen.
        """
        if self._async_lock is None:
            self._async_lock = asyncio.Lock()

        if self._async_lock.locked():
            logger.warning("Búsqueda ya en curso. Rechazando invocación concurrente.")
            if is_manual and self.telegram_bot.is_configured():
                await self.telegram_bot.send_message("⏳ Ya hay un escaneo de empleo en curso. Por favor espera a que finalice.")
            return

        async with self._async_lock:
            start_time = time.time()
            trigger_type = trigger_label or ("manual" if is_manual else "scheduled")
            run_id = self.db.start_pipeline_run(trigger_type)
            tag = trigger_type.upper()

            logger.info(">>> INICIANDO PIPELINE DE EMPLEO (%s) - Run ID: %d <<<", tag, run_id)
            self.db.log_event("INFO", "pipeline", f"Inicio de escaneo ({tag}) [Run ID {run_id}]")

            total_found = 0
            new_count = 0
            relevant_matches = []
            error_encountered = None

            # Inicializar preferencias de canal inmediatamente para garantizar su disponibilidad en bloques except
            send_tg_pref = (
                self.settings.get("notificaciones", {}).get("enviar_telegram", True)
                and self.settings.get("notificaciones", {}).get("telegram", {}).get("habilitado", True)
            )
            save_ui_pref = self.settings.get("notificaciones", {}).get("guardar_en_interfaz", True)

            try:
                # Recargar configuración fresca desde disco para respetar cambios recientes o del CV activo
                import yaml
                from ..storage import SETTINGS_FILE
                if os.path.exists(SETTINGS_FILE):
                    try:
                        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                            fresh = yaml.safe_load(f) or {}
                            self.settings = fresh
                            self.connectors_mgr.settings = fresh
                    except Exception as s_err:
                        logger.debug("Error recargando settings en runner: %s", s_err)

                # 1. Descubrimiento de ofertas y deduplicación (en worker thread)
                self.db.log_event("INFO", "pipeline", "Iniciando rastreo de ofertas en portales...")
                new_jobs, metrics = await asyncio.to_thread(self.connectors_mgr.run_discovery)
                total_found = metrics["total_encontradas"]
                new_count = metrics["nuevas_guardadas"]
                self.db.log_event("INFO", "pipeline", f"Descubrimiento completado: {total_found} ofertas encontradas ({new_count} nuevas registradas).")

                # Combinar ofertas recién descubiertas con cualquier vacante pendiente de evaluación en BD
                pending_jobs = await asyncio.to_thread(self.db.get_unevaluated_jobs, 100)
                job_dict = {}
                for j in pending_jobs:
                    j_id = j.get("id") if isinstance(j, dict) else j["id"]
                    if j_id:
                        job_dict[j_id] = dict(j)
                for j in new_jobs:
                    j_id = j.get("id") if isinstance(j, dict) else j["id"]
                    if j_id:
                        job_dict[j_id] = dict(j)
                jobs_to_evaluate = list(job_dict.values())

                if not jobs_to_evaluate:
                    logger.info("No hay vacantes nuevas ni pendientes de evaluación en este ciclo.")
                    self.db.log_event("INFO", "pipeline", "No hay vacantes nuevas ni pendientes de evaluación en este ciclo.")
                    self.db.finish_pipeline_run(
                        run_id=run_id,
                        status="completed",
                        total_found=total_found,
                        new_jobs=0,
                        relevant_jobs=0,
                    )
                    if send_tg_pref and self.telegram_bot.is_configured():
                        await self.telegram_bot.send_message(
                            f"ℹ️ <b>Escaneo {tag.lower()} finalizado:</b>\n"
                            f"Se escanearon {total_found} ofertas en las fuentes, pero no hay vacantes nuevas hoy."
                        )
                    return

                # 2. Evaluación paralela y delimitada con pre-filtro y Ollama
                min_score = self.settings.get("evaluacion", {}).get("umbral_minimo_puntuacion", 65)
                generate_docs = self.settings.get("evaluacion", {}).get("generar_documentos", True)
                concurrency = int(self.settings.get("evaluacion", {}).get("concurrencia", 2))
                semaphore = asyncio.Semaphore(concurrency)
                self.db.log_event("INFO", "pipeline", f"Iniciando evaluación de {len(jobs_to_evaluate)} vacantes con IA (umbral: {min_score}%)...")

                async def _evaluate_and_process_job(job: Dict[str, Any]) -> Optional[Dict[str, Any]]:
                    async with semaphore:
                        # Ceder brevemente el control al event loop para responder peticiones HTTP (healthcheck/UI)
                        await asyncio.sleep(0.02)
                        try:
                            self.db.update_job_status(job["id"], "evaluating")
                            eval_res = await asyncio.to_thread(self.scoring_engine.evaluate, job)
                            score = eval_res.get("score", 0)
                            telegram_status = 0

                            if score >= min_score and eval_res.get("should_apply"):
                                doc_paths = None
                                if generate_docs:
                                    from ..tailoring.cv_reader import get_active_cv_status
                                    cv_status = get_active_cv_status()

                                    # Si el usuario subió un CV o si tenemos el perfil cargado en profile.yaml
                                    if cv_status.get("has_cv") or bool(self.profile):
                                        self.db.update_job_status(job["id"], "generating_docs")
                                        # 3. Adaptación honesta y validada de CV y Carta de Presentación
                                        cv_md, diff_audit = await asyncio.to_thread(self.cv_tailorer.tailor, job, eval_res)
                                        letter_md = await asyncio.to_thread(self.letter_generator.generate, job, eval_res)

                                        # 4. Compilación PDF ATS-friendly con ReportLab
                                        doc_paths = await asyncio.to_thread(
                                            self.pdf_renderer.render_cv_and_letter,
                                            job=job,
                                            cv_md=cv_md,
                                            diff_audit=diff_audit,
                                            letter_md=letter_md,
                                        )

                                        # 5. Persistir rutas en base de datos
                                        self.db.save_documents({
                                            "job_id": job["id"],
                                            "cv_pdf_path": doc_paths["cv_pdf_path"],
                                            "cv_md_path": doc_paths["cv_md_path"],
                                            "letter_pdf_path": doc_paths["letter_pdf_path"],
                                            "letter_md_path": doc_paths["letter_md_path"],
                                            "diff_summary": yaml.dump(diff_audit, allow_unicode=True),
                                        })

                                # 6. Notificar por Telegram solo si el canal está expresamente habilitado
                                if send_tg_pref and self.telegram_bot.is_configured():
                                    try:
                                        await self.telegram_bot.send_job_notification(
                                            job=job,
                                            eval_result=eval_res,
                                            doc_paths=doc_paths,
                                        )
                                        telegram_status = 1
                                    except Exception as tg_err:
                                        logger.error("Error enviando notificación Telegram para oferta ID %d: %s", job["id"], tg_err)
                                        telegram_status = -1
                                else:
                                    telegram_status = 0

                                # 7. Actualizar estados independientes por canal
                                ui_saved_val = 1 if save_ui_pref else 0
                                self.db.update_job_channel_status(
                                    job_id=job["id"],
                                    telegram_notified=telegram_status,
                                    ui_saved=ui_saved_val,
                                )
                                self.db.update_job_status(job["id"], "notified" if telegram_status == 1 else "evaluated")
                                self.db.log_event("INFO", "pipeline", f"Oferta ID {job['id']} ('{job.get('title', '')[:30]}') puntuada: {score}/100 -> APTO (Documentos generados).")
                                return job
                            else:
                                self.db.update_job_status(job["id"], "discarded")
                                self.db.log_event("INFO", "pipeline", f"Oferta ID {job['id']} ('{job.get('title', '')[:30]}') puntuada: {score}/100 -> Descartada (< {min_score}).")
                                return None

                        except Exception as eval_err:
                            logger.error("Error evaluando oferta ID %d: %s", job.get("id"), eval_err)
                            self.db.log_event("ERROR", "evaluator", f"Fallo evaluando oferta ID {job.get('id')}: {str(eval_err)}")
                            self.db.update_job_status(job.get("id"), "discovered")
                            return None

                eval_tasks = [_evaluate_and_process_job(job) for job in jobs_to_evaluate]
                eval_results = await asyncio.gather(*eval_tasks, return_exceptions=True)
                for res in eval_results:
                    if isinstance(res, dict):
                        relevant_matches.append(res)

                elapsed = time.time() - start_time
                self.db.finish_pipeline_run(
                    run_id=run_id,
                    status="completed",
                    total_found=total_found,
                    new_jobs=new_count,
                    relevant_jobs=len(relevant_matches),
                )
                self.db.log_event(
                    "INFO",
                    "pipeline",
                    f"Ciclo completado en {elapsed:.1f}s: {new_count} nuevas registradas, {len(relevant_matches)} relevantes procesadas.",
                )

                logger.info(
                    "Ciclo finalizado en %.1fs: %d ofertas nuevas evaluadas, %d relevantes procesadas.",
                    elapsed,
                    len(new_jobs),
                    len(relevant_matches),
                )

                # Resumen final en Telegram (solo si canal habilitado)
                if send_tg_pref and self.telegram_bot.is_configured():
                    source_stats_str = ", ".join(f"{k}: {v}" for k, v in metrics.get("por_fuente", {}).items())
                    await self.telegram_bot.send_message(
                        f"🏁 <b>Resumen del escaneo ({tag.lower()}):</b>\n"
                        f"• Ofertas nuevas registradas: <b>{new_count}</b>\n"
                        f"• Ofertas relevantes procesadas (≥{min_score}/100): <b>{len(relevant_matches)}</b>\n"
                        f"• Fuentes consultadas: <i>{source_stats_str or 'Normales'}</i>\n"
                        f"• Tiempo de ejecución: <b>{elapsed:.1f}s</b>"
                    )

            except Exception as e:
                error_encountered = str(e)
                logger.error("Error crítico durante ejecución del pipeline: %s", e, exc_info=True)
                self.db.finish_pipeline_run(
                    run_id=run_id,
                    status="failed",
                    total_found=total_found,
                    new_jobs=new_count,
                    relevant_jobs=len(relevant_matches),
                    error_message=error_encountered,
                )
                self.db.log_event("CRITICAL", "pipeline", f"Fallo catastrófico: {str(e)}")
                if send_tg_pref and self.telegram_bot.is_configured():
                    await self.telegram_bot.send_message(f"⚠️ <b>Alerta del sistema:</b> Error en el escaneo: {str(e)}")

    def check_missed_run_on_startup(self) -> None:
        """
        Comprueba al arrancar el contenedor si hoy o en días previos se perdieron ejecuciones.
        1. Registra formalmente en pipeline_runs como 'skipped' los días anteriores en que el equipo estuvo apagado.
        2. Si la ejecución de HOY se perdió (la hora programada ya pasó y no hay ejecuciones hoy),
           programa exactamente UNA ejecución de recuperación (catch-up), evitando acumulaciones en ráfaga.
        """
        # Registrar explícitamente días omitidos previos en el histórico
        self.db.record_skipped_days()

        hora = self.settings.get("horario", {}).get("hora", 8)
        minuto = self.settings.get("horario", {}).get("minuto", 30)

        now = datetime.now()
        scheduled_time_passed = (now.hour > hora) or (now.hour == hora and now.minute >= minuto)

        if scheduled_time_passed and not self.db.has_run_today():
            logger.info(
                "Detectada ejecución diaria perdida hoy (%02d:%02d ya pasó y no hay ejecuciones registradas). "
                "Programando exactamente una ejecución de recuperación (catch-up) en 15 segundos...",
                hora,
                minuto,
            )
            # Ejecutar con retraso para permitir inicialización completa de Ollama
            loop = asyncio.get_event_loop()
            loop.call_later(15, lambda: asyncio.create_task(self.run_pipeline(trigger_label="catch_up")))
        else:
            logger.info("Estado de ejecución diaria verificado: no se requiere catch-up en el arranque.")

    def setup_schedule(self) -> None:
        """
        Programa la tarea diaria recurrente en APScheduler con:
        - max_instances=1 (evita solapamientos)
        - coalesce=True (si hubo varios reinicios o apagados, solo ejecuta una vez)
        - misfire_grace_time=3600 (si el equipo se encendió hasta 1h después de la hora programada, corre al encender)
        """
        hora = self.settings.get("horario", {}).get("hora", 8)
        minuto = self.settings.get("horario", {}).get("minuto", 30)

        trigger = CronTrigger(hour=hora, minute=minuto)
        self.scheduler.add_job(
            self.run_pipeline,
            trigger=trigger,
            id="daily_job_search",
            name="Búsqueda Diaria de Empleo",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=3600,
        )
        logger.info("Planificador programado diariamente a las %02d:%02d horas (coalesce=True).", hora, minuto)

    def is_running(self) -> bool:
        """Indica si el pipeline se encuentra actualmente en ejecución activa."""
        return self._async_lock is not None and self._async_lock.locked()

    def reload_settings(self) -> None:
        """Recarga la configuración desde settings.yaml y propaga los cambios a los componentes."""
        settings_path = os.path.join(self.config_dir, "settings.yaml")
        self.settings = self._load_yaml(settings_path)
        self.connectors_mgr.settings = self.settings
        self.connectors_mgr.reload_connectors()
        self.scoring_engine.settings = self.settings
        self.telegram_bot.settings = self.settings
        self.telegram_bot.reload_credentials()
        logger.info("Configuraciones recargadas dinámicamente en JobPipelineRunner.")
