"""Modelos de datos y clase base abstracta para los conectores de empleo."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class JobOffer:
    """Representación normalizada y canónica de una oferta de empleo."""

    title: str
    company: str
    job_url: str
    source: str
    location: str = "España"
    is_remote: bool = False
    description: str = ""
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: str = "EUR"
    date_posted: Optional[str] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convierte la oferta a diccionario compatible con la base de datos."""
        return {
            "title": self.title.strip(),
            "company": self.company.strip() or "Empresa Confidencial",
            "job_url": self.job_url.strip(),
            "source": self.source.strip().lower(),
            "location": self.location.strip() or "España",
            "is_remote": 1 if self.is_remote else 0,
            "description": self.description.strip(),
            "salary_min": self.salary_min,
            "salary_max": self.salary_max,
            "salary_currency": self.salary_currency,
            "date_posted": self.date_posted or datetime.now().strftime("%Y-%m-%d"),
        }


class BaseConnector(ABC):
    """Clase base que deben implementar todos los conectores de empleo."""

    def __init__(self, name: str, enabled: bool = True):
        self.name = name
        self.enabled = enabled

    @abstractmethod
    def search(
        self,
        search_terms: List[str],
        locations: List[str],
        hours_old: int = 48,
        limit_per_search: int = 15,
    ) -> List[JobOffer]:
        """Ejecuta la búsqueda de ofertas y devuelve una lista normalizada."""
        pass
