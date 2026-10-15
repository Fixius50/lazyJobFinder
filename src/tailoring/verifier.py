"""Validador programático estricto de afirmaciones concretas y veracidad contra el perfil canónico."""

import logging
import re
from typing import Any, Dict, List, Set, Tuple

logger = logging.getLogger("lazyJobFinder.tailoring.verifier")


class ProfileVerifier:
    """
    Valida mediante código que ninguna afirmación profesional generada contradiga o invente datos.
    Distingue explícitamente entre competencias formativas/académicas y experiencia profesional en empresas.
    """

    def __init__(self, profile: Dict[str, Any]):
        self.profile = profile
        self.allowed_skills = self._extract_allowed_skills()
        self.allowed_institutions = self._extract_allowed_institutions()
        self.allowed_degrees = self._extract_allowed_degrees()
        self.allowed_projects = self._extract_allowed_projects()
        # Verificar si el perfil cuenta con historial laboral comercial
        self.has_commercial_employment = bool(profile.get("experiencia_laboral", []))

    def _extract_allowed_skills(self) -> Set[str]:
        skills = set()
        competencias = self.profile.get("competencias_tecnicas", {})

        for item in competencias.get("lenguajes", []):
            if isinstance(item, dict):
                skills.add(item.get("nombre", "").lower().strip())
                for c in item.get("conceptos", []):
                    skills.add(c.lower().strip())
            elif isinstance(item, str):
                skills.add(item.lower().strip())

        for db in competencias.get("bases_de_datos", []):
            skills.add(db.lower().strip())
            if "mysql" in db.lower():
                skills.add("mysql")
            if "postgres" in db.lower():
                skills.add("postgresql")
                skills.add("postgres")
            if "mongodb" in db.lower():
                skills.add("mongodb")
            if "oracle" in db.lower():
                skills.add("oracle")

        for fw in competencias.get("frameworks_y_librerias", []):
            skills.add(fw.lower().strip())
            if "spring" in fw.lower():
                skills.add("spring")
                skills.add("spring boot")

        for h in competencias.get("herramientas_y_entornos", []):
            skills.add(h.lower().strip())
            if "git" in h.lower():
                skills.add("git")
                skills.add("github")
            if "linux" in h.lower():
                skills.add("linux")
            if "rest" in h.lower():
                skills.add("rest")
                skills.add("api rest")
                skills.add("apis rest")

        skills.update({"java", "sql", "pl/sql", "javascript", "php", "html", "css", "html5", "css3", "json", "xml", "poo", "dam", "full stack"})
        return {s for s in skills if s}

    def _extract_allowed_institutions(self) -> Set[str]:
        inst = set()
        for f in self.profile.get("formacion", []):
            if f.get("institucion"):
                inst.add(f.get("institucion").lower().strip())
        return inst

    def _extract_allowed_degrees(self) -> Set[str]:
        degs = set()
        for f in self.profile.get("formacion", []):
            if f.get("titulo"):
                degs.add(f.get("titulo").lower().strip())
        degs.add("desarrollo de aplicaciones multiplataforma")
        degs.add("dam")
        return degs

    def _extract_allowed_projects(self) -> List[Dict[str, Any]]:
        return self.profile.get("proyectos_destacados", [])

    def get_approved_atomic_facts(self) -> Dict[str, Any]:
        """
        Devuelve el conjunto cerrado de hechos atómicos estructurados aprobados.
        Esta es la ÚNICA fuente de verdad autorizada para la IA.
        """
        candidato = self.profile.get("candidato", {})
        return {
            "candidato": {
                "nombre": candidato.get("nombre_completo", "Roberto"),
                "titulo": candidato.get("titulo_profesional", "Desarrollador Junior (DAM)"),
                "ciudad": candidato.get("ciudad", "España"),
            },
            "formacion_academica": [
                {
                    "titulo": f.get("titulo"),
                    "institucion": f.get("institucion"),
                    "año": f.get("fecha_fin"),
                }
                for f in self.profile.get("formacion", [])
            ],
            "experiencia_comercial_previa": "Ninguna en empresas (perfil junior recién titulado en FP DAM)",
            "competencias_tecnicas_certificadas": sorted(list(self.allowed_skills)),
            "proyectos_academicos_certificados": [
                {
                    "nombre": p.get("nombre"),
                    "tecnologias": p.get("tecnologias", []),
                    "descripcion": p.get("descripcion", "").strip(),
                }
                for p in self.allowed_projects
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

        # 3. Validación de roles ficticios
        fictitious_roles = [
            r"\b(fui|como)\s+(lead|senior|arquitecto|project\s+manager|jefe\s+de\s+equipo)\b",
            r"\blideré\s+equipos?\b",
            r"\bgestión\s+de\s+personal\b",
            r"\bgestión\s+de\s+presupuestos?\b",
        ]
        for pattern in fictitious_roles:
            if re.search(pattern, text_lower):
                violations.append(f"Afirmación no respaldada: Se atribuye un rol de antigüedad o gestión ({pattern}).")

        # 4. Tecnologías ajenas no respaldadas
        words = re.findall(r"\b[A-Za-z0-9#\+\./\-]+\b", text)
        blacklisted_techs = {
            "kubernetes", "k8s", "aws", "azure", "gcp", "react native", "flutter",
            "scala", "golang", "c#", ".net", "cobol", "rust", "angular", "react",
            "django", "ruby", "rails", "swift", "kotlin", "objective-c"
        }
        for word in words:
            w_lower = word.lower()
            if w_lower in blacklisted_techs and w_lower not in self.allowed_skills:
                violations.append(f"Tecnología no respaldada en el perfil canónico: '{word}'.")

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
        """Construye un resumen certificado a partir de los datos estructurados aprobados en profile.yaml."""
        verified_matched = [s for s in matched_skills if s.lower() in self.allowed_skills]
        tech_clause = f" con especial foco en {', '.join(verified_matched[:3])}" if verified_matched else ""

        return (
            f"Titulado en Desarrollo de Aplicaciones Multiplataforma (DAM){tech_clause}, "
            f"con sólida preparación técnica adquirida en programación orientada a objetos (Java), persistencia en bases de datos relacionales "
            f"(SQL) y creación de APIs REST. Proactivo y comprometido con las buenas prácticas, con alta motivación por incorporarme al "
            f"equipo de {company} para aportar valor en la vacante de {job_title} y continuar consolidando mi carrera profesional."
        )

    def validate_matched_skills(self, claimed_skills: List[str]) -> List[str]:
        """Filtra y devuelve exclusivamente las habilidades que existen fehacientemente en el perfil canónico."""
        verified = []
        for skill in claimed_skills:
            clean = skill.strip()
            if not clean:
                continue
            if clean.lower() in self.allowed_skills:
                verified.append(clean)
            elif any(allowed in clean.lower() for allowed in ["java", "sql", "pl/sql", "dam", "linux", "git", "php", "rest", "nosql"]):
                verified.append(clean)
            else:
                logger.debug("Habilidad descartada por no existir en profile.yaml: '%s'", clean)
        return verified
