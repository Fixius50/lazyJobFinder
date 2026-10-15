"""Conector para la API REST oficial de InfoJobs (developer.infojobs.net)."""

import logging
import os
from typing import List, Optional
import requests
from requests.auth import HTTPBasicAuth

from .base import BaseConnector, JobOffer

logger = logging.getLogger("lazyJobFinder.connectors.infojobs")


class InfoJobsConnector(BaseConnector):
    """Conector que utiliza la API REST oficial de InfoJobs con Basic Auth."""

    BASE_URL = "https://api.infojobs.net/api/9/offer"

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        enabled: bool = True,
    ):
        super().__init__(name="infojobs_api", enabled=enabled)
        self.client_id = client_id or os.getenv("INFOJOBS_CLIENT_ID", "").strip()
        self.client_secret = client_secret or os.getenv("INFOJOBS_CLIENT_SECRET", "").strip()

    def search(
        self,
        search_terms: List[str],
        locations: List[str],
        hours_old: int = 48,
        limit_per_search: int = 15,
    ) -> List[JobOffer]:
        if not self.enabled:
            logger.info("Conector InfoJobs API deshabilitado en configuración.")
            return []

        if not self.client_id or not self.client_secret:
            logger.info(
                "InfoJobs API no configurada (INFOJOBS_CLIENT_ID / SECRET no definidos). "
                "Se omitirá esta fuente sin interrumpir el resto."
            )
            return []

        offers: List[JobOffer] = []
        seen_urls = set()
        auth = HTTPBasicAuth(self.client_id, self.client_secret)
        headers = {"Accept": "application/json"}

        for term in search_terms:
            try:
                params = {
                    "q": term,
                    "maxResults": min(limit_per_search, 20),
                    "order": "updated",
                }

                logger.debug("Consultando InfoJobs API para término '%s'", term)
                response = requests.get(
                    self.BASE_URL,
                    headers=headers,
                    params=params,
                    auth=auth,
                    timeout=15,
                )

                if response.status_code == 401 or response.status_code == 403:
                    logger.warning(
                        "Credenciales de InfoJobs API no válidas o denegadas (HTTP %d). "
                        "Verifica INFOJOBS_CLIENT_ID y CLIENT_SECRET.",
                        response.status_code,
                    )
                    break

                if response.status_code != 200:
                    logger.warning(
                        "InfoJobs API retornó HTTP %d: %s",
                        response.status_code,
                        response.text[:200],
                    )
                    continue

                data = response.json()
                raw_offers = data.get("offers", [])

                for item in raw_offers:
                    link = item.get("link", "").strip()
                    if not link or link in seen_urls:
                        continue

                    title = item.get("title", "").strip()
                    author_info = item.get("author", {})
                    company = author_info.get("name", "Empresa en InfoJobs") if author_info else "Empresa"
                    province_info = item.get("province", {})
                    province = province_info.get("value", "España") if province_info else "España"
                    teleworking = item.get("teleworking", {})
                    teleworking_val = teleworking.get("value", "").lower() if teleworking else ""
                    is_remote = any(r in teleworking_val for r in ["remoto", "teletrabajo"])

                    req_min = item.get("requirementMin", "")
                    desc = item.get("description", "") or req_min
                    full_desc = f"{req_min}\n\n{desc}".strip()

                    salary_min = None
                    salary_max = None
                    if "salaryMin" in item and isinstance(item["salaryMin"], dict):
                        salary_min = item["salaryMin"].get("value")
                    if "salaryMax" in item and isinstance(item["salaryMax"], dict):
                        salary_max = item["salaryMax"].get("value")

                    offer = JobOffer(
                        title=title,
                        company=company,
                        job_url=link,
                        source="infojobs",
                        location=province,
                        is_remote=is_remote,
                        description=full_desc,
                        salary_min=float(salary_min) if salary_min else None,
                        salary_max=float(salary_max) if salary_max else None,
                        salary_currency="EUR",
                        date_posted=item.get("published", ""),
                        raw_data=item,
                    )

                    offers.append(offer)
                    seen_urls.add(link)

            except Exception as e:
                logger.warning("Error en InfoJobs API para '%s': %s", term, e)

        logger.info("InfoJobs API recuperó %d ofertas únicas.", len(offers))
        return offers
