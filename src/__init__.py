"""lazyJobFinder: Sistema local y gratuito de búsqueda de empleo automatizada."""

__version__ = "1.0.0"

# Centralizar la caché de bytecode de Python en .cache/pycache/ desde el inicio
from .storage import setup_pycache_centralization

setup_pycache_centralization()
