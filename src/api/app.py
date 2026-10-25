"""Aplicación FastAPI principal para la interfaz de administración local de lazyJobFinder."""

import logging
import mimetypes
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Garantizar tipos MIME correctos para hojas de estilo y scripts estáticos
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("application/javascript", ".js")

from .routes import cv, jobs, maintenance, search, settings, system

logger = logging.getLogger("lazyJobFinder.api")

app = FastAPI(
    title="lazyJobFinder Admin API",
    description="API REST local y autónoma para el panel de administración de lazyJobFinder.",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class ActivityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        system.record_activity()
        return await call_next(request)


# Registrar actividad en cada petición recibida en el puerto 8000
app.add_middleware(ActivityMiddleware)

# Permitir CORS únicamente para orígenes locales del panel frontend (Next.js)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_app_startup():
    idle_sec = int(os.getenv("IDLE_SHUTDOWN_SECONDS", "180"))
    if idle_sec > 0:
        system.start_port_activity_watchdog(idle_seconds=idle_sec, startup_grace_seconds=180)

# Montar routers bajo el prefijo /api
app.include_router(system.router, prefix="/api")
app.include_router(cv.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(maintenance.router, prefix="/api")


@app.get("/api/health")
def api_health():
    """Comprobación de salud básica de la API."""
    return {"status": "ok", "app": "lazyJobFinder Admin API", "version": "1.0.0"}


# Servir el frontend compilado (Next.js export) en el mismo puerto 8000 unificado
import os
from fastapi.staticfiles import StaticFiles
from ..storage import WEB_OUT_DIR

web_out_candidates = [
    WEB_OUT_DIR,
    "/app/web/out",
]
for candidate in web_out_candidates:
    if os.path.isdir(candidate):
        logger.info("Montando frontend web estático unificado desde: %s", candidate)
        app.mount("/", StaticFiles(directory=candidate, html=True), name="frontend")
        break


if __name__ == "__main__":
    import uvicorn
    # Vincular estrictamente a localhost por defecto para máxima seguridad
    uvicorn.run("src.api.app:app", host="127.0.0.1", port=8000, reload=True)
