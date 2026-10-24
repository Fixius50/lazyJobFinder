"""Configuración automática de Python para centralizar pycache en todo el proyecto."""
import os
import sys

_repo_root = os.path.dirname(os.path.abspath(__file__))
_cache_target = os.environ.get("PYTHONPYCACHEPREFIX") or os.path.join(_repo_root, ".cache", "pycache")

try:
    os.makedirs(_cache_target, exist_ok=True)
    if sys.pycache_prefix != _cache_target:
        sys.pycache_prefix = _cache_target
        os.environ["PYTHONPYCACHEPREFIX"] = _cache_target
except Exception:
    pass
