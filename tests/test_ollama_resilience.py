"""Pruebas de concurrencia, resiliencia y timeouts para el cliente Ollama en lazyJobFinder."""

import threading
import time
import unittest
from unittest.mock import MagicMock, patch

import requests

from src.evaluator.ollama_client import OllamaClient


class TestOllamaResilience(unittest.TestCase):
    def setUp(self):
        self.client = OllamaClient(base_url="http://localhost:11434", default_model="qwen2.5:3b-instruct")

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


if __name__ == "__main__":
    unittest.main()
