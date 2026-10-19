"""Punto de entrada principal de la aplicación lazyJobFinder."""

import asyncio
import logging
import os
import signal
import sys
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("lazyJobFinder.main")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from .scheduler.runner import JobPipelineRunner


async def main() -> None:
    logger.info("==================================================")
    logger.info("   INICIANDO lazyJobFinder (Versión 1.0.0)        ")
    logger.info("   Búsqueda de Empleo Local, Gratuita y Autónoma ")
    logger.info("==================================================")

    # 1. Instanciar el orquestador principal
    runner = JobPipelineRunner()

    # 2. Programar la ejecución diaria recurrente
    runner.setup_schedule()
    runner.scheduler.start()
    logger.info("Planificador APScheduler iniciado correctamente.")

    # 3. Comprobar si hubo una ejecución perdida hoy al reiniciar el contenedor
    runner.check_missed_run_on_startup()

    # 4. Iniciar API FastAPI local para el panel de administración
    api_server = None
    server_task = None
    try:
        import uvicorn
        from .api.app import app as fastapi_app
        import src.api.deps as api_deps

        # Inyectar el runner singleton inicializado para sincronización perfecta
        api_deps._runner_instance = runner
        api_deps._db_instance = runner.db

        config = uvicorn.Config(
            fastapi_app,
            host="0.0.0.0",
            port=8000,
            log_level="warning",
            access_log=False,
        )
        api_server = uvicorn.Server(config)
        server_task = asyncio.create_task(api_server.serve())
        logger.info("API FastAPI de Administración iniciada en puerto 8000 (http://127.0.0.1:8000/api/docs)")
    except Exception as e:
        logger.warning("No se pudo iniciar la API FastAPI: %s", e)

    # 5. Configurar bot de Telegram
    app = runner.telegram_bot.build_application()

    stop_event = asyncio.Event()

    def _signal_handler():
        logger.info("Señal de detención recibida. Finalizando tareas limpiamente...")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            asyncio.get_running_loop().add_signal_handler(sig, _signal_handler)
        except (NotImplementedError, AttributeError):
            pass

    app_started = False
    if app:
        logger.info(
            "Conectando Bot de Telegram para usuario autorizado ID: %s",
            runner.telegram_bot.allowed_user_id,
        )
        try:
            await app.initialize()
            await app.start()
            await app.updater.start_polling(drop_pending_updates=True)
            await runner.telegram_bot.send_message(
                "🟢 <b>lazyJobFinder ha arrancado con éxito.</b>\n"
                "El sistema está monitorizando ofertas en segundo plano.\n"
                "Panel Web disponible en http://localhost:8000\n"
                "Escribe <code>/estado</code> para ver métricas o <code>/buscar</code> para escaneo inmediato."
            )
            logger.info("Bot de Telegram en modo Long-Polling activo.")
            app_started = True
        except Exception as e:
            logger.error("Error conectando el bot de Telegram: %s. La aplicación continúa activa en modo Web local.", e)
            app_started = False
    else:
        logger.warning(
            "ℹ️ Bot de Telegram no activo (credenciales no configuradas o placeholder en .env).\n"
            "El sistema continúa ejecutando el planificador y la API de administración local."
        )

    # Esperar señal de parada (mantiene vivos la API y el planificador)
    await stop_event.wait()

    # Parada limpia del bot si estaba activo
    if app_started and app and app.updater:
        logger.info("Deteniendo bot de Telegram...")
        try:
            await app.updater.stop()
            await app.stop()
            await app.shutdown()
        except Exception as e:
            logger.warning("Error deteniendo el bot de Telegram: %s", e)

    # Parada limpia del planificador y servidor API
    if api_server:
        api_server.should_exit = True
        if server_task:
            try:
                await asyncio.wait_for(server_task, timeout=5.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass

    runner.scheduler.shutdown()
    logger.info("lazyJobFinder finalizado correctamente.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Aplicación detenida por el usuario.")
