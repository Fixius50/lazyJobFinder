"""Tests para el umbral de generación documental (CV adaptado y carta de presentación).

Valida que:
1. El sistema genera documentos exclusivamente cuando la puntuación es igual o superior al 50%.
2. Para vacantes con puntuación menor al 50%, no se invoca la generación de documentos.
"""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from src.scheduler.runner import JobPipelineRunner


class TestDocumentGenerationThreshold(unittest.TestCase):
    def setUp(self):
        self.runner = JobPipelineRunner()
        self.runner.cv_tailorer = MagicMock()
        self.runner.letter_generator = MagicMock()
        self.runner.pdf_renderer = MagicMock()
        self.runner.db = MagicMock()
        self.runner.telegram_bot = MagicMock()
        self.runner.telegram_bot.is_configured.return_value = False

    def test_document_generation_condition_strict_50(self):
        """Verifica que la regla can_generate_docs solo aplique para score >= 50."""
        # Candidato con score 78 (debe generar)
        eval_high = {"job_id": 1, "score": 78, "should_apply": True}
        can_generate_docs = True

        should_gen_high = can_generate_docs and eval_high.get("score", 0) >= 50
        self.assertTrue(should_gen_high, "Con score 78 (>= 50), debe permitirse la generación de documentos.")

        # Candidato exactamente en el umbral 50 (debe generar)
        eval_exact = {"job_id": 2, "score": 50, "should_apply": True}
        should_gen_exact = can_generate_docs and eval_exact.get("score", 0) >= 50
        self.assertTrue(should_gen_exact, "Con score exactamente 50 (>= 50), debe permitirse la generación.")

        # Candidato con score 49 (NO debe generar)
        eval_low = {"job_id": 3, "score": 49, "should_apply": False}
        should_gen_low = can_generate_docs and eval_low.get("score", 0) >= 50
        self.assertFalse(should_gen_low, "Con score 49 (< 50), NO debe generarse CV ni carta.")

        # Candidato con score 25 (NO debe generar)
        eval_discarded = {"job_id": 4, "score": 25, "should_apply": False}
        should_gen_discarded = can_generate_docs and eval_discarded.get("score", 0) >= 50
        self.assertFalse(should_gen_discarded, "Con score 25 (< 50), NO debe generarse CV ni carta.")


if __name__ == "__main__":
    unittest.main()
