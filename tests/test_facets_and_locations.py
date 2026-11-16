"""Pruebas unitarias para la extracción de ubicaciones y el retorno de facetas dinámicas."""

import os
import sqlite3
import tempfile
import unittest

from src.database import Database, extract_location_city


class TestFacetsAndLocations(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_facets.db")
        self.db = Database(self.db_path)
        self._populate_test_data()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _populate_test_data(self):
        with self.db._get_connection() as conn:
            sample_jobs = [
                ("Dev Python", "Empresa A", "Madrid, Community of Madrid, Spain", "CV_TEST.pdf"),
                ("Dev Java", "Empresa B", "Madrid, MD, Spain", "CV_TEST.pdf"),
                ("Dev Frontend", "Empresa C", "Greater Madrid Metropolitan Area", "CV_TEST.pdf"),
                ("Fullstack", "Empresa D", "Barcelona, Catalonia, Spain", "CV_TEST.pdf"),
                ("Backend", "Empresa E", "Greater Barcelona Metropolitan Area", "CV_TEST.pdf"),
                ("Data Engineer", "Empresa F", "Seville, Andalusia, Spain", "CV_TEST.pdf"),
                ("DevOps", "Empresa G", "A Coruña, Galicia, Spain", "CV_TEST.pdf"),
                ("QA", "Empresa H", "Greater La Coruña Area", "CV_TEST.pdf"),
                ("SysAdmin", "Empresa I", "Spain", "CV_TEST.pdf"),  # Genérica
            ]
            for idx, (title, comp, loc, cv) in enumerate(sample_jobs, start=1):
                conn.execute(
                    """
                    INSERT INTO jobs (
                        id, url_hash, content_fingerprint, canonical_url, title, company, location,
                        source, status, cv_filename, ui_saved, salary_min, salary_max, salary_currency
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'linkedin', 'discovered', ?, 1, 30000, 45000, 'EUR')
                    """,
                    (idx, f"hash_{idx}", f"fp_{idx}", f"https://example.com/job/{idx}", title, comp, loc, cv),
                )
            conn.commit()

    def test_extract_location_city(self):
        """Verifica la normalización de cadenas de ubicación en ciudades limpias."""
        self.assertEqual(extract_location_city("Madrid, Community of Madrid, Spain"), "Madrid")
        self.assertEqual(extract_location_city("Madrid, MD, Spain"), "Madrid")
        self.assertEqual(extract_location_city("Greater Madrid Metropolitan Area"), "Madrid")
        self.assertEqual(extract_location_city("Barcelona, Catalonia, Spain"), "Barcelona")
        self.assertEqual(extract_location_city("Greater Barcelona Metropolitan Area"), "Barcelona")
        self.assertEqual(extract_location_city("Seville, Andalusia, Spain"), "Sevilla")
        self.assertEqual(extract_location_city("Sevilla, AN, Spain"), "Sevilla")
        self.assertEqual(extract_location_city("A Coruña, Galicia, Spain"), "A Coruña")
        self.assertEqual(extract_location_city("Greater La Coruña Area"), "A Coruña")
        self.assertIsNone(extract_location_city("Spain"))
        self.assertIsNone(extract_location_city("MD, Spain"))
        self.assertIsNone(extract_location_city("En remoto, Spain"))
        self.assertIsNone(extract_location_city(""))
        self.assertIsNone(extract_location_city(None))

    def test_get_filter_facets_includes_top_locations(self):
        """Verifica que get_filter_facets devuelve top_locations, salary_stats y score_stats requeridos por la UI."""
        facets = self.db.get_filter_facets(cv_filename="CV_TEST.pdf")

        self.assertIn("top_locations", facets)
        self.assertIn("salary_stats", facets)
        self.assertIn("score_stats", facets)

        locations = facets["top_locations"]
        self.assertIsInstance(locations, list)
        self.assertGreater(len(locations), 0)

        # Verificar formato {name, count}
        for loc in locations:
            self.assertIn("name", loc)
            self.assertIn("count", loc)

        loc_map = {l["name"]: l["count"] for l in locations}
        # Madrid debe agrupar 3 ofertas
        self.assertEqual(loc_map.get("Madrid"), 3)
        # Barcelona debe agrupar 2 ofertas
        self.assertEqual(loc_map.get("Barcelona"), 2)
        # Sevilla debe agrupar 1 oferta
        self.assertEqual(loc_map.get("Sevilla"), 1)
        # A Coruña debe agrupar 2 ofertas
        self.assertEqual(loc_map.get("A Coruña"), 2)
        # "Spain" genérica no debe aparecer como ciudad
        self.assertNotIn("Spain", loc_map)

        # salary_stats
        self.assertEqual(facets["salary_stats"]["currency"], "€")
        self.assertEqual(facets["salary_stats"]["min"], 30000.0)
        self.assertEqual(facets["salary_stats"]["max"], 45000.0)

    def test_paginated_jobs_location_filtering(self):
        """Verifica que el filtrado por ubicación en get_jobs_paginated encuentra ofertas por ciudad y variantes."""
        res_madrid = self.db.get_jobs_paginated(location="Madrid", cv_filename="CV_TEST.pdf")
        self.assertEqual(res_madrid["total"], 3)

        res_bcn = self.db.get_jobs_paginated(location="Barcelona", cv_filename="CV_TEST.pdf")
        self.assertEqual(res_bcn["total"], 2)

        res_sevilla = self.db.get_jobs_paginated(location="Sevilla", cv_filename="CV_TEST.pdf")
        self.assertEqual(res_sevilla["total"], 1)

        res_coruna = self.db.get_jobs_paginated(location="A Coruña", cv_filename="CV_TEST.pdf")
        self.assertEqual(res_coruna["total"], 2)


if __name__ == "__main__":
    unittest.main()
