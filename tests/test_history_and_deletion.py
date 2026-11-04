"""Pruebas unitarias para el vaciado de historial y eliminación de ofertas en SQLite."""

import os
import tempfile
import unittest

from src.database import Database


class TestHistoryAndDeletion(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_history.db")
        self.db = Database(db_path=self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_clear_applications_history_and_rediscovery(self):
        """Verifica que vaciar historial limpie SQLite y permita revalorar la oferta al reencontrarla."""
        sample_job = {
            "job_url": "https://ejemplo.com/oferta-1",
            "title": "Desarrollador Python Senior",
            "company": "Tech Solutions",
            "location": "Madrid",
            "description": "Buscamos desarrollador Python con experiencia.",
            "source": "indeed",
            "status": "evaluated",
        }

        # 1. Insertar oferta inicial
        job_id, status = self.db.save_job(sample_job)
        self.assertEqual(status, "inserted")
        self.assertIsNotNone(job_id)

        # 2. Registrar evaluación
        self.db.save_evaluation({
            "job_id": job_id,
            "score": 85,
            "fit_level": "ALTO",
            "matched_skills": ["Python"],
            "missing_skills": [],
            "strengths": ["Python"],
            "gaps": [],
            "reasoning": "Buen encaje",
            "should_apply": True,
        })

        # 3. Intentar guardar de nuevo antes de limpiar: debe ser already_exists
        dup_id, dup_status = self.db.save_job(sample_job)
        self.assertEqual(dup_status, "already_exists")

        # 4. Limpiar historial
        stats = self.db.clear_applications_history()
        self.assertEqual(stats["jobs_deleted"], 1)
        self.assertEqual(stats["evaluations_deleted"], 1)

        # Comprobar que las tablas quedaron vacías
        with self.db._get_connection() as conn:
            jobs_count = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
            evals_count = conn.execute("SELECT COUNT(*) FROM evaluations").fetchone()[0]
            self.assertEqual(jobs_count, 0)
            self.assertEqual(evals_count, 0)

        # 5. Volver a encontrar la oferta: debe tratarse como nueva (inserted) para revalorar
        new_id, new_status = self.db.save_job(sample_job)
        self.assertEqual(new_status, "inserted")
        self.assertIsNotNone(new_id)

    def test_delete_individual_job_and_rediscovery(self):
        """Verifica que eliminar una oferta específica la retire de jobs y evaluations permitiendo revalorarla."""
        sample_job = {
            "job_url": "https://ejemplo.com/oferta-2",
            "title": "Ingeniero Cloud AWS",
            "company": "CloudCorp",
            "location": "Remoto",
            "description": "Especialista AWS.",
            "source": "linkedin",
        }

        job_id, status = self.db.save_job(sample_job)
        self.assertEqual(status, "inserted")

        self.db.save_evaluation({
            "job_id": job_id,
            "score": 40,
            "fit_level": "BAJO",
            "matched_skills": [],
            "missing_skills": ["AWS"],
            "strengths": [],
            "gaps": ["AWS"],
            "reasoning": "Falta AWS",
            "should_apply": False,
        })

        # Eliminar la oferta individualmente
        deleted = self.db.delete_job(job_id)
        self.assertTrue(deleted)

        # Comprobar que no queda ni la oferta ni la evaluación
        with self.db._get_connection() as conn:
            job_row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            eval_row = conn.execute("SELECT * FROM evaluations WHERE job_id = ?", (job_id,)).fetchone()
            self.assertIsNone(job_row)
            self.assertIsNone(eval_row)

        # Volver a guardarla: debe volver a insertarse limpiamente
        re_id, re_status = self.db.save_job(sample_job)
        self.assertEqual(re_status, "inserted")

