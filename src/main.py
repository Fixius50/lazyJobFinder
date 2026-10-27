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

from .storage import (
    ensure_storage_dirs,
    setup_pycache_centralization,
    sync_secrets_to_env,
)

# Centralizar la caché de compilación bytecode y asegurar carpetas de datos
setup_pycache_centralization()
ensure_storage_dirs()

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Cargar secretos persistentes en el volumen local (/app/data/secrets.json)
# Garantiza que las claves API y de Telegram sobrevivan a la recreación de contenedores Docker
sync_secrets_to_env()

from .scheduler.runner import JobPipelineRunner


SRC_DIR = os.path.abspath(os.path.dirname(__file__))
_RELOAD_REQUESTED = False


async def _code_reload_watcher(stop_event: asyncio.Event) -> None:
    """Monitoriza modificaciones en archivos de código (.py) y solicita reinicio automático si cambian."""
    global _RELOAD_REQUESTED
    if os.getenv("ENABLE_HOT_RELOAD", "false").lower() not in ("true", "1"):
        return

    try:
        from watchfiles import awatch, PythonFilter
        async for changes in awatch(SRC_DIR, watch_filter=PythonFilter(), stop_event=stop_event):
            first_change = next(iter(changes), None)
            changed_name = os.path.basename(first_change[1]) if first_change else "código"
            logger.info("⚡ Cambio detectado en el código fuente (%s). Reiniciando servidor automáticamente...", changed_name)
            _RELOAD_REQUESTED = True
            stop_event.set()
            break
    except Exception as e:
        logger.debug("Observador watchfiles no disponible o finalizado: %s", e)


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
    try:
        import src.api.deps as api_deps
        api_deps.set_stop_event(stop_event)
    except Exception:
        pass

    def _signal_handler():
        logger.info("Señal de detención recibida. Finalizando tareas limpiamente...")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            asyncio.get_running_loop().add_signal_handler(sig, _signal_handler)
        except (NotImplementedError, AttributeError):
            pass

    # 6. Iniciar tarea de auto-recarga ante modificaciones en el código fuente
    watcher_task = asyncio.create_task(_code_reload_watcher(stop_event))

    app_started = False
    if app:
        logger.info(
            "Conectando Bot de Telegram para usuario autorizado ID: %s",
            runner.telegram_bot.allowed_user_id,
        )
        try:
            await app.initialize()
            await app.start()
            await app.updater.start_polling(drop_pending_updates=True, bootstrap_retries=-1, poll_interval=1.0)
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

    if not watcher_task.done():
        watcher_task.cancel()

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

    if _RELOAD_REQUESTED:
        logger.info("Recargando lazyJobFinder con el nuevo código fuente...")
        try:
            os.execv(sys.executable, [sys.executable, "-m", "src.main"])
        except Exception as e:
            logger.warning("Fallo en execv (%s). Finalizando para que Docker reinicie el contenedor.", e)
            sys.exit(0)
