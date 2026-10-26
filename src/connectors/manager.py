"""Gestor y orquestador central de todos los conectores de empleo con reporte de salud."""

import logging
from typing import Any, Dict, List, Tuple
from ..database import Database
from .base import JobOffer
from .infojobs_connector import InfoJobsConnector
from .jobspy_connector import JobSpyConnector
from .tecnoempleo_connector import TecnoempleoConnector

logger = logging.getLogger("lazyJobFinder.connectors.manager")


class ConnectorManager:
    """Orquesta la extracción multi-fuente, deduplicación temprana y seguimiento de salud de conectores."""

    def __init__(self, db: Database, settings: Dict[str, Any]):
        self.db = db
        self.settings = settings
        self.connectors = []
        self.source_health: Dict[str, Dict[str, Any]] = {}
        self._init_connectors()

    def _init_connectors(self) -> None:
        sources_cfg = self.settings.get("fuentes", {})

        # 1. Tecnoempleo RSS (Gratuito, abierto, sin claves)
        tecno_cfg = sources_cfg.get("tecnoempleo_rss", {})
        if tecno_cfg.get("habilitado", True):
            conn = TecnoempleoConnector(enabled=True)
            self.connectors.append(conn)
            self.source_health["tecnoempleo"] = {"status": "ready", "offers": 0, "error": None}

        # 2. InfoJobs API (Oficial REST)
        infojobs_cfg = sources_cfg.get("infojobs_api", {})
        if infojobs_cfg.get("habilitado", True):
            import os
            ij_id = infojobs_cfg.get("client_id") or os.getenv("INFOJOBS_CLIENT_ID", "").strip()
            ij_secret = infojobs_cfg.get("client_secret") or os.getenv("INFOJOBS_CLIENT_SECRET", "").strip()
            conn = InfoJobsConnector(client_id=ij_id, client_secret=ij_secret, enabled=True)
            self.connectors.append(conn)
            status_desc = "ready" if (conn.client_id and conn.client_secret) else "not_configured"
            self.source_health["infojobs"] = {"status": status_desc, "offers": 0, "error": None}

        # 3. JobSpy (Indeed, LinkedIn, Glassdoor, Google Jobs)
        jobspy_cfg = sources_cfg.get("jobspy", {})
        if jobspy_cfg.get("habilitado", True):
            sites = jobspy_cfg.get("sitios", ["indeed", "linkedin", "glassdoor", "google"])
            conn = JobSpyConnector(enabled=True, sites=sites)
            self.connectors.append(conn)
            for site in sites:
                self.source_health[f"jobspy_{site}"] = {"status": "ready", "offers": 0, "error": None}

        logger.info(
            "ConnectorManager inicializado con %d conectores activos.",
            len(self.connectors),
        )

    def reload_connectors(self) -> None:
        """Reinicializa los conectores para reflejar cambios en credenciales en caliente."""
        self.connectors = []
        self.source_health = {}
        self._init_connectors()

    def get_source_statuses(self) -> Dict[str, str]:
        """Devuelve un resumen legible del estado de cada fuente para Telegram y diagnóstico."""
        summary = {}
        for name, data in self.source_health.items():
            status = data.get("status", "unknown")
            offers = data.get("offers", 0)
            err = data.get("error")
            if status == "ok":
                summary[name] = f"🟢 OK ({offers} ofertas)"
            elif status == "not_configured":
                summary[name] = "⚪ No configurado (sin claves)"
            elif status == "error":
                summary[name] = f"🔴 Error ({err[:25]}...)" if err else "🔴 Error"
            else:
                summary[name] = f"🟡 {status}"
        return summary

    def run_discovery(self) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Ejecuta la búsqueda en todas las fuentes configuradas, deduplica y guarda las nuevas ofertas.
        Retorna la lista de ofertas nuevas insertadas en base de datos y un resumen de métricas.
        """
        # 1. Obtener CV activo y términos de búsqueda dinámicos adaptados (operación ultraligera O(1))
        from ..tailoring.cv_reader import get_active_cv_status
        cv_meta = get_active_cv_status()

        busqueda_cfg = self.settings.get("busqueda", {})
        if not cv_meta.get("has_cv"):
            logger.info("Sin CV activo seleccionado. Omitiendo escaneo en portales.")
            return [], {
                "total_encontradas": 0,
                "nuevas_guardadas": 0,
                "fuentes": {c.name: 0 for c in self.connectors},
            }

        active_terms = cv_meta.get("search_terms") or []
        if active_terms:
            raw_terms = active_terms
        else:
            raw_terms = busqueda_cfg.get("terminos") or []

        combined_terms: List[str] = []
        for t in raw_terms:
            clean_t = str(t).strip()
            if clean_t and clean_t.lower() not in [x.lower() for x in combined_terms]:
                combined_terms.append(clean_t)

        if not combined_terms:
            logger.info("El CV activo '%s' no tiene términos de búsqueda válidos. Omitiendo escaneo.", cv_meta.get("filename"))
            return [], {
                "total_encontradas": 0,
                "nuevas_guardadas": 0,
                "fuentes": {c.name: 0 for c in self.connectors},
            }

        # Mantener los 2 términos principales del CV y rotar/muestrear los términos secundarios
        # para que cada ciclo de búsqueda descubra ofertas distintas y no siempre las mismas
        import random
        if len(combined_terms) > 8:
            primary_terms = combined_terms[:2]
            secondary_terms = combined_terms[2:]
            random.shuffle(secondary_terms)
            search_terms = primary_terms + secondary_terms[:6]
        else:
            search_terms = list(combined_terms)

        logger.info(
            "Discovery utilizando términos adaptados al CV activo '%s' (%s): %s (de %d términos posibles)",
            cv_meta.get("filename"),
            cv_meta.get("primary_role", "perfil profesional"),
            search_terms,
            len(combined_terms),
        )
        print(f"\n[Escáner de Empleo] Buscando en portales ofertas para el CV '{cv_meta.get('filename')}': {search_terms}", flush=True)

        locations = busqueda_cfg.get("ubicaciones", ["Spain"])
        hours_old = busqueda_cfg.get("antiguedad_horas", 48)
        limit_per_source = busqueda_cfg.get("limite_por_fuente", 15)

        all_discovered: List[JobOffer] = []
        source_counts: Dict[str, int] = {}

        for connector in self.connectors:

            try:
                logger.info("Iniciando escaneo con conector '%s'...", connector.name)
                offers = connector.search(
                    search_terms=search_terms,
                    locations=locations,
                    hours_old=hours_old,
                    limit_per_search=limit_per_source,
                )
                source_counts[connector.name] = len(offers)
                all_discovered.extend(offers)

                if connector.name == "jobspy" and isinstance(connector, JobSpyConnector):
                    for site, site_stat in connector.site_status.items():
                        is_ok = "ok" in site_stat
                        self.source_health[f"jobspy_{site}"] = {
                            "status": "ok" if is_ok else "error",
                            "offers": len([o for o in offers if o.source == site]),
                            "error": site_stat if not is_ok else None,
                        }
                else:
                    health_entry = {
                        "status": "ok",
                        "offers": len(offers),
                        "error": None,
                    }
                    self.source_health[connector.name] = health_entry
                    if connector.name in ("tecnoempleo", "tecnoempleo_rss"):
                        self.source_health["tecnoempleo"] = health_entry
                        self.source_health["tecnoempleo_rss"] = health_entry

                self.db.log_event(
                    level="INFO",
                    source=connector.name,
                    message=f"Búsqueda finalizada con {len(offers)} ofertas.",
                )
            except Exception as e:
                logger.error("Error en conector '%s': %s", connector.name, e)
                self.source_health[connector.name] = {
                    "status": "error",
                    "offers": 0,
                    "error": str(e),
                }
                self.db.log_event(
                    level="ERROR",
                    source=connector.name,
                    message=f"Fallo durante la búsqueda: {str(e)}",
                )

        # Proceso de deduplicación e inserción en base de datos
        newly_inserted_jobs: List[Dict[str, Any]] = []
        duplicates_count = 0
        cross_portal_count = 0
        updated_count = 0

        active_cv_name = cv_meta.get("filename") if cv_meta.get("has_cv") else None

        for offer in all_discovered:
            offer_dict = offer.to_dict()
            if active_cv_name:
                offer_dict["cv_filename"] = active_cv_name
            job_id, status_code = self.db.save_job(offer_dict)

            if status_code == "inserted" and job_id:
                offer_dict["id"] = job_id
                newly_inserted_jobs.append(offer_dict)
            elif status_code == "cross_portal_duplicate":
                cross_portal_count += 1
                duplicates_count += 1
            elif status_code == "description_updated":
                updated_count += 1
            else:
                duplicates_count += 1

        logger.info(
            "Descubrimiento: %d encontradas | %d nuevas | %d duplicadas (%d entre portales) | %d actualizadas.",
            len(all_discovered),
            len(newly_inserted_jobs),
            duplicates_count,
            cross_portal_count,
            updated_count,
        )

        metrics = {
            "total_encontradas": len(all_discovered),
            "duplicadas": duplicates_count,
            "duplicadas_entre_portales": cross_portal_count,
            "actualizadas": updated_count,
            "nuevas_guardadas": len(newly_inserted_jobs),
            "por_fuente": source_counts,
            "estados_fuentes": self.get_source_statuses(),
        }

        return newly_inserted_jobs, metrics
