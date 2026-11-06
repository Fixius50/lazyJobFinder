"""Cliente HTTP robusto para la instancia de Ollama ejecutándose en Docker."""

import json
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional
try:
    import requests
    from requests.adapters import HTTPAdapter
except ImportError:
    requests = None
    HTTPAdapter = None

try:
    import ollama
except ImportError:
    ollama = None

logger = logging.getLogger("lazyJobFinder.evaluator.ollama")


class OllamaClient:
    """Cliente para interactuar con la API REST de Ollama en contenedor local o host con connection pooling, detección de GPU y concurrencia adaptable."""

    _generation_lock = threading.Lock()

    def __init__(
        self,
        base_url: Optional[str] = None,
        default_model: Optional[str] = None,
        max_concurrency: Optional[int] = None,
    ):
        self.default_model = default_model or os.getenv("OLLAMA_MODEL", "qwen2.5:3b-instruct")
        self._explicit_base_url = base_url
        self.base_url = self._resolve_base_url(base_url)
        self.max_concurrency = max(
            1,
            int(max_concurrency or os.getenv("OLLAMA_CONCURRENCY", os.getenv("OLLAMA_NUM_PARALLEL", "1"))),
        )
        self._semaphore = threading.Semaphore(self.max_concurrency)
        self._last_health_check_time: float = 0.0
        self._cached_health: Optional[Dict[str, Any]] = None
        self._is_gpu: bool = False
        self._device_info: str = "CPU"
        self._backend_type: str = os.getenv("LLM_BACKEND", "auto")  # "auto", "ollama", "openai"

        self._ollama_sdk = ollama.Client(host=self.base_url) if (ollama and self._backend_type != "openai") else None

        if requests and HTTPAdapter:
            self._session = requests.Session()
            adapter = HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=0)
            self._session.mount("http://", adapter)
            self._session.mount("https://", adapter)
        else:
            self._session = None

    def _resolve_base_url(self, explicit_url: Optional[str] = None) -> str:
        """Determina la mejor URL para Ollama: si hay GPU activa en el host se usa host.docker.internal; de lo contrario, la red directa de contenedores http://ollama:11434."""
        if explicit_url:
            return explicit_url.rstrip("/")
        env_url = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434").rstrip("/")
        if env_url == "http://ollama:11434" and requests:
            host_candidate = "http://host.docker.internal:11434"
            try:
                ps_resp = requests.get(f"{host_candidate}/api/ps", timeout=0.5)
                if ps_resp.status_code == 200:
                    models = ps_resp.json().get("models", [])
                    if any(m.get("size_vram", 0) > 0 for m in models):
                        logger.info("Ollama en host físico con GPU activa detectado en %s.", host_candidate)
                        return host_candidate
            except Exception:
                pass
        return env_url

    def set_concurrency(self, concurrency: int) -> None:
        """Ajusta dinámicamente la cantidad de peticiones paralelas permitidas hacia Ollama."""
        # En CPU, concurrencia > 1 satura los núcleos y causa timeouts por contención de hilos
        if not getattr(self, "_is_gpu", False):
            self.max_concurrency = 1
        else:
            self.max_concurrency = max(1, int(concurrency))
        self._semaphore = threading.Semaphore(self.max_concurrency)
        logger.debug("Concurrencia de OllamaClient ajustada a %d slots simultáneos.", self.max_concurrency)

    def check_health(self, force: bool = False) -> Dict[str, Any]:
        """Verifica la conectividad con Ollama con caché rápida (15s), detectando aceleración GPU o CPU."""
        now = time.time()
        if not force and self._cached_health is not None and (now - self._last_health_check_time < 15.0):
            return self._cached_health

        try:
            http_client = self._session or requests

            if self._ollama_sdk:
                try:
                    resp = self._ollama_sdk.list()
                    models = [getattr(m, "model", "") or getattr(m, "name", "") for m in getattr(resp, "models", [])]
                    res = {
                        "online": True,
                        "models": models,
                        "default_model": self.default_model,
                        "default_model_installed": any(
                            self.default_model.split(":")[0] in m for m in models
                        ),
                        "device": self._device_info,
                        "is_gpu": self._is_gpu,
                        "base_url": self.base_url,
                        "max_concurrency": self.max_concurrency,
                    }
                    self._cached_health = res
                    self._last_health_check_time = now
                    return res
                except Exception as sdk_err:
                    logger.debug("Ollama SDK list falló, intentando requests: %s", sdk_err)

            resp = http_client.get(f"{self.base_url}/api/tags", timeout=2.5)
            if resp.status_code == 200:
                self._backend_type = "ollama"
                data = resp.json()
                models = [m.get("name") for m in data.get("models", [])]

                res = {
                    "online": True,
                    "backend": "ollama",
                    "models": models,
                    "default_model": self.default_model,
                    "default_model_installed": any(
                        self.default_model.split(":")[0] in m for m in models
                    ),
                    "device": self._device_info,
                    "is_gpu": self._is_gpu,
                    "base_url": self.base_url,
                    "max_concurrency": self.max_concurrency,
                }
                self._cached_health = res
                self._last_health_check_time = now
                return res

            # Si /api/tags retornó 404, verificar si se trata de un servidor compatible OpenAI (llama-server, vLLM)
            if resp.status_code == 404:
                try:
                    oa_resp = http_client.get(f"{self.base_url}/v1/models", timeout=2.5)
                    if oa_resp.status_code == 200:
                        self._backend_type = "openai"
                        oa_data = oa_resp.json()
                        models = [m.get("id") for m in oa_data.get("data", [])]
                        res = {
                            "online": True,
                            "backend": "openai",
                            "models": models,
                            "default_model": self.default_model,
                            "default_model_installed": True,
                            "device": self._device_info,
                            "is_gpu": self._is_gpu,
                            "base_url": self.base_url,
                            "max_concurrency": self.max_concurrency,
                        }
                        self._cached_health = res
                        self._last_health_check_time = now
                        return res
                except Exception:
                    pass

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

    def detect_acceleration(self) -> Dict[str, Any]:
        """Inspecciona en tiempo real si el modelo está acelerado por GPU o ejecutándose en CPU mediante /api/ps."""
        http_client = self._session or requests
        device = "CPU (Cuantizado)"
        is_gpu = False
        size_vram = 0
        try:
            ps_resp = http_client.get(f"{self.base_url}/api/ps", timeout=1.5)
            if ps_resp.status_code == 200:
                ps_data = ps_resp.json()
                for loaded in ps_data.get("models", []):
                    vram = loaded.get("size_vram", 0)
                    if vram > 0:
                        is_gpu = True
                        size_vram = max(size_vram, vram)
                if is_gpu:
                    device = f"GPU ({size_vram // (1024 * 1024)} MB VRAM)"
                else:
                    device = "CPU (Cuantizado)"
        except Exception:
            pass

        self._is_gpu = is_gpu
        self._device_info = device
        return {"device": device, "is_gpu": is_gpu, "size_vram": size_vram}

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        model: Optional[str] = None,
        format_json: bool = True,
        format_schema: Optional[Any] = None,
        temperature: float = 0.1,
        timeout: int = 300,
        num_predict: Optional[int] = None,
        num_ctx: Optional[int] = None,
    ) -> str:
        """
        Envía un prompt a Ollama y retorna la respuesta generada de forma sincronizada y thread-safe.
        Soporta formato JSON genérico ('format': 'json') o salidas estructuradas nativas
        restringidas por gramática llama.cpp pasando un JSON Schema ('format': {...}).
        Gestiona la concurrencia adaptable para GPU o CPU evitando cuellos de botella artificiales.
        """
        target_model = model or self.default_model
        num_pred = num_predict or (400 if (format_json or format_schema) else 512)
        ctx_size = num_ctx or (2048 if not (format_json or format_schema) else 4096)

        total_cpus = os.cpu_count() or 4
        if getattr(self, "_is_gpu", False):
            cpu_threads = max(2, min(total_cpus, 4))
        else:
            # En CPU repartir núcleos entre workers para evitar contención de memoria
            cpu_threads = max(2, min(total_cpus // max(1, self.max_concurrency), 6))

        is_openai = self._backend_type == "openai"
        if is_openai:
            endpoint = f"{self.base_url}/v1/chat/completions"
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            payload = {
                "model": target_model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": num_pred,
                "stream": False,
            }
            if format_json or format_schema:
                payload["response_format"] = {"type": "json_object"}
        else:
            endpoint = f"{self.base_url}/api/generate"
            payload = {
                "model": target_model,
                "prompt": prompt,
                "system": system_prompt,
                "stream": False,
                "keep_alive": "24h",
                "options": {
                    "temperature": temperature,
                    "top_p": 0.9,
                    "num_ctx": ctx_size,
                    "num_predict": num_pred,
                    "num_thread": cpu_threads,
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
            raise ConnectionError(f"Servidor LLM ({self._backend_type}) no está disponible en {self.base_url}")

        max_retries = 2
        backoff = 1.0

        # Si concurrencia == 1 usar _generation_lock para compatibilidad estricta.
        # Si concurrencia > 1 usar _semaphore para habilitar procesamiento paralelo.
        lock_ctx = OllamaClient._generation_lock if self.max_concurrency <= 1 else self._semaphore

        for attempt in range(1, max_retries + 1):
            try:
                with lock_ctx:
                    logger.debug(
                        "Llamando a LLM (%s, intento %d/%d, slot concurrente) con modelo '%s' (timeout=%ss, num_predict=%d, threads=%d)...",
                        self._backend_type,
                        attempt,
                        max_retries,
                        target_model,
                        timeout,
                        num_pred,
                        cpu_threads,
                    )
                    start_time = time.time()

                    if not is_openai and self._ollama_sdk:
                        try:
                            options = {
                                "temperature": temperature,
                                "top_p": 0.9,
                                "num_ctx": ctx_size,
                                "num_predict": num_pred,
                                "num_thread": cpu_threads,
                            }
                            gen_resp = self._ollama_sdk.generate(
                                model=target_model,
                                prompt=prompt,
                                system=system_prompt,
                                stream=False,
                                keep_alive="24h",
                                format=payload.get("format"),
                                options=options,
                            )
                            response_text = getattr(gen_resp, "response", "") or ""
                            response_text = response_text.strip()
                            elapsed = time.time() - start_time
                            logger.debug("Ollama SDK respondió en %.2f segundos (%d chars).", elapsed, len(response_text))
                            return response_text
                        except Exception as sdk_gen_err:
                            logger.debug("Ollama SDK generate falló (%s), intentando fallback HTTP...", sdk_gen_err)

                    http_client = self._session or requests
                    resp = http_client.post(endpoint, json=payload, timeout=timeout)
                    elapsed = time.time() - start_time

                    if resp.status_code == 200:
                        data = resp.json()
                        if is_openai:
                            choices = data.get("choices", [])
                            response_text = choices[0].get("message", {}).get("content", "").strip() if choices else ""
                        else:
                            response_text = data.get("response", "").strip()
                        logger.debug("Motor LLM (%s) respondió en %.2f segundos (%d chars).", self._backend_type, elapsed, len(response_text))
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
