"""Pruebas de inicialización única y persistencia de estado para Database y Storage."""

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from src.database import Database
import src.storage as storage


class TestDatabaseSingleton(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_lifecycle.db")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_database_init_db_runs_only_once_per_path(self):
        """Verifica que instanciar Database varias veces solo invoque init_db una vez."""
        orig_init = Database.init_db
        call_count = 0

        def counting_init(db_self, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            return orig_init(db_self, *args, **kwargs)

        with patch.object(Database, "init_db", counting_init):
            db1 = Database(db_path=self.db_path)
            self.assertTrue(os.path.exists(self.db_path))

            # Segunda y tercera instanciación con la misma ruta
            db2 = Database(db_path=self.db_path)
            db3 = Database(db_path=self.db_path)

            # Debe haber ejecutado init_db únicamente 1 vez
            self.assertEqual(call_count, 1)

    def test_storage_get_storage_db_caches_instance(self):
        """Verifica que _get_storage_db en storage.py reutilice la misma instancia."""
        with storage._storage_db_lock:
            storage._storage_db = None

        inst1 = storage._get_storage_db()
        inst2 = storage._get_storage_db()
        self.assertIs(inst1, inst2, "storage._get_storage_db debe retornar exactamente la misma instancia singleton")


if __name__ == "__main__":
    unittest.main()
