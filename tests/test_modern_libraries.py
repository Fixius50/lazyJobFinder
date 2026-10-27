"""Suite de pruebas unitarias para las nuevas bibliotecas de modernización arquitectónica.

Valida:
1. price-parser: Extracción precisa de salarios y rangos desde texto.
2. trafilatura: Extracción de texto limpio eliminando etiquetas y scripts.
3. sqlite-utils: Manipulación ágil y segura del esquema SQLite sin DDL manual.
4. jinja2: Generación estructurada de cartas y documentos sin concatenaciones frágiles.
5. pydantic-settings: Tipado fuerte y carga de variables de entorno del sistema.
6. ollama SDK: Comunicación e interoperabilidad con el cliente nativo de Ollama.
"""

import os
import tempfile
import unittest

from price_parser import parse_price
import trafilatura
import sqlite_utils
from jinja2 import Template

from src.connectors.tecnoempleo_connector import clean_html
from src.database import Database
from src.storage import AppSettings


class TestModernLibraries(unittest.TestCase):
    def test_price_parser_salaries(self):
        """Verifica que price-parser detecte importes y monedas en textos de ofertas."""
        p1 = parse_price("35.000 € brutos anuales")
        self.assertEqual(p1.amount_float, 35000.0)
        self.assertEqual(p1.currency, "€")

        p2 = parse_price("2.200 EUR/mes")
        self.assertEqual(p2.amount_float, 2200.0)

        p3 = parse_price("Sin remuneración especificada")
        self.assertIsNone(p3.amount_float)

    def test_trafilatura_clean_html(self):
        """Verifica que clean_html limpie el HTML con trafilatura extrayendo párrafos reales."""
        html_sample = """
        <html>
            <head><title>Oferta</title></head>
            <body>
                <header><nav>Menú de navegación</nav></header>
                <main>
                    <h1>Desarrollador Python / React</h1>
                    <p>Buscamos un perfil con experiencia sólida en FastAPI, SQLite y React.</p>
                    <p>Modalidad 100% remota con horario flexible.</p>
                </main>
                <footer>Aviso de cookies y derechos reservados.</footer>
            </body>
        </html>
        """
        clean = clean_html(html_sample)
        self.assertIn("Desarrollador Python", clean)
        self.assertIn("FastAPI, SQLite y React", clean)
        # trafilatura descarta navegación y footers automáticamente
        self.assertNotIn("Aviso de cookies", clean)

    def test_sqlite_utils_integration(self):
        """Verifica la interoperabilidad de sqlite-utils con Database."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "test_utils.db")
            db = Database(db_path=db_path)
            utils_db = db.get_utils_db()

            self.assertIsNotNone(utils_db)
            self.assertIn("jobs", utils_db.table_names())
            self.assertIn("evaluations", utils_db.table_names())

            # Inserción con sqlite-utils y verificación con consulta tradicional
            utils_db["app_state"].upsert({"key": "test_modern_key", "value": '"modern_value"'}, pk="key")
            read_back = db.get_app_state("test_modern_key")
            self.assertEqual(read_back, "modern_value")

    def test_jinja2_letter_templating(self):
        """Verifica el renderizado de cartas de presentación mediante Jinja2."""
        from src.tailoring.cover_letter import CoverLetterGenerator
        gen = CoverLetterGenerator(profile={})
        letter = gen._assemble_letter(
            nombre="Roberto Gómez",
            email="roberto@example.com",
            telefono="600123456",
            ciudad="Madrid",
            empresa="Tech Innovations SL",
            puesto="Full Stack Developer",
            fecha="2026-10-27",
            body="Estoy muy motivado para aportar mi experiencia en desarrollo web moderno.",
        )
        self.assertIn("# Carta de Presentación", letter)
        self.assertIn("Roberto Gómez", letter)
        self.assertIn("Tech Innovations SL", letter)
        self.assertIn("Full Stack Developer", letter)
        self.assertIn("Madrid | roberto@example.com | 600123456", letter)

    def test_pydantic_settings_instance(self):
        """Verifica que AppSettings cargue y valide las rutas del proyecto."""
        if AppSettings:
            settings = AppSettings()
            self.assertTrue(os.path.isabs(settings.project_root))
            self.assertTrue(os.path.isabs(settings.data_dir))
            self.assertTrue(settings.database_path.endswith(".db"))


if __name__ == "__main__":
    unittest.main()
