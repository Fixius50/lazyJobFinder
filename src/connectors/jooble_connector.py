"""Conector para el metabuscador y agregador global Jooble mediante su API REST oficial."""

import html
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
import requests

from .base import BaseConnector, JobOffer

logger = logging.getLogger("lazyJobFinder.connectors.jooble")


def _clean_snippet(raw_snippet: str) -> str:
    """Limpia etiquetas HTML, secuencias de escape y espacios sobrantes del resumen de Jooble."""
    if not raw_snippet:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw_snippet)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


class JoobleConnector(BaseConnector):
    """
    Conector que consulta el agregador Jooble (metabuscador multi-sitio que indexa miles
    de bolsas de empleo, páginas de empresas y ETTs como Randstad o Adecco).
    Utiliza la API REST oficial mediante solicitudes HTTP POST con carga JSON.
    """

    BASE_URL = "https://jooble.org/api"

    def __init__(
        self,
        api_key: Optional[str] = None,
        enabled: bool = True,
    ):
        super().__init__(name="jooble", enabled=enabled)
        self.api_key = (api_key or os.getenv("JOOBLE_API_KEY", "")).strip()

    def search(
        self,
        search_terms: List[str],
        locations: List[str],
        hours_old: int = 48,
        limit_per_search: int = 15,
    ) -> List[JobOffer]:
        if not self.enabled:
            logger.info("Conector Jooble deshabilitado en configuración.")
            return []

        if not self.api_key:
            logger.info(
                "Jooble API no configurada (JOOBLE_API_KEY no definida). "
                "Para activarla de forma gratuita, obtén una clave en https://jooble.org/api/about"
            )
            return []

        offers: List[JobOffer] = []
        seen_urls = set()
        primary_location = locations[0] if locations else "Spain"
        endpoint = f"{self.BASE_URL}/{self.api_key}"

        for term in search_terms:
            try:
                payload: Dict[str, Any] = {
                    "keywords": term,
                    "location": primary_location,
                    "page": 1,
                    "resultOnPage": min(max(5, limit_per_search), 50),
                }

                logger.debug("Consultando Jooble API para '%s' en '%s'", term, primary_location)
                response = requests.post(
                    endpoint,
                    json=payload,
                    headers={"Content-Type": "application/json", "Accept": "application/json"},
                    timeout=15,
                )

                if response.status_code in (401, 403):
                    logger.warning("Clave de Jooble API no válida o denegada (HTTP %d).", response.status_code)
                    break
                elif response.status_code != 200:
                    logger.warning("Jooble API respondió con código HTTP %d para '%s'.", response.status_code, term)
                    continue

                data = response.json()
                jobs = data.get("jobs", [])
                logger.debug("Jooble API retornó %d ofertas para '%s'.", len(jobs), term)

                for item in jobs:
                    job_url = str(item.get("link") or "").strip()
                    if not job_url or job_url in seen_urls:
                        continue

                    title = str(item.get("title") or "").strip()
                    company = str(item.get("company") or "").strip() or "Empresa Confidencial"
                    loc = str(item.get("location") or primary_location).strip()
                    snippet = _clean_snippet(str(item.get("snippet") or ""))
                    original_source = str(item.get("source") or "jooble").strip()

                    # Extracción de salario si está disponible
                    salary_str = str(item.get("salary") or "").strip()
                    salary_min = None
                    salary_max = None
                    if salary_str:
                        try:
                            from price_parser import parse_price
                            # Buscar rangos como "20.000 - 30.000 €"
                            nums = re.findall(r"([0-9.,]+)", salary_str.replace(" ", ""))
                            if nums:
                                p1 = parse_price(nums[0])
                                if p1.amount_float and 500 < p1.amount_float < 300000:
                                    salary_min = float(p1.amount_float)
                                if len(nums) > 1:
                                    p2 = parse_price(nums[1])
                                    if p2.amount_float and 500 < p2.amount_float < 300000:
                                        salary_max = float(p2.amount_float)
                        except Exception:
                            pass

                    # Detección de jornada o contrato
                    job_type_raw = str(item.get("type") or "").strip().lower()
                    schedule = None
                    contract_type = None
                    if "completa" in job_type_raw or "full" in job_type_raw:
                        schedule = "Jornada Completa"
                    elif "parcial" in job_type_raw or "part" in job_type_raw or "media" in job_type_raw:
                        schedule = "Media Jornada"

                    if "indefinido" in job_type_raw or "fijo" in job_type_raw or "permanent" in job_type_raw:
                        contract_type = "Indefinido"
                    elif "temporal" in job_type_raw or "prácticas" in job_type_raw or "beca" in job_type_raw:
                        contract_type = "Temporal"

                    # Detección de teletrabajo en ubicación o texto
                    is_remote = any(
                        r in loc.lower() or r in title.lower() or r in snippet.lower()
                        for r in ("remoto", "teletrabajo", "remote", "desde casa")
                    )

                    date_posted = None
                    updated_val = item.get("updated")
                    if updated_val:
                        try:
                            date_posted = str(updated_val).split("T")[0]
                        except Exception:
                            date_posted = datetime.now().strftime("%Y-%m-%d")

                    offer = JobOffer(
                        title=title,
                        company=company,
                        job_url=job_url,
                        source="jooble",
                        location=loc,
                        is_remote=is_remote,
                        description=snippet,
                        salary_min=salary_min,
                        salary_max=salary_max,
                        salary_currency="EUR",
                        date_posted=date_posted,
                        contract_type=contract_type,
                        schedule=schedule,
                        raw_data={
                            "jooble_id": item.get("id"),
                            "original_source": original_source,
                            "salary_raw": salary_str,
                        },
                    )
                    offers.append(offer)
                    seen_urls.add(job_url)

            except Exception as e:
                logger.warning("Error en petición a Jooble API para '%s': %s", term, e)

        logger.info("Jooble API recuperó %d ofertas únicas.", len(offers))
        return offers

