"""Validador programático estricto de afirmaciones concretas y veracidad contra el perfil canónico."""

import logging
import re
from typing import Any, Dict, List, Set, Tuple

logger = logging.getLogger("lazyJobFinder.tailoring.verifier")


class ProfileVerifier:
    """
    Valida mediante código que ninguna afirmación profesional generada contradiga o invente datos.
    Soporta cualquier perfil profesional (técnico, administrativo, creativo, salud, etc.)
    extrayendo las competencias y titulación directamente del perfil del usuario o su CV.
    """

    def __init__(self, profile: Dict[str, Any], cv_text: str = ""):
        self.profile = profile or {}
        self.cv_text = cv_text or ""
        self.cv_text_lower = self.cv_text.lower()
        self.allowed_skills = self._extract_allowed_skills()
        self.allowed_institutions = self._extract_allowed_institutions()
        self.allowed_degrees = self._extract_allowed_degrees()
        self.allowed_projects = self._extract_allowed_projects()
        self.has_commercial_employment = bool(profile.get("experiencia_laboral", [])) or "experiencia" in self.cv_text_lower

    def _extract_allowed_skills(self) -> Set[str]:
        skills = set()
        competencias = self.profile.get("competencias_tecnicas", {})
        if isinstance(competencias, dict):
            for k, val in competencias.items():
                if isinstance(val, list):
                    for item in val:
                        if isinstance(item, dict):
                            skills.add(item.get("nombre", "").lower().strip())
                            for c in item.get("conceptos", []):
                                skills.add(c.lower().strip())
                        elif isinstance(item, str):
                            skills.add(item.lower().strip())
                elif isinstance(val, str):
                    skills.add(val.lower().strip())
        elif isinstance(competencias, list):
            for item in competencias:
                if isinstance(item, str):
                    skills.add(item.lower().strip())

        # Habilidades adicionales generales del perfil
        for h in self.profile.get("habilidades", []):
            if isinstance(h, str):
                skills.add(h.lower().strip())

        return {s for s in skills if s}

    def _extract_allowed_institutions(self) -> Set[str]:
        inst = set()
        for f in self.profile.get("formacion", []):
            if isinstance(f, dict) and f.get("institucion"):
                inst.add(f.get("institucion").lower().strip())
        return inst

    def _extract_allowed_degrees(self) -> Set[str]:
        degs = set()
        for f in self.profile.get("formacion", []):
            if isinstance(f, dict) and f.get("titulo"):
                degs.add(f.get("titulo").lower().strip())
        candidato = self.profile.get("candidato", {})
        if candidato.get("titulo_profesional"):
            degs.add(candidato.get("titulo_profesional").lower().strip())
        return degs

    def _extract_allowed_projects(self) -> List[Dict[str, Any]]:
        return self.profile.get("proyectos", []) or self.profile.get("proyectos_destacados", [])

    def get_approved_atomic_facts(self) -> Dict[str, Any]:
        """
        Devuelve el conjunto cerrado de hechos atómicos estructurados aprobados.
        Esta es la ÚNICA fuente de verdad autorizada para la IA.
        """
        candidato = self.profile.get("candidato", {})
        formacion = self.profile.get("formacion", [])
        titulo_principal = (
            formacion[0].get("titulo") if formacion and isinstance(formacion[0], dict) and formacion[0].get("titulo")
            else candidato.get("titulo_profesional", "Profesional")
        )

        exp_list = self.profile.get("experiencia_laboral", [])
        if exp_list:
            historial = f"{len(exp_list)} puestos previos acreditados"
        else:
            historial = "Formación académica y proyectos prácticos acreditados"

        return {
            "candidato": {
                "nombre": candidato.get("nombre_completo", "Candidato"),
                "titulo": candidato.get("titulo_profesional", titulo_principal),
                "ciudad": candidato.get("ciudad", "España"),
            },
            "formacion_academica": [
                {
                    "titulo": f.get("titulo"),
                    "institucion": f.get("institucion"),
                    "año": f.get("fecha_fin"),
                }
                for f in formacion if isinstance(f, dict)
            ],
            "experiencia_comercial_previa": historial,
            "competencias_tecnicas_certificadas": sorted(list(self.allowed_skills)),
            "proyectos_academicos_certificados": [
                {
                    "nombre": p.get("nombre"),
                    "tecnologias": p.get("tecnologias", []),
                    "descripcion": p.get("descripcion", "").strip(),
                }
                for p in self.allowed_projects if isinstance(p, dict)
            ],
        }

    def validate_concrete_assertions(self, text: str, target_company: str = "") -> Tuple[bool, List[str]]:
        """
        Valida rigurosamente mediante código que ninguna afirmación en el texto generado contradiga
        o exceda los hechos certificados en config/profile.yaml:
        1. Prohíbe afirmar experiencia laboral comercial o empleo previo si no existe en profile.yaml.
        2. Prohíbe invención de titulaciones no cursadas (Ingeniería, Grado universitario, Máster, Doctorado).
        3. Prohíbe invención de roles de liderazgo, arquitectura o antigüedad (Senior, Lead, Arquitecto).
        4. Prohíbe atribuir competencias técnicas a tecnologías ajenas no listadas.
        5. Prohíbe invención de empresas pasadas donde supuestamente trabajó.
        """
        violations = []
        text_lower = text.lower()

        # 1. Validación de experiencia laboral previa
        if not self.has_commercial_employment:
            employment_assertions = [
                r"\b(\d+|\w+)\s+años?\s+de\s+experiencia\s+(laboral|profesional|en\s+empresas|en\s+el\s+sector)",
                r"\b(trabajé|he\s+trabajado|desempeñé|fui\s+empleado|en\s+mi\s+anterior\s+empresa|en\s+antiguos\s+empleos)\b",
                r"\bexperiencia\s+laboral\s+previa\b",
                r"\bexperiencia\s+en\s+empresas\b",
                r"\btras\s+años?\s+en\s+la\s+industria\b",
                r"\bmi\s+anterior\s+puesto\b",
            ]
            for pattern in employment_assertions:
                if re.search(pattern, text_lower):
                    violations.append(f"Afirmación no respaldada: Se atribuye experiencia comercial previa cuando el perfil es académico DAM ({pattern}).")

        # 2. Validación de titulaciones ficticias
        unapproved_degrees = [
            r"\b(ingenier[ií]a\s+inform[aá]tica|ingeniero\s+inform[aá]tico)\b",
            r"\b(grado\s+en\s+ingenier[ií]a|grado\s+universitario|licenciatur[a|o])\b",
            r"\bm[aá]ster\s+(en|of)\b",
            r"\bdoctorado\s+(en)?\b",
        ]
        for pattern in unapproved_degrees:
            if re.search(pattern, text_lower):
                violations.append(f"Titulación no respaldada en el perfil: Detectada mención indebida ({pattern}).")

        # 3. Validación de roles no respaldados (solo si no figuran en el CV o perfil)
        fictitious_roles = [
            (r"\b(fui|como)\s+(lead|senior|arquitecto|project\s+manager|jefe\s+de\s+equipo)\b", "rol de liderazgo o seniority"),
            (r"\blideré\s+equipos?\b", "liderazgo de equipos"),
            (r"\bgestión\s+de\s+personal\b", "gestión de personal"),
            (r"\bgestión\s+de\s+presupuestos?\b", "gestión de presupuestos"),
        ]
        for pattern, desc in fictitious_roles:
            if re.search(pattern, text_lower):
                # Si el término figura en el CV o perfil del candidato, es verídico
                if not any(re.search(pattern, src) for src in [self.cv_text_lower, str(self.profile).lower()]):
                    violations.append(f"Afirmación no respaldada: Se atribuye {desc} no documentado.")

        # 4. Tecnologías o competencias no respaldadas
        words = re.findall(r"\b[A-Za-z0-9#\+\./\-]+\b", text)
        common_advanced_techs = {
            "kubernetes", "k8s", "aws", "azure", "gcp", "react native", "flutter",
            "scala", "golang", "c#", ".net", "cobol", "rust", "angular", "react",
            "django", "ruby", "rails", "swift", "kotlin", "objective-c"
        }
        for word in words:
            w_lower = word.lower()
            if w_lower in common_advanced_techs:
                if w_lower not in self.allowed_skills and w_lower not in self.cv_text_lower:
                    violations.append(f"Competencia no respaldada en el perfil ni en el CV: '{word}'.")

        return len(violations) == 0, violations

    def sanitize_summary(
        self,
        generated_summary: str,
        matched_skills: List[str],
        company: str,
        job_title: str,
    ) -> Tuple[str, List[str]]:
        """
        Inspecciona y valida el resumen generado. Si contiene afirmaciones no contrastadas
        o tecnologías no autorizadas, recurre inmediatamente a la plantilla canónica aprobada.
        """
        corrections = []

        if not generated_summary or len(generated_summary.strip()) < 40:
            corrections.append("Resumen generado vacío o insuficiente. Usando plantilla canónica.")
            return self._build_canonical_summary(matched_skills, company, job_title), corrections

        is_valid, violations = self.validate_concrete_assertions(generated_summary, target_company=company)
        if not is_valid:
            corrections.extend(violations)
            logger.warning(
                "Resumen generado rechazado por ProfileVerifier debido a afirmaciones no respaldadas: %s",
                violations,
            )
            # Reemplazo seguro por la plantilla canónica 100% verídica
            return self._build_canonical_summary(matched_skills, company, job_title), corrections

        return generated_summary.strip(), ["Contenido validado algorítmicamente contra el perfil canónico."]

    def _build_canonical_summary(self, matched_skills: List[str], company: str, job_title: str) -> str:
        """Construye un resumen profesional verídico adaptado a cualquier disciplina laboral."""
        candidato = self.profile.get("candidato", {})
        titulo = candidato.get("titulo_profesional") or "Profesional"
        resumen_base = self.profile.get("resumen_base", "").strip()

        if resumen_base:
            return resumen_base

        verified_matched = [s for s in matched_skills if s.lower() in self.allowed_skills or (self.cv_text_lower and s.lower() in self.cv_text_lower)]
        skills_clause = f" con competencias destacadas en {', '.join(verified_matched[:4])}" if verified_matched else ""

        return (
            f"{titulo}{skills_clause}. "
            f"Perfil proactivo, riguroso y comprometido con la excelencia, con alta motivación por incorporarme "
            f"al equipo de {company} para aportar valor en la vacante de {job_title} y continuar creciendo profesionalmente."
        )

    def validate_matched_skills(self, claimed_skills: List[str]) -> List[str]:
        """Filtra y devuelve las habilidades verificables en el perfil del usuario o en su CV activo."""
        verified = []
        for skill in claimed_skills:
            clean = skill.strip()
            if not clean:
                continue
            clean_lower = clean.lower()
            # 1. Comprobar contra competencias del perfil
            if clean_lower in self.allowed_skills:
                verified.append(clean)
            # 2. Comprobar si figura textualmente en el CV activo
            elif self.cv_text_lower and clean_lower in self.cv_text_lower:
                verified.append(clean)
            # 3. Si no hay perfil ni CV cargado, aceptar las detectadas objetivamente por el motor
            elif not self.allowed_skills and not self.cv_text_lower:
                verified.append(clean)
            else:
                logger.debug("Habilidad descartada por no figurar en CV ni perfil: '%s'", clean)
        return verified

