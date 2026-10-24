"""Conector modular con aislamiento de fallos por portal para JobSpy (Indeed, LinkedIn, Glassdoor, Google Jobs)."""

import logging
import random
import time
from typing import Dict, List, Tuple

from .base import BaseConnector, JobOffer

logger = logging.getLogger("lazyJobFinder.connectors.jobspy")


class JobSpyConnector(BaseConnector):
    """
    Conector unificado que ejecuta cada bolsa de empleo de JobSpy de forma completamente
    independiente, asegurando que el bloqueo o fallo de un portal (ej. LinkedIn rate-limit)
    no impida extraer ofertas de los demás (Indeed, Glassdoor, Google Jobs).
    """

    def __init__(self, enabled: bool = True, sites: List[str] = None):
        super().__init__(name="jobspy", enabled=enabled)
        self.sites = sites or ["indeed", "linkedin", "glassdoor", "google"]
        self.site_status: Dict[str, str] = {s: "untested" for s in self.sites}

    def search(
        self,
        search_terms: List[str],
        locations: List[str],
        hours_old: int = 48,
        limit_per_search: int = 15,
    ) -> List[JobOffer]:
        if not self.enabled:
            logger.info("Conector JobSpy deshabilitado en configuración.")
            return []

        try:
            from jobspy import scrape_jobs
        except ImportError:
            logger.error("Librería 'python-jobspy' no instalada.")
            self.site_status = {s: "missing_library" for s in self.sites}
            return []

        offers: List[JobOffer] = []
        seen_urls = set()
        primary_location = locations[0] if locations else "Remote"

        # AISLAMIENTO ESTRICTO POR PORTAL:
        # Cada portal se consulta por separado para aislar fallos de red o rate-limits
        for site in self.sites:
            site_offers_count = 0
            site_error = None

            for term in search_terms:
                try:
                    logger.debug("JobSpy consultando portal '%s' para término '%s'...", site, term)
                    # Pausa preventiva con jitter aleatorio para reducir la probabilidad de bloqueo anti-bot
                    time.sleep(random.uniform(1.8, 3.2))

                    kwargs = {
                        "site_name": [site],
                        "search_term": term,
                        "location": primary_location,
                        "results_wanted": min(limit_per_search, 15),
                        "hours_old": hours_old,
                    }
                    if site == "indeed":
                        loc_low = primary_location.lower()
                        if any(k in loc_low for k in ("spain", "españa", "madrid", "barcelona", "valencia")):
                            kwargs["country_indeed"] = "spain"
                        elif any(k in loc_low for k in ("uk", "united kingdom", "london", "londres", "manchester")):
                            kwargs["country_indeed"] = "uk"
                        elif any(k in loc_low for k in ("germany", "deutschland", "berlin", "munich")):
                            kwargs["country_indeed"] = "germany"
                        elif any(k in loc_low for k in ("france", "paris")):
                            kwargs["country_indeed"] = "france"
                        elif any(k in loc_low for k in ("canada", "toronto", "vancouver")):
                            kwargs["country_indeed"] = "canada"
                        else:
                            kwargs["country_indeed"] = "usa"

                    jobs_df = scrape_jobs(**kwargs)

                    if jobs_df is not None and not jobs_df.empty:
                        for _, row in jobs_df.iterrows():
                            job_url = str(row.get("job_url") or "").strip()
                            if not job_url or job_url in seen_urls:
                                continue

                            title = str(row.get("title") or "").strip()
                            company = str(row.get("company") or "").strip() or "Empresa Confidencial"
                            loc = str(row.get("location") or primary_location).strip()
                            is_remote = bool(row.get("is_remote")) if "is_remote" in row else False
                            desc = str(row.get("description") or "").strip()
                            date_posted = str(row.get("date_posted") or "")

                            salary_min = None
                            salary_max = None
                            try:
                                if row.get("min_amount") is not None and not str(row.get("min_amount")).lower() == "nan":
                                    salary_min = float(row.get("min_amount"))
                                if row.get("max_amount") is not None and not str(row.get("max_amount")).lower() == "nan":
                                    salary_max = float(row.get("max_amount"))
                            except Exception:
                                pass

                            raw_job_type = str(row.get("job_type") or "").strip()
                            if raw_job_type.lower() == "nan":
                                raw_job_type = ""
                            contract_type = None
                            schedule = None
                            if raw_job_type:
                                jt_lower = raw_job_type.lower()
                                if "fulltime" in jt_lower or "full_time" in jt_lower:
                                    schedule = "Jornada Completa"
                                elif "parttime" in jt_lower or "part_time" in jt_lower:
                                    schedule = "Media Jornada"
                                if "contract" in jt_lower:
                                    contract_type = "Contrato Temporal"
                                elif "internship" in jt_lower:
                                    contract_type = "Prácticas / Beca"
                                elif "fulltime" in jt_lower or "permanent" in jt_lower:
                                    contract_type = "Indefinido"

                            offer = JobOffer(
                                title=title,
                                company=company,
                                job_url=job_url,
                                source=f"{site}",
                                location=loc,
                                is_remote=is_remote,
                                description=desc,
                                salary_min=salary_min,
                                salary_max=salary_max,
                                salary_currency=str(row.get("currency") or "EUR"),
                                date_posted=date_posted,
                                contract_type=contract_type,
                                schedule=schedule,
                                raw_data={"portal": site, "job_type": raw_job_type},
                            )

                            offers.append(offer)
                            seen_urls.add(job_url)
                            site_offers_count += 1

                except Exception as e:
                    site_error = str(e)
                    logger.warning("Fallo en portal '%s' de JobSpy para término '%s': %s", site, term, e)

            # Registrar el estado individual del portal
            if site_error:
                self.site_status[site] = f"error: {site_error[:40]}"
            else:
                self.site_status[site] = f"ok ({site_offers_count} ofertas)"

        logger.info(
            "JobSpy finalizó con %d ofertas totales. Estado de portales: %s",
            len(offers),
            self.site_status,
        )
        return offers
