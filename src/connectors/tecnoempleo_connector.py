"""Conector para Tecnoempleo utilizando sus canales RSS oficiales y abiertos."""

import html
import logging
import re
import urllib.parse
from typing import List
import feedparser
import requests

from .base import BaseConnector, JobOffer

logger = logging.getLogger("lazyJobFinder.connectors.tecnoempleo")


def clean_html(raw_html: str) -> str:
    """Elimina etiquetas HTML y entidades para obtener texto plano limpio."""
    if not raw_html:
        return ""
    clean_text = re.sub(r"<[^>]+>", " ", raw_html)
    clean_text = html.unescape(clean_text)
    clean_text = re.sub(r"\s+", " ", clean_text)
    return clean_text.strip()


class TecnoempleoConnector(BaseConnector):
    """Conector que consume los canales RSS de tecnoempleo.com sin necesidad de API keys."""

    def __init__(self, enabled: bool = True):
        super().__init__(name="tecnoempleo_rss", enabled=enabled)
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        }

    def search(
        self,
        search_terms: List[str],
        locations: List[str],
        hours_old: int = 48,
        limit_per_search: int = 15,
    ) -> List[JobOffer]:
        if not self.enabled:
            logger.info("Conector Tecnoempleo RSS deshabilitado.")
            return []

        offers: List[JobOffer] = []
        seen_urls = set()

        # Tecnoempleo admite búsquedas por término y generación directa de RSS
        for term in search_terms:
            encoded_term = urllib.parse.quote_plus(term)
            rss_url = f"https://www.tecnoempleo.com/busqueda-empleo.php?te={encoded_term}&en=rss"

            try:
                logger.debug("Consultando RSS Tecnoempleo: %s", rss_url)
                resp = requests.get(rss_url, headers=self.headers, timeout=15)
                if resp.status_code != 200:
                    logger.warning(
                        "Tecnoempleo RSS retornó HTTP %d para término '%s'",
                        resp.status_code,
                        term,
                    )
                    continue

                feed = feedparser.parse(resp.content)
                if not feed.entries:
                    continue

                count = 0
                for entry in feed.entries:
                    link = entry.get("link", "").strip()
                    if not link or link in seen_urls:
                        continue

                    title = entry.get("title", "").strip()
                    raw_desc = entry.get("summary", "") or entry.get("description", "")
                    clean_desc = clean_html(raw_desc)

                    # Extracción heurística de empresa si viene en el título o descripción
                    company = "Tecnoempleo / Empresa IT"
                    if " en " in title:
                        parts = title.split(" en ")
                        if len(parts) >= 2:
                            company = parts[-1].split(" - ")[0].strip()

                    # Comprobar si es remoto
                    is_remote = any(
                        r in (title + " " + clean_desc).lower()
                        for r in ["teletrabajo", "remoto", "100% remoto", "remote"]
                    )

                    pub_date = entry.get("published", "") or entry.get("updated", "")

                    offer = JobOffer(
                        title=title,
                        company=company,
                        job_url=link,
                        source="tecnoempleo",
                        location="España",
                        is_remote=is_remote,
                        description=clean_desc,
                        date_posted=pub_date,
                        raw_data={"rss_id": entry.get("id", ""), "tags": entry.get("tags", [])},
                    )

                    offers.append(offer)
                    seen_urls.add(link)
                    count += 1
                    if count >= limit_per_search:
                        break

            except Exception as e:
                logger.warning("Error consultando Tecnoempleo RSS para '%s': %s", term, e)

        logger.info("Tecnoempleo RSS recuperó %d ofertas únicas.", len(offers))
        return offers
