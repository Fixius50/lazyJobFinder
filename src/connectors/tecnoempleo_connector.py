"""Conector para Tecnoempleo mediante extracción HTML directa y canales RSS."""

from datetime import datetime
import html
import logging
import re
import urllib.parse
from typing import List
from bs4 import BeautifulSoup
import feedparser
import requests

from .base import BaseConnector, JobOffer

logger = logging.getLogger("lazyJobFinder.connectors.tecnoempleo")


def clean_html(raw_html: str) -> str:
    """Extrae texto plano limpio de contenidos HTML utilizando trafilatura con fallback robusto."""
    if not raw_html:
        return ""
    try:
        import trafilatura
        extracted = trafilatura.extract(raw_html, include_links=False, include_comments=False)
        if extracted and len(extracted.strip()) > 20:
            return extracted.strip()
    except Exception:
        pass
    clean_text = re.sub(r"<[^>]+>", " ", raw_html)
    clean_text = html.unescape(clean_text)
    clean_text = re.sub(r"\s+", " ", clean_text)
    return clean_text.strip()


class TecnoempleoConnector(BaseConnector):
    """Conector que extrae ofertas de tecnoempleo.com sin necesidad de API keys."""

    def __init__(self, enabled: bool = True):
        super().__init__(name="tecnoempleo_rss", enabled=enabled)
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        }

    def search(
        self,
        search_terms: List[str],
        locations: List[str],
        hours_old: int = 48,
        limit_per_search: int = 15,
    ) -> List[JobOffer]:
        if not self.enabled:
            logger.info("Conector Tecnoempleo deshabilitado.")
            return []

        offers: List[JobOffer] = []
        seen_urls = set()

        for term in search_terms:
            encoded_term = urllib.parse.quote_plus(term)
            search_url = f"https://www.tecnoempleo.com/busqueda-empleo.php?te={encoded_term}&ord=1"

            try:
                logger.debug("Consultando Tecnoempleo para '%s': %s", term, search_url)
                resp = requests.get(search_url, headers=self.headers, timeout=15)
                if resp.status_code != 200:
                    logger.warning(
                        "Tecnoempleo retornó HTTP %d para término '%s'",
                        resp.status_code,
                        term,
                    )
                    continue

                content_type = resp.headers.get("Content-Type", "").lower()
                term_count = 0

                def _check_match(location_str: str, remote_flag: bool, date_str: str) -> bool:
                    """Aplica filtros unificados de ubicación y antigüedad a ofertas de cualquier formato."""
                    if locations:
                        norm_locations = [l.strip().lower() for l in locations if l.strip()]
                        is_broad = any(b in norm_locations for b in ["spain", "españa", "espana"])
                        if not is_broad:
                            matched = any(
                                nl in location_str.lower() or (nl in ["remoto", "teletrabajo", "remote"] and remote_flag)
                                for nl in norm_locations
                            )
                            if not matched:
                                return False

                    if hours_old and hours_old > 0 and date_str and date_str not in ("Reciente", "Desconocida"):
                        dt = None
                        for fmt in (
                            "%Y-%m-%d",
                            "%d/%m/%Y",
                            "%Y-%m-%dT%H:%M:%S",
                            "%a, %d %b %Y %H:%M:%S %z",
                            "%a, %d %b %Y %H:%M:%S",
                        ):
                            try:
                                dt = datetime.strptime(date_str.split("+")[0].strip(), fmt)
                                break
                            except Exception:
                                continue
                        if dt:
                            diff_hours = (datetime.now() - dt.replace(tzinfo=None)).total_seconds() / 3600
                            if diff_hours > (hours_old + 24):
                                return False

                    return True

                # 1. Intento por XML/RSS si la respuesta es feed
                if "xml" in content_type or resp.text.strip().startswith("<?xml"):
                    feed = feedparser.parse(resp.content)
                    for entry in feed.entries:
                        link = entry.get("link", "").strip()
                        if not link or link in seen_urls:
                            continue
                        title = entry.get("title", "").strip()
                        raw_desc = entry.get("summary", "") or entry.get("description", "")
                        clean_desc = clean_html(raw_desc)
                        company = "Tecnoempleo / Empresa IT"
                        if " en " in title:
                            parts = title.split(" en ")
                            if len(parts) >= 2:
                                company = parts[-1].split(" - ")[0].strip()
                        is_remote = any(
                            r in (title + " " + clean_desc).lower()
                            for r in ["teletrabajo", "remoto", "100% remoto", "remote", "hibrido"]
                        )
                        raw_pub = entry.get("published", "") or entry.get("updated", "")
                        pub_date = "Desconocida"
                        if raw_pub:
                            try:
                                if hasattr(entry, "published_parsed") and entry.published_parsed:
                                    pub_date = datetime(*entry.published_parsed[:6]).strftime("%Y-%m-%d")
                                else:
                                    pub_date = str(raw_pub)[:10]
                            except Exception:
                                pub_date = str(raw_pub)[:10]

                        loc = "España"
                        if not _check_match(loc, is_remote, pub_date):
                            continue

                        offers.append(
                            JobOffer(
                                title=title,
                                company=company,
                                job_url=link,
                                source="tecnoempleo",
                                location=loc,
                                is_remote=is_remote,
                                description=clean_desc,
                                date_posted=pub_date,
                                raw_data={"source": "rss"},
                            )
                        )
                        seen_urls.add(link)
                        term_count += 1
                        if term_count >= limit_per_search:
                            break

                # 2. Extracción directa del HTML con BeautifulSoup
                if term_count == 0:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    cards = soup.find_all("div", class_=lambda c: c and "border" in c and "rounded" in c)

                    for card in cards:
                        a_title = card.find("a", href=lambda h: h and "/rf-" in h)
                        if not a_title:
                            continue

                        link = a_title.get("href", "").strip()
                        if not link:
                            continue
                        if link.startswith("/"):
                            link = f"https://www.tecnoempleo.com{link}"

                        if link in seen_urls:
                            continue

                        title = a_title.text.strip()

                        a_comp = card.find("a", href=lambda h: h and "/re-" in h)
                        company = a_comp.text.strip() if a_comp else "Empresa IT"

                        # Localización y modalidad
                        spans = card.find_all("span")
                        span_texts = [s.text.strip() for s in spans if s.text.strip()]
                        combined_text = f"{title} {' '.join(span_texts)}".lower()

                        loc = "España"
                        for s in spans:
                            b = s.find("b")
                            if b and b.text.strip() and "urgente" not in b.text.lower():
                                loc = b.text.strip()
                                break

                        is_remote = any(
                            r in combined_text
                            for r in ["teletrabajo", "remoto", "100% remoto", "remote", "híbrido", "hibrido"]
                        )

                        # Extracción de fecha real del card (ej: "19/10/2026")
                        pub_date = "Desconocida"
                        date_match = re.search(r"(\d{1,2}/\d{1,2}/\d{4})", card.text)
                        if date_match:
                            try:
                                dt = datetime.strptime(date_match.group(1), "%d/%m/%Y")
                                pub_date = dt.strftime("%Y-%m-%d")
                            except Exception:
                                pass

                        if not _check_match(loc, is_remote, pub_date):
                            continue

                        desc_elem = card.find("span", class_=lambda cl: cl and "hidden-md-down" in cl)
                        desc = desc_elem.text.strip() if desc_elem else " ".join(span_texts[:3])
                        # Extraer tipo de contrato, jornada y formación de las etiquetas del card
                        contract_type = None
                        schedule = None
                        education_level = None
                        for st in span_texts:
                            stl = st.lower()
                            if "indefinid" in stl:
                                contract_type = "Indefinido"
                            elif "temporal" in stl:
                                contract_type = "Temporal"
                            elif "práctica" in stl or "practica" in stl or "beca" in stl:
                                contract_type = "Prácticas / Beca"
                            elif "freelance" in stl or "autónom" in stl:
                                contract_type = "Autónomo / Freelance"

                            if "completa" in stl or "full-time" in stl:
                                schedule = "Jornada Completa"
                            elif "parcial" in stl or "media jornada" in stl or "part-time" in stl:
                                schedule = "Media Jornada"
                            elif "flexible" in stl:
                                schedule = "Horario Flexible"

                            if any(k in stl for k in ["grado", "ingenier", "universit"]):
                                education_level = "Grado / Universidad"
                            elif any(k in stl for k in ["fp", "ciclo", "módulo", "formación profesional"]):
                                education_level = "FP / Ciclo Formativo"
                            elif any(k in stl for k in ["master", "máster", "postgrado"]):
                                education_level = "Máster / Postgrado"

                        offer = JobOffer(
                            title=title,
                            company=company,
                            job_url=link,
                            source="tecnoempleo",
                            location=loc,
                            is_remote=is_remote,
                            description=desc or f"Oferta de {title} en {company} ({loc})",
                            date_posted=pub_date,
                            contract_type=contract_type,
                            schedule=schedule,
                            education_level=education_level,
                            raw_data={"source": "html_scraper"},
                        )

                        offers.append(offer)
                        seen_urls.add(link)
                        term_count += 1
                        if term_count >= limit_per_search:
                            break

            except Exception as e:
                logger.warning("Error consultando Tecnoempleo para '%s': %s", term, e)

        logger.info("Tecnoempleo recuperó %d ofertas únicas.", len(offers))
        return offers
