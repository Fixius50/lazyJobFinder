"""Gestor de migraciones no destructivas y transaccionales para SQLite en lazyJobFinder.

Diseñado con salvaguardas operativas de nivel de producción:
1. Copia de respaldo recuperable (.bak) previa a cualquier alteración de esquema.
2. Ejecución estrictamente transaccional (BEGIN IMMEDIATE ... COMMIT / ROLLBACK).
3. Inspección PRAGMA table_info idempotente que jamás borra tablas ni datos.
4. Reversión limpia en caso de error sin dejar estados inconsistentes en user_version.
"""

import logging
import os
import shutil
import sqlite3
from datetime import datetime
from typing import List, Optional, Set

logger = logging.getLogger("lazyJobFinder.migrations")


class DatabaseMigrator:
    """Aplica migraciones incrementales no destructivas con respaldo previo y transacciones atómicas."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def get_existing_columns(self, table_name: str, conn: Optional[sqlite3.Connection] = None) -> Set[str]:
        """Devuelve los nombres de las columnas existentes en una tabla mediante PRAGMA table_info."""
        if conn is not None:
            cursor = conn.execute(f"PRAGMA table_info({table_name});")
            return {row["name"] for row in cursor.fetchall()}
        with self._get_connection() as c:
            cursor = c.execute(f"PRAGMA table_info({table_name});")
            return {row["name"] for row in cursor.fetchall()}

    def get_user_version(self) -> int:
        """Obtiene la versión actual del esquema registrada en PRAGMA user_version."""
        with self._get_connection() as conn:
            cursor = conn.execute("PRAGMA user_version;")
            row = cursor.fetchone()
            return int(row[0]) if row else 0

    def create_pre_migration_backup(self, current_version: int) -> Optional[str]:
        """
        Crea una copia de seguridad recuperable previa a cualquier alteración.
        Ejecuta un checkpoint de WAL previo para asegurar la consistencia del archivo principal.
        """
        if not os.path.exists(self.db_path) or os.path.getsize(self.db_path) == 0:
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{self.db_path}.backup_v{current_version}_{timestamp}.bak"

        try:
            # Checkpoint para sincronizar páginas WAL pendientes al archivo .db
            with self._get_connection() as conn:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")

            shutil.copy2(self.db_path, backup_path)
            logger.info("Respaldo pre-migración creado exitosamente en: %s", backup_path)
            return backup_path
        except Exception as e:
            logger.error("Fallo al crear copia de respaldo pre-migración: %s", e)
            raise RuntimeError(f"Abortando migración: no se pudo garantizar la copia de seguridad: {e}")

    def run_migrations_safely(self) -> List[str]:
        """
        Ejecuta de forma secuencial, transaccional y no destructiva las migraciones pendientes.
        Garantiza que un fallo restaure el estado previo y no corrompa user_version.
        """
        applied = []
        current_version = self.get_user_version()
        logger.info("Versión de esquema SQLite detectada: v%d", current_version)

        # Si ya está en la versión deseada (v3), no hay cambios pendientes
        if current_version >= 3:
            return applied

        # 1. Crear respaldo recuperable antes de cualquier modificación
        backup_file = self.create_pre_migration_backup(current_version)

        # 2. Migración v1 -> v2: Deduplicación fuzzy y trazabilidad entre portales
        if current_version < 2:
            conn = self._get_connection()
            try:
                # Transacción inmediata para evitar escrituras concurrentes durante la alteración
                conn.execute("BEGIN IMMEDIATE;")
                
                existing_cols = self.get_existing_columns("jobs", conn=conn)

                # Columna duplicate_of_id
                if "duplicate_of_id" not in existing_cols:
                    logger.info("Migración v2: Añadiendo columna 'duplicate_of_id' a 'jobs'...")
                    conn.execute(
                        "ALTER TABLE jobs ADD COLUMN duplicate_of_id INTEGER REFERENCES jobs(id) ON DELETE SET NULL;"
                    )

                # Columna similarity_score
                if "similarity_score" not in existing_cols:
                    logger.info("Migración v2: Añadiendo columna 'similarity_score' a 'jobs'...")
                    conn.execute("ALTER TABLE jobs ADD COLUMN similarity_score REAL;")

                # Columna alternate_sources
                if "alternate_sources" not in existing_cols:
                    logger.info("Migración v2: Añadiendo columna 'alternate_sources' a 'jobs'...")
                    conn.execute("ALTER TABLE jobs ADD COLUMN alternate_sources TEXT DEFAULT '[]';")

                # Índice para acelerar búsquedas canónicas y evitar scans secuenciales
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_jobs_duplicate_of ON jobs(duplicate_of_id);"
                )

                # Actualizar versión de esquema dentro del bloque transaccional
                conn.execute("PRAGMA user_version = 2;")
                conn.commit()

                applied.append("v2_fuzzy_dedup_and_tracking")
                logger.info("Migración v2 completada y confirmada (COMMIT) con éxito.")
                current_version = 2

            except Exception as e:
                conn.rollback()
                logger.critical("Error crítico en migración v2: %s. Ejecutado ROLLBACK.", e, exc_info=True)
                if backup_file and os.path.exists(backup_file):
                    logger.warning("Restaurando base de datos desde respaldo previo: %s", backup_file)
                    conn.close()
                    shutil.copy2(backup_file, self.db_path)
                raise e
            finally:
                conn.close()

        # 3. Migración v2 -> v3: Canales de notificación independientes (UI y Telegram)
        if current_version < 3:
            conn = self._get_connection()
            try:
                conn.execute("BEGIN IMMEDIATE;")
                existing_cols = self.get_existing_columns("jobs", conn=conn)

                # Columna telegram_notified (0 = pendiente/omitido, 1 = enviado con éxito, -1 = fallido)
                if "telegram_notified" not in existing_cols:
                    logger.info("Migración v3: Añadiendo columna 'telegram_notified' a 'jobs'...")
                    conn.execute("ALTER TABLE jobs ADD COLUMN telegram_notified INTEGER DEFAULT 0;")

                # Columna ui_saved (1 = activo en interfaz de administración, 0 = oculto/descartado)
                if "ui_saved" not in existing_cols:
                    logger.info("Migración v3: Añadiendo columna 'ui_saved' a 'jobs'...")
                    conn.execute("ALTER TABLE jobs ADD COLUMN ui_saved INTEGER DEFAULT 1;")

                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_jobs_notification_channels ON jobs(telegram_notified, ui_saved);"
                )

                conn.execute("PRAGMA user_version = 3;")
                conn.commit()

                applied.append("v3_notification_channels")
                logger.info("Migración v3 completada y confirmada (COMMIT) con éxito.")

            except Exception as e:
                conn.rollback()
                logger.critical("Error crítico en migración v3: %s. Ejecutado ROLLBACK.", e, exc_info=True)
                if backup_file and os.path.exists(backup_file):
                    logger.warning("Restaurando base de datos desde respaldo previo: %s", backup_file)
                    conn.close()
                    shutil.copy2(backup_file, self.db_path)
                raise e
            finally:
                conn.close()

        return applied
