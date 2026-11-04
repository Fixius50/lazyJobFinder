"""Pruebas de concurrencia, resiliencia y timeouts para el cliente Ollama en lazyJobFinder."""

import threading
import time
import unittest
from unittest.mock import MagicMock, patch

import requests

from src.evaluator.ollama_client import OllamaClient


class TestOllamaResilience(unittest.TestCase):
    def setUp(self):
        self.client = OllamaClient(base_url="http://localhost:11434", default_model="qwen2.5:3b-instruct", max_concurrency=1)

    def test_health_check_caching(self):
        """Verifica que check_health utilice caché rápida para no sobrecargar el endpoint."""
        with patch.object(self.client, "_session") as mock_session:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"models": [{"name": "qwen2.5:3b-instruct"}]}
            mock_session.get.return_value = mock_resp

            res1 = self.client.check_health()
            self.assertTrue(res1["online"])
            self.assertEqual(mock_session.get.call_count, 1)

            # Llamada inmediata: debe retornar desde caché sin volver a consultar
            res2 = self.client.check_health()
            self.assertTrue(res2["online"])
            self.assertEqual(mock_session.get.call_count, 1)

    def test_generation_lock_serializes_concurrent_calls(self):
        """Verifica que el cerrojo _generation_lock evite que múltiples hilos compitan en Ollama CPU."""
        execution_order = []

        def mock_post(*args, **kwargs):
            thread_name = threading.current_thread().name
            execution_order.append(f"{thread_name}_start")
            time.sleep(0.05)
            execution_order.append(f"{thread_name}_end")
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"response": "OK"}
            return mock_resp

        with patch.object(self.client, "check_health", return_value={"online": True}):
            with patch.object(self.client, "_session") as mock_session:
                mock_session.post.side_effect = mock_post

                t1 = threading.Thread(target=self.client.generate, args=("prompt 1",), name="T1")
                t2 = threading.Thread(target=self.client.generate, args=("prompt 2",), name="T2")

                t1.start()
                t2.start()
                t1.join()
                t2.join()

                # La ejecución debe ser estrictamente secuencial gracias a _generation_lock:
                # [T1_start, T1_end, T2_start, T2_end] o [T2_start, T2_end, T1_start, T1_end]
                # En ningún caso los dos _start pueden ser consecutivos
                self.assertEqual(len(execution_order), 4)
                self.assertIn(execution_order[0].replace("_start", "_end"), execution_order[1])

    def test_concurrency_allows_parallel_calls_when_configured(self):
        """Verifica que al configurar concurrencia > 1 (GPU o multi-slot), múltiples hilos puedan ejecutarse simultáneamente."""
        client_parallel = OllamaClient(base_url="http://localhost:11434", max_concurrency=2)
        execution_order = []
        barrier = threading.Barrier(2)

        def mock_post(*args, **kwargs):
            thread_name = threading.current_thread().name
            execution_order.append(f"{thread_name}_start")
            # Ambos hilos alcanzan la barrera dentro de la ejecución concurrente
            try:
                barrier.wait(timeout=1.0)
            except threading.BrokenBarrierError:
                pass
            execution_order.append(f"{thread_name}_end")
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"response": "OK"}
            return mock_resp

        with patch.object(client_parallel, "check_health", return_value={"online": True}):
            with patch.object(client_parallel, "_session") as mock_session:
                mock_session.post.side_effect = mock_post

                t1 = threading.Thread(target=client_parallel.generate, args=("prompt 1",), name="T1")
                t2 = threading.Thread(target=client_parallel.generate, args=("prompt 2",), name="T2")

                t1.start()
                t2.start()
                t1.join()
                t2.join()

                # Con concurrencia=2, ambos hilos inician antes de que el primero termine:
                # Los dos primeros eventos deben ser _start
                starts = [e for e in execution_order if "_start" in e]
                self.assertEqual(len(starts), 2)
                self.assertIn(execution_order[0], ["T1_start", "T2_start"])
                self.assertIn(execution_order[1], ["T1_start", "T2_start"])

    def test_generate_respects_custom_num_predict_and_timeout(self):
        """Verifica que el payload transmita num_predict y timeout configurados."""
        captured_payload = {}
        captured_timeout = None

        def mock_post(endpoint, json=None, timeout=None):
            nonlocal captured_payload, captured_timeout
            captured_payload = json
            captured_timeout = timeout
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"response": "Resumen adaptado"}
            return mock_resp

        with patch.object(self.client, "check_health", return_value={"online": True}):
            with patch.object(self.client, "_session") as mock_session:
                mock_session.post.side_effect = mock_post

                res = self.client.generate(
                    prompt="Resumen para CV",
                    format_json=False,
                    timeout=95,
                    num_predict=140,
                )
                self.assertEqual(res, "Resumen adaptado")
                self.assertEqual(captured_timeout, 95)
                self.assertEqual(captured_payload["options"]["num_predict"], 140)

    def test_model_not_found_raises_file_not_found_immediately(self):
        """HTTP 404 debe levantar FileNotFoundError sin realizar reintentos inútiles."""
        with patch.object(self.client, "check_health", return_value={"online": True}):
            with patch.object(self.client, "_session") as mock_session:
                mock_resp = MagicMock()
                mock_resp.status_code = 404
                mock_resp.text = "model 'fake:model' not found"
                mock_session.post.return_value = mock_resp

                with self.assertRaises(FileNotFoundError):
                    self.client.generate(prompt="test", model="fake:model")

    def test_check_health_detects_gpu_device(self):
        """Verifica que detect_acceleration determine la presencia de GPU a través de /api/ps."""
        with patch.object(self.client, "_session") as mock_session:
            resp_ps = MagicMock(status_code=200)
            resp_ps.json.return_value = {
                "models": [{"name": "qwen2.5:3b-instruct", "size_vram": 2366226432}]
            }
            mock_session.get.return_value = resp_ps

            accel = self.client.detect_acceleration()
            self.assertTrue(accel["is_gpu"])
            self.assertIn("GPU", accel["device"])
            self.assertEqual(accel["size_vram"], 2366226432)

    def test_openai_compatible_endpoint_generate(self):
        """Verifica la compatibilidad dual con servidores OpenAI/llama.cpp (/v1/chat/completions)."""
        client_openai = OllamaClient(base_url="http://localhost:8080", max_concurrency=1)
        client_openai._backend_type = "openai"

        with patch.object(client_openai, "check_health", return_value={"online": True}):
            with patch.object(client_openai, "_session") as mock_session:
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.json.return_value = {
                    "choices": [{"message": {"content": '{"apto": true, "puntuacion": 95}'}}]
                }
                mock_session.post.return_value = mock_resp

                res = client_openai.generate(prompt="Evalúa esta oferta", system_prompt="Eres un evaluador", format_json=True)
                self.assertIn("95", res)
                # Verificar que llamó a /v1/chat/completions con formato OpenAI
                call_args = mock_session.post.call_args
                self.assertIn("/v1/chat/completions", call_args[0][0])
                self.assertEqual(call_args[1]["json"]["response_format"], {"type": "json_object"})


if __name__ == "__main__":
    unittest.main()
