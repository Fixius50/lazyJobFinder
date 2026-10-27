"""Pruebas de resiliencia y tolerancia a fallos para el bot de Telegram de lazyJobFinder."""

import asyncio
import logging
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from telegram.error import NetworkError, TimedOut, TelegramError
from telegram.request import HTTPXRequest

from src.telegram_bot.bot import TelegramJobBot, TelegramNetworkFilter


class TestTelegramResilience(unittest.TestCase):
    def setUp(self):
        self.mock_db = MagicMock()
        self.settings = {
            "notificaciones": {
                "telegram": {
                    "bot_token": "999999999:AAFakeValidMockTokenForResilienceTestXYZ",
                    "allowed_user_id": 5978474268,
                }
            }
        }
        self.bot = TelegramJobBot(
            db=self.mock_db,
            settings=self.settings,
        )

    def test_telegram_network_filter_suppresses_traceback(self):
        """Verifica que el filtro de red elimine el traceback ruidoso de errores transitorios."""
        filt = TelegramNetworkFilter()
        record = logging.LogRecord(
            name="telegram.ext._utils.networkloop",
            level=logging.ERROR,
            pathname="networkloop.py",
            lineno=100,
            msg="Error while getting Updates",
            args=(),
            exc_info=(NetworkError, NetworkError("httpx.ConnectError: [Errno -2] Name or service not known"), None),
        )
        self.assertTrue(filt.filter(record))
        self.assertIsNone(record.exc_info, "exc_info debe ser limpiado para evitar trazas gigantes en consola")
        self.assertEqual(record.levelno, logging.WARNING, "El nivel debe reducirse a WARNING")
        self.assertIn("Aviso de conectividad en Telegram", record.msg)

    def test_on_error_handles_transient_network_error(self):
        """Verifica que _on_error capture NetworkError y TimedOut sin propagar excepción."""
        context = MagicMock()
        context.error = NetworkError("httpx.ConnectError: Name or service not known")

        loop = asyncio.new_event_loop()
        try:
            # No debe lanzar excepción
            loop.run_until_complete(self.bot._on_error(update=None, context=context))
        finally:
            loop.close()

    def test_build_application_configures_httpx_request(self):
        """Verifica que build_application configure HTTPXRequest con timeouts y pool robustos."""
        with patch.object(self.bot, "is_configured", return_value=True), patch("src.telegram_bot.bot.ApplicationBuilder") as mock_builder_cls:
            mock_builder = MagicMock()
            mock_builder_cls.return_value = mock_builder
            mock_builder.token.return_value = mock_builder
            mock_builder.request.return_value = mock_builder
            mock_app = MagicMock()
            mock_builder.build.return_value = mock_app

            app = self.bot.build_application()
            self.assertIsNotNone(app)
            # Verificar que se llamó con request HTTPXRequest
            mock_builder.request.assert_called_once()
            called_request = mock_builder.request.call_args[0][0]
            self.assertIsInstance(called_request, HTTPXRequest)
            mock_app.add_error_handler.assert_called_once()


if __name__ == "__main__":
    unittest.main()
