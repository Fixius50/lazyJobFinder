"""Cliente HTTP robusto para la instancia de Ollama ejecutándose en Docker."""

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional
import requests

logger = logging.getLogger("lazyJobFinder.evaluator.ollama")


class OllamaClient:
    """Cliente para interactuar con la API REST de Ollama en contenedor local."""

    def __init__(self, base_url: Optional[str] = None, default_model: Optional[str] = None):
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")).rstrip("/")
        self.default_model = default_model or os.getenv("OLLAMA_MODEL", "qwen2.5:3b-instruct")

    def check_health(self) -> Dict[str, Any]:
        """Verifica la conectividad con Ollama y lista los modelos disponibles en el volumen."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("name") for m in data.get("models", [])]
                return {
                    "online": True,
                    "models": models,
                    "default_model": self.default_model,
                    "default_model_installed": any(
                        self.default_model.split(":")[0] in m for m in models
                    ),
                }
            return {"online": False, "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            logger.debug("Ollama healthcheck falló: %s", e)
            return {"online": False, "error": str(e)}

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        model: Optional[str] = None,
        format_json: bool = True,
        format_schema: Optional[Any] = None,
        temperature: float = 0.1,
        timeout: int = 60,
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
            "options": {
                "temperature": temperature,
                "top_p": 0.9,
                "num_ctx": 4096,
            },
        }

        # Soporte para salidas estructuradas nativas de Ollama (JSON Schema o boolean)
        if format_schema is not None:
            if isinstance(format_schema, dict):
                payload["format"] = format_schema
            elif isinstance(format_schema, str):
                payload["format"] = format_schema
            elif format_schema:
                payload["format"] = "json"
        elif format_json:
            payload["format"] = "json"

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
                resp = requests.post(endpoint, json=payload, timeout=timeout)
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
            except requests.exceptions.RequestException as e:
                logger.warning("Fallo de conexión con Ollama en intento %d/%d: %s", attempt, max_retries, e)

            if attempt < max_retries:
                time.sleep(backoff)
                backoff *= 2.0

        raise RuntimeError(
            f"No se pudo obtener respuesta de Ollama tras {max_retries} intentos en {self.base_url}"
        )
