"""Cliente HTTP robusto para la instancia de Ollama ejecutándose en Docker."""

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional
try:
    import requests
    from requests.adapters import HTTPAdapter
except ImportError:
    requests = None
    HTTPAdapter = None

logger = logging.getLogger("lazyJobFinder.evaluator.ollama")


class OllamaClient:
    """Cliente para interactuar con la API REST de Ollama en contenedor local con connection pooling."""

    def __init__(self, base_url: Optional[str] = None, default_model: Optional[str] = None):
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")).rstrip("/")
        self.default_model = default_model or os.getenv("OLLAMA_MODEL", "qwen2.5:3b-instruct")
        self._last_health_check_time: float = 0.0
        self._cached_health: Optional[Dict[str, Any]] = None

        if requests and HTTPAdapter:
            self._session = requests.Session()
            adapter = HTTPAdapter(pool_connections=5, pool_maxsize=10, max_retries=0)
            self._session.mount("http://", adapter)
            self._session.mount("https://", adapter)
        else:
            self._session = None

    def check_health(self, force: bool = False) -> Dict[str, Any]:
        """Verifica la conectividad con Ollama con caché rápida (15s) y timeout corto (2.5s)."""
        now = time.time()
        if not force and self._cached_health is not None and (now - self._last_health_check_time < 15.0):
            return self._cached_health

        try:
            http_client = self._session or requests
            resp = http_client.get(f"{self.base_url}/api/tags", timeout=2.5)
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("name") for m in data.get("models", [])]
                res = {
                    "online": True,
                    "models": models,
                    "default_model": self.default_model,
                    "default_model_installed": any(
                        self.default_model.split(":")[0] in m for m in models
                    ),
                }
                self._cached_health = res
                self._last_health_check_time = now
                return res
            res = {"online": False, "error": f"HTTP {resp.status_code}"}
            self._cached_health = res
            self._last_health_check_time = now
            return res
        except Exception as e:
            logger.debug("Ollama healthcheck falló: %s", e)
            res = {"online": False, "error": str(e)}
            self._cached_health = res
            self._last_health_check_time = now
            return res

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        model: Optional[str] = None,
        format_json: bool = True,
        format_schema: Optional[Any] = None,
        temperature: float = 0.1,
        timeout: int = 120,
    ) -> str:
        """
        Envía un prompt a Ollama y retorna la respuesta generada.
        Soporta formato JSON genérico ('format': 'json') o salidas estructuradas nativas
        restringidas por gramática llama.cpp pasando un JSON Schema ('format': {...}).
        """
        target_model = model or self.default_model
        payload = {
            "model": target_model,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
            "keep_alive": "24h",
            "options": {
                "temperature": temperature,
                "top_p": 0.9,
                "num_ctx": 2048,
                "num_predict": 512,
            },
        }

        # Soporte para salidas estructuradas de Ollama (JSON Schema o boolean)
        if format_schema is not None:
            if isinstance(format_schema, dict):
                payload["format"] = format_schema
            elif isinstance(format_schema, str):
                payload["format"] = format_schema
            elif format_schema:
                payload["format"] = "json"
        elif format_json:
            payload["format"] = "json"

        if not self.check_health().get("online"):
            raise ConnectionError(f"Ollama no está disponible en {self.base_url}")

        endpoint = f"{self.base_url}/api/generate"
        max_retries = 2
        backoff = 1.0

        for attempt in range(1, max_retries + 1):
            try:
                logger.debug(
                    "Llamando a Ollama (intento %d/%d) con modelo '%s'...",
                    attempt,
                    max_retries,
                    target_model,
                )
                start_time = time.time()
                http_client = self._session or requests
                resp = http_client.post(endpoint, json=payload, timeout=timeout)
                elapsed = time.time() - start_time

                if resp.status_code == 200:
                    data = resp.json()
                    response_text = data.get("response", "").strip()
                    logger.debug("Ollama respondió en %.2f segundos (%d chars).", elapsed, len(response_text))
                    return response_text

                # Si el modelo no está instalado, abortar inmediatamente sin reintentos inútiles
                if resp.status_code == 404:
                    err_msg = (
                        f"Modelo '{target_model}' no encontrado en Ollama (HTTP 404). "
                        f"Descárgalo con: docker exec -it lazyjob_ollama ollama pull {target_model}"
                    )
                    logger.error(err_msg)
                    raise FileNotFoundError(err_msg)

                logger.warning(
                    "Ollama retornó HTTP %d: %s. Reintentando...",
                    resp.status_code,
                    resp.text[:200],
                )
            except requests.exceptions.Timeout as e:
                logger.warning("Ollama ocupado procesando tokens en CPU (intento %d/%d superó los %ss): %s", attempt, max_retries, timeout, e)
            except requests.exceptions.RequestException as e:
                self._cached_health = {"online": False, "error": str(e)}
                self._last_health_check_time = time.time()
                logger.warning("Fallo de conexión con Ollama en intento %d/%d: %s", attempt, max_retries, e)

            if attempt < max_retries:
                time.sleep(backoff)
                backoff *= 2.0

        raise RuntimeError(
            f"No se pudo obtener respuesta de Ollama tras {max_retries} intentos en {self.base_url}"
        )
