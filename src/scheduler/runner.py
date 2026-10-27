"""Orquestador completo del pipeline y planificador de ejecución periódica con APScheduler."""

import asyncio
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import re
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


def _extract_cv_scoring_keywords(profile: Dict[str, Any], settings: Dict[str, Any]) -> List[str]:
    """Extrae palabras clave y términos de búsqueda del CV activo para ordenar la cola de inferencia."""
    keywords = set()
    search_terms = settings.get("busqueda", {}).get("terminos", [])
    if isinstance(search_terms, list):
        for t in search_terms:
            t_clean = str(t).strip().lower()
            if len(t_clean) >= 3:
                keywords.add(t_clean)

    candidato = profile.get("candidato", {})
    if candidato.get("titular"):
        for word in re.findall(r"\w+", candidato["titular"].lower()):
            if len(word) >= 4:
                keywords.add(word)

    competencias = profile.get("competencias_tecnicas", {})
    if isinstance(competencias, dict):
        for sk_list in competencias.values():
            if isinstance(sk_list, list):
                for sk in sk_list:
                    sk_clean = str(sk).strip().lower()
                    if 3 <= len(sk_clean) <= 25:
                        keywords.add(sk_clean)

    for exp in profile.get("experiencia_laboral", []):
        puesto = (exp.get("puesto") or "").lower()
        for word in re.findall(r"\w+", puesto):
            if len(word) >= 4 and word not in ("responsable", "director", "empresa", "desde", "hasta"):
                keywords.add(word)

    return list(keywords)


def _calculate_job_evaluation_priority(job: Dict[str, Any], keywords: List[str]) -> int:
    """Calcula una prioridad numérica para ordenar el orden de inferencia.
    NO descarta ninguna oferta. Las ofertas con mayor coincidencia con el CV
    se evalúan primero para que los mejores empleos aparezcan en el panel de inmediato."""
    if not keywords:
        return 0
    title = (job.get("title") or "").lower()
    desc = (job.get("description") or "")[:500].lower()
    score = 0
    for kw in keywords:
        if kw in title:
            score += 10
        elif kw in desc:
            score += 2
    return score


class JobPipelineRunner:
    """Orquesta todo el flujo: Descubrimiento -> Deduplicación -> Scoring -> Documentos -> Telegram."""

    def __init__(
        self,
        config_dir: Optional[str] = None,
        db_path: Optional[str] = None,
    ):
        from ..storage import CONFIG_DIR
        self.config_dir = config_dir or CONFIG_DIR

        from ..storage import get_persisted_settings
        from ..tailoring.cv_reader import get_active_profile
        self.settings = get_persisted_settings()
        self.profile = get_active_profile()
        self.profile_path = None

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
        self._stop_requested: bool = False

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

        from ..tailoring.cv_reader import get_active_cv_status
        cv_status = get_active_cv_status()
        if not cv_status.get("has_cv"):
            logger.info("Pipeline omitido: no hay ningún CV activo configurado en el sistema.")
            if is_manual and self.telegram_bot.is_configured():
                await self.telegram_bot.send_message("ℹ️ No hay ningún CV activo seleccionado. Sube o activa un CV en el panel para buscar ofertas.")
            return

        async with self._async_lock:
            self._stop_requested = False
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
                # Recargar configuración fresca desde SQLite para respetar cambios recientes
                from ..storage import get_persisted_settings
                try:
                    fresh = get_persisted_settings()
                    if fresh:
                        self.settings = fresh
                        self.connectors_mgr.settings = fresh
                except Exception as s_err:
                    logger.debug("Error recargando settings en runner: %s", s_err)

                try:
                    from ..tailoring.cv_reader import get_active_profile
                    fresh_prof = get_active_profile(self.profile_path)
                    if fresh_prof:
                        self.profile = fresh_prof
                        if hasattr(self, "cv_tailorer"):
                            self.cv_tailorer.profile = fresh_prof
                            if hasattr(self.cv_tailorer, "verifier"):
                                self.cv_tailorer.verifier.profile = fresh_prof
                        if hasattr(self, "letter_generator"):
                            self.letter_generator.profile = fresh_prof
                except Exception as p_err:
                    logger.debug("Error recargando perfil activo en runner: %s", p_err)

                # 1. Preparar cola concurrente de evaluación para ejecutar descubrimiento y evaluación en paralelo
                self.db.reset_evaluating_jobs()
                active_cv_name = cv_status.get("filename") if cv_status.get("has_cv") else None

                # Recuperar vacantes pendientes de evaluación previas en SQLite (orden natural de registro)
                pending_jobs = await asyncio.to_thread(self.db.get_unevaluated_jobs, 500, active_cv_name)

                eval_queue: asyncio.Queue[Optional[Dict[str, Any]]] = asyncio.Queue()
                seen_job_ids = set()

                for j in pending_jobs:
                    j_id = j.get("id") if isinstance(j, dict) else j["id"]
                    if j_id and j_id not in seen_job_ids:
                        seen_job_ids.add(j_id)
                        eval_queue.put_nowait(dict(j))

                loop = asyncio.get_running_loop()

                def _on_job_saved(job_dict: Dict[str, Any]) -> None:
                    """Callback emitido en tiempo real por cada conector en cuanto guarda una nueva oferta."""
                    if self._stop_requested:
                        return
                    j_id = job_dict.get("id")
                    if j_id and j_id not in seen_job_ids:
                        seen_job_ids.add(j_id)
                        loop.call_soon_threadsafe(eval_queue.put_nowait, job_dict)

                # Parámetros de evaluación y generación documental
                min_score = int(self.settings.get("evaluacion", {}).get("umbral_minimo_puntuacion", 50))
                generate_docs = self.settings.get("evaluacion", {}).get("generar_documentos", False)
                concurrency = max(1, int(self.settings.get("evaluacion", {}).get("concurrencia", 1)))
                qualified_candidates: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []

                from ..tailoring.cv_reader import get_active_cv_status
                cv_status = get_active_cv_status()
                can_generate_docs = generate_docs and (cv_status.get("has_cv") or bool(self.profile))

                # Cola concurrente de generación de documentos en tiempo real
                docs_queue: asyncio.Queue[Optional[Tuple[Dict[str, Any], Dict[str, Any]]]] = asyncio.Queue()
                queued_doc_job_ids = set()

                # Precargar ofertas ya evaluadas en la BD que aún necesiten documentos
                if can_generate_docs:
                    try:
                        pending_docs_db = await asyncio.to_thread(
                            self.db.get_evaluated_jobs_needing_docs,
                            50,
                            active_cv_name,
                            50,
                        )
                        for item in pending_docs_db:
                            j_id = item["id"]
                            if j_id not in queued_doc_job_ids:
                                queued_doc_job_ids.add(j_id)
                                eval_dict = {
                                    "score": item.get("score", 0),
                                    "fit_level": item.get("fit_level", "BUENO"),
                                    "should_apply": bool(item.get("should_apply", True)),
                                    "matched_skills": item.get("matched_skills", []),
                                    "missing_skills": item.get("missing_skills", []),
                                    "strengths": item.get("strengths", []),
                                    "gaps": item.get("gaps", []),
                                    "reasoning": item.get("reasoning", ""),
                                }
                                docs_queue.put_nowait((item, eval_dict))
                        if pending_docs_db:
                            logger.info("Precargadas %d ofertas evaluadas pendientes de documentos en la cola en tiempo real.", len(pending_docs_db))
                    except Exception as pend_err:
                        logger.debug("Error precargando vacantes pendientes de docs: %s", pend_err)

                # Generador y guardador individual de documentos en tiempo real
                async def _generate_docs_for_item(job: Dict[str, Any], eval_res: Dict[str, Any]) -> None:
                    score = eval_res.get("score", 0)
                    doc_paths = None
                    try:
                        self.db.update_job_status(job["id"], "generating_docs")
                        print(f"[Docs / En Vivo] -> Oferta #{job['id']} ('{job.get('title')}', {job.get('company')}) - Score {score}/100: Generando CV y carta...", flush=True)
                        logger.info("Generando CV y carta en tiempo real para oferta ID %d ('%s')", job["id"], job.get("title"))

                        cv_md, diff_audit = await asyncio.to_thread(self.cv_tailorer.tailor, job, eval_res)
                        letter_md = await asyncio.to_thread(self.letter_generator.generate, job, eval_res)

                        doc_paths = await asyncio.to_thread(
                            self.pdf_renderer.render_cv_and_letter,
                            job=job,
                            cv_md=cv_md,
                            diff_audit=diff_audit,
                            letter_md=letter_md,
                        )

                        self.db.save_documents({
                            "job_id": job["id"],
                            "cv_pdf_path": doc_paths["cv_pdf_path"],
                            "cv_md_path": doc_paths["cv_md_path"],
                            "letter_pdf_path": doc_paths["letter_pdf_path"],
                            "letter_md_path": doc_paths["letter_md_path"],
                            "diff_summary": yaml.dump(diff_audit, allow_unicode=True),
                        })
                        logger.info("CV y carta guardados exitosamente para oferta ID %d.", job["id"])
                    except Exception as doc_err:
                        logger.error("Error generando documentos para oferta ID %d: %s", job["id"], doc_err)

                    # Notificación opcional por Telegram
                    telegram_status = 0
                    if send_tg_pref and self.telegram_bot.is_configured():
                        try:
                            await self.telegram_bot.send_job_notification(
                                job=job,
                                eval_result=eval_res,
                                doc_paths=doc_paths,
                            )
                            telegram_status = 1
                        except Exception as tg_err:
                            logger.error("Error enviando notificación Telegram para ID %d: %s", job["id"], tg_err)
                            telegram_status = -1

                    ui_saved_val = 1 if save_ui_pref else 0
                    self.db.update_job_channel_status(
                        job_id=job["id"],
                        telegram_notified=telegram_status,
                        ui_saved=ui_saved_val,
                    )
                    self.db.update_job_status(job["id"], "evaluated")

                # Tarea Consumidora Documental en vivo
                async def _docs_worker():
                    while True:
                        item = await docs_queue.get()
                        if item is None:
                            docs_queue.task_done()
                            break
                        j, er = item
                        relevant_matches.append(j)
                        await _generate_docs_for_item(j, er)
                        docs_queue.task_done()

                # Tarea Productora: Rastreo en portales con guardado incremental en tiempo real
                async def _run_discovery_task():
                    try:
                        self.db.log_event("INFO", "pipeline", "Iniciando rastreo de ofertas en portales y evaluación simultánea...")
                        res = await asyncio.to_thread(
                            self.connectors_mgr.run_discovery,
                            _on_job_saved,
                            lambda: self._stop_requested,
                        )
                        self.db.log_event("INFO", "pipeline", f"Descubrimiento completado: {res[1]['total_encontradas']} ofertas encontradas ({res[1]['nuevas_guardadas']} nuevas registradas).")
                        return res
                    finally:
                        # Indicar a todos los workers de evaluación que la fase de descubrimiento ha concluido
                        for _ in range(concurrency):
                            loop.call_soon_threadsafe(eval_queue.put_nowait, None)

                # Tarea Consumidora: Evaluación con IA en paralelo conforme van llegando o existían pendientes
                async def _eval_worker():
                    while True:
                        if self._stop_requested:
                            eval_queue.task_done()
                            break
                        job = await eval_queue.get()
                        if job is None:
                            eval_queue.task_done()
                            break
                        if self._stop_requested:
                            eval_queue.task_done()
                            break
                        try:
                            self.db.update_job_status(job["id"], "evaluating")
                            eval_res = await asyncio.to_thread(self.scoring_engine.evaluate, job)
                            if not eval_res or eval_res.get("score") is None:
                                self.db.update_job_status(job["id"], "discovered")
                            else:
                                score = eval_res.get("score", 0)
                                if score >= min_score and eval_res.get("should_apply"):
                                    self.db.update_job_status(job["id"], "evaluated")
                                    logger.info("Oferta ID %d ('%s') puntuada: %d/100 -> APTO.", job["id"], job.get("title", "")[:30], score)
                                    qualified_candidates.append((job, eval_res))
                                    # Encolar para generación de CV y carta mientras se siguen buscando ofertas
                                    if can_generate_docs and job["id"] not in queued_doc_job_ids:
                                        queued_doc_job_ids.add(job["id"])
                                        docs_queue.put_nowait((job, eval_res))
                                else:
                                    self.db.update_job_status(job["id"], "discarded")
                                    logger.info("Oferta ID %d ('%s') puntuada: %d/100 -> Descartada (< %d).", job["id"], job.get("title", "")[:30], score, min_score)
                        except Exception as eval_err:
                            logger.error("Error evaluando oferta ID %d: %s", job.get("id"), eval_err)
                            self.db.update_job_status(job.get("id"), "discovered")
                        finally:
                            eval_queue.task_done()

                # Ejecutar descubrimiento, evaluación y generación documental concurrentemente
                discovery_task = asyncio.create_task(_run_discovery_task())
                eval_tasks = [asyncio.create_task(_eval_worker()) for _ in range(concurrency)]
                docs_task = asyncio.create_task(_docs_worker())

                discovery_result, *_ = await asyncio.gather(discovery_task, *eval_tasks)
                new_jobs, metrics = discovery_result
                total_found = metrics["total_encontradas"]
                new_count = metrics["nuevas_guardadas"]

                # Indicar a la tarea de documentos que ya no entrarán más ofertas nuevas y esperar a que vacíe la cola
                await docs_queue.put(None)
                await docs_task

                # Si no hubo ofertas evaluadas ni pendientes ni nuevas, finalizar run
                if not seen_job_ids and not new_jobs and not relevant_matches:
                    logger.info("No hay vacantes nuevas ni pendientes de evaluación en este ciclo.")
                    self.db.log_event("INFO", "pipeline", "No hay vacantes nuevas ni pendientes de evaluación en este ciclo.")
                    self.db.finish_pipeline_run(
                        run_id=run_id,
                        status="completed",
                        total_found=total_found,
                        new_jobs=0,
                        relevant_jobs=0,
                    )
                    return

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

    def check_missed_run_on_startup(self) -> None:
        """
        Comprueba al arrancar el contenedor si hoy o en días previos se perdieron ejecuciones.
        1. Registra formalmente en pipeline_runs como 'skipped' los días anteriores en que el equipo estuvo apagado.
        2. Si la ejecución de HOY se perdió (la hora programada ya pasó y no hay ejecuciones hoy),
           programa exactamente UNA ejecución de recuperación (catch-up), evitando acumulaciones en ráfaga.
        """
        # Registrar explícitamente días omitidos previos en el histórico
        self.db.record_skipped_days()

        # Si no hay CV activo, omitir catch-up en el arranque
        from ..tailoring.cv_reader import get_active_cv_status
        cv_status = get_active_cv_status()
        if not cv_status.get("has_cv"):
            logger.info("Sin CV activo configurado en el sistema. Omitiendo catch-up de ejecución diaria en el arranque.")
            return

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

    def request_stop(self) -> bool:
        """Solicita la detención inmediata del ciclo de búsqueda en ejecución."""
        if not self.is_running():
            return False
        self._stop_requested = True
        logger.info("Detención de búsqueda solicitada por el usuario.")
        self.db.log_event("WARNING", "pipeline", "Detención de búsqueda solicitada por el usuario desde la interfaz web.")
        return True

    def reload_settings(self) -> None:
        """Recarga la configuración desde SQLite y propaga los cambios a los componentes."""
        from ..storage import get_persisted_settings
        self.settings = get_persisted_settings()
        self.connectors_mgr.settings = self.settings
        self.connectors_mgr.reload_connectors()
        self.scoring_engine.settings = self.settings
        self.telegram_bot.settings = self.settings
        self.telegram_bot.reload_credentials()
        logger.info("Configuraciones recargadas dinámicamente desde SQLite en JobPipelineRunner.")
