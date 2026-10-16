"""Aplicación FastAPI principal para la interfaz de administración local de lazyJobFinder."""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

web_out_candidates = [
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "web", "out")),
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
