"""Centralización automática de la caché de bytecode de Python para todo el repositorio."""

import os
import sys

# Forzar que cualquier ejecución de Python (CLI, VS Code, Pylance, py_compile, pytest)
# escriba exclusivamente en src/__pycache__ y no genere carpetas __pycache__ dispersas
_repo_root = os.path.dirname(os.path.abspath(__file__))
_central_cache = os.path.join(_repo_root, "src", "__pycache__")
try:
    os.makedirs(_central_cache, exist_ok=True)
    sys.pycache_prefix = _central_cache
    os.environ["PYTHONPYCACHEPREFIX"] = _central_cache
except Exception:
    pass
