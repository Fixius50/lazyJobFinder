"""Pruebas unitarias para las columnas booleanas de provider_settings y el conector Jooble."""

import os
import sqlite3
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from src.connectors.base import BaseConnector, JobOffer
from src.connectors.jooble_connector import JoobleConnector, _clean_snippet


class TestProviderSettingsAndJooble(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_settings.db")
        self._init_mock_db(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _init_mock_db(self, path: str):
        conn = sqlite3.connect(path)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS provider_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                enable_infojobs INTEGER NOT NULL DEFAULT 0,
                enable_tecnoempleo INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT DEFAULT (datetime('now', 'localtime'))
            );
            """
        )
        conn.execute("INSERT OR IGNORE INTO provider_settings (id, enable_infojobs, enable_tecnoempleo) VALUES (1, 0, 0);")
        conn.commit()
        conn.close()

    def test_provider_settings_columns_exist_and_default_to_zero(self):
        """Verifica que las 2 columnas booleanas existen en provider_settings con valor por defecto 0 (desactivadas)."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(provider_settings);")
        cols = {row["name"]: row["type"] for row in cur.fetchall()}
        self.assertIn("enable_infojobs", cols)
        self.assertIn("enable_tecnoempleo", cols)

        cur.execute("SELECT enable_infojobs, enable_tecnoempleo FROM provider_settings WHERE id = 1;")
        row = cur.fetchone()
        self.assertEqual(row["enable_infojobs"], 0)
        self.assertEqual(row["enable_tecnoempleo"], 0)
        conn.close()

    def test_provider_settings_update(self):
        """Verifica la actualización de las 2 columnas booleanas en la base de datos."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            INSERT INTO provider_settings (id, enable_infojobs, enable_tecnoempleo, updated_at)
            VALUES (1, 1, 1, datetime('now', 'localtime'))
            ON CONFLICT(id) DO UPDATE SET
                enable_infojobs = excluded.enable_infojobs,
                enable_tecnoempleo = excluded.enable_tecnoempleo,
                updated_at = excluded.updated_at;
            """
        )
        conn.commit()

        cur = conn.cursor()
        cur.execute("SELECT enable_infojobs, enable_tecnoempleo FROM provider_settings WHERE id = 1;")
        row = cur.fetchone()
        self.assertEqual(row["enable_infojobs"], 1)
        self.assertEqual(row["enable_tecnoempleo"], 1)
        conn.close()

    def test_clean_snippet(self):
        """Verifica la limpieza de etiquetas HTML en los resúmenes de Jooble."""
        raw = "Buscamos <b>Desarrollador Python</b> &amp; Django para empresa &lt;top&gt;."
        clean = _clean_snippet(raw)
        self.assertEqual(clean, "Buscamos Desarrollador Python & Django para empresa <top>.")

    @patch("requests.post")
    def test_jooble_connector_search(self, mock_post):
        """Verifica la normalización de ofertas recibidas desde la API REST de Jooble."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "totalCount": 1,
            "jobs": [
                {
                    "id": 998877,
                    "title": "Ingeniero de Software",
                    "company": "Randstad Empleo ETT",
                    "location": "Madrid, España",
                    "snippet": "Puesto estable con teletrabajo y 30.000 € brutos.",
                    "salary": "28.000 - 32.000 €",
                    "source": "randstad.es",
                    "type": "Jornada completa / Indefinido",
                    "link": "https://es.jooble.org/jdp/998877",
                    "updated": "2026-11-13T10:00:00.0000000",
                }
            ],
        }
        mock_post.return_value = mock_response

        connector = JoobleConnector(api_key="test_api_key_123", enabled=True)
        offers = connector.search(search_terms=["Software"], locations=["Madrid"])

        self.assertEqual(len(offers), 1)
        offer = offers[0]
        self.assertEqual(offer.title, "Ingeniero de Software")
        self.assertEqual(offer.company, "Randstad Empleo ETT")
        self.assertEqual(offer.source, "jooble")
        self.assertEqual(offer.job_url, "https://es.jooble.org/jdp/998877")
        self.assertTrue(offer.is_remote)
        self.assertEqual(offer.schedule, "Jornada Completa")
        self.assertEqual(offer.contract_type, "Indefinido")
        self.assertEqual(offer.raw_data.get("original_source"), "randstad.es")


if __name__ == "__main__":
    unittest.main()

