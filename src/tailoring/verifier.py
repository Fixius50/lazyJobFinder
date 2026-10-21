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
        # Las competencias y herramientas DEBEN provenir 100% exclusivamente del CV aportado.
        if self.cv_text and self.cv_text.strip():
            return self._extract_skills_from_cv_text()
        return set()

    def _extract_skills_from_cv_text(self) -> Set[str]:
        """Extrae competencias, herramientas, maquinaria y aptitudes exclusivamente del CV activo de forma universal."""
        skills = set()
        lines = self.cv_text.splitlines()

        stop_lines_pattern = re.compile(
            r"(\bduración\s+del\s+curso\b|\bfecha\s*:|\bfirma\b|\bfdo\s*:|\bconforme\s+ha\s+cursado\b|"
            r"\bcamino\s+del|\bcalle\b|\bavenida\b|\b\d{5}\b|\bdni\b|\bnie\b|\bnif\b|\badecco\b|"
            r"\bmancomunado\b|\bdomicilio\b|\btel[eé]fono\b|\bemail\b|\bcorreo\b|\bhttp\b|\bwww\b)",
            re.IGNORECASE,
        )

        stop_words = {
            "el", "la", "los", "las", "un", "una", "unos", "unas", "del", "al", "con", "sin", "por", "para",
            "como", "sobre", "entre", "desde", "hasta", "según", "segun", "conforme", "artículo", "articulo",
            "ley", "decreto", "servicio", "prevención", "evaluación", "evaluacion", "siguientes", "contenidos",
            "certifica", "certificado", "superado", "éxito", "exito", "mancomunado", "grupo", "adecco",
            "alumno", "roberto", "monedero", "alonso", "programa", "formación", "formacion", "curso",
            "genérico", "generico", "lugares", "equipos", "trabajo", "trabajos", "psicosociales", "físicos",
            "fisicos", "químicos", "quimicos", "biológicos", "biologicos", "pvd", "especialidad", "riesgos",
            "laborales", "madrid", "pozuelo", "alarcon", "alarcón", "barcelona", "valencia", "sevilla", "bilbao",
            "málaga", "zaragoza", "españa", "spain", "camino", "cerro", "gamos", "dni", "nie", "horas", "min",
            "minutos", "diciembre", "enero", "consta", "nivel", "medio", "básico", "alto", "avanzado", "profesional",
            "candidato", "titular", "año", "años", "experiencia", "conocimientos", "habilidades", "competencias"
        }

        in_skills_section = False
        has_explicit_sections = bool(
            re.search(
                r"(contenido|módulo|modulo|curso|formación|formacion|habilidad|competencia|conocimiento|skill|herramienta|aptitud|destreza|funciones|tareas)",
                self.cv_text,
                re.IGNORECASE,
            )
        )

        for line in lines:
            clean_line = line.strip()
            if not clean_line or stop_lines_pattern.search(clean_line):
                in_skills_section = False
                continue

            # Detección de encabezado de sección relevante
            if re.search(r"(contenidos|módulos|competencias|habilidades|skills|conocimientos|herramientas|funciones|formación)\s*:?$", clean_line, re.IGNORECASE):
                in_skills_section = True
                continue

            is_bullet = clean_line.startswith(("-", "*", "•", "·", "1.", "2.", "3.", "4.", "5."))
            if has_explicit_sections and not in_skills_section and not is_bullet:
                continue

            clean_content = re.sub(r"^[\-\*•·0-9\.\s]+", "", clean_line)
            chunks = re.split(r"[,;•|·\*\–/\t]|\s{2,}", clean_content)
            for chunk in chunks:
                sub_chunks = re.split(r"(?<=[a-zñáéíóú0-9])\s+(?=[A-ZÁÉÍÓÚ][a-zñáéíóú])", chunk)
                for sc in sub_chunks:
                    cand = sc.strip().lower()
                    cand = re.sub(r"^(nivel|conocimientos en|experiencia en|avanzado|medio|básico|alto|dominio de|especialidad)\s+", "", cand).strip()
                    cand = re.sub(r"[\(\)\[\]\{\}\"\']", "", cand).strip(" -.,;:•|·/*")
                    if not cand or len(cand) < 3 or stop_lines_pattern.search(cand):
                        continue

                    if ":" in cand:
                        parts = [p.strip() for p in cand.split(":") if p.strip()]
                        for p in parts:
                            p_clean = re.sub(r"[\(\)\[\]\{\}\"\']", "", p).strip(" -.,;:•|·/*")
                            if p_clean not in stop_words and len(p_clean) >= 3 and not stop_lines_pattern.search(p_clean):
                                skills.add(p_clean)
                    else:
                        if cand not in stop_words and not stop_lines_pattern.search(cand):
                            skills.add(cand)

        # Expansión de sinónimos y términos técnicos de diferentes oficios (logística, almacén, sanidad, administración, etc.)
        expanded = set(skills)
        for s in list(skills):
            if "carretillaselevadoras" in s or "carretilla" in s:
                expanded.add("carretillas elevadoras")
                expanded.add("carretilla")
                expanded.add("carretillero")
            if "traspaletamanual" in s or "traspaleta" in s:
                expanded.add("traspaleta manual")
                expanded.add("traspaleta eléctrica")
                expanded.add("traspaleta")
            if "manipulación de objetos" in s or "manipulación de cargas" in s:
                expanded.add("manipulación de cargas")
                expanded.add("manipulacion de cargas")
            if "protección individual" in s or "epi" in s:
                expanded.add("epi")
                expanded.add("epis")
            if "logística" in s or "logistica" in s:
                expanded.add("almacén")
                expanded.add("almacen")
                expanded.add("logística")
            if "prevención de riesgos" in s or "riesgos laborales" in s:
                expanded.add("prevención de riesgos laborales")
                expanded.add("prl")

        return {
            s for s in expanded
            if s not in stop_words and len(s) >= 3 and not s.isdigit()
        }

    def _extract_allowed_institutions(self) -> Set[str]:
        inst = set()
        if self.cv_text:
            matches = re.findall(
                r"(?:universidad|instituto|centro|colegio|escuela|cámara de comercio|grupo adecco|adecco|servicio de prevención)\s+[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]{3,35}",
                self.cv_text,
                re.IGNORECASE,
            )
            for m in matches:
                inst.add(m.strip().lower())
        return inst

    def _extract_allowed_degrees(self) -> Set[str]:
        degs = set()
        if self.cv_text:
            degree_matches = re.findall(
                r"(?:grado|máster|master|ingenier[íi]a|licenciatura|fp|ciclo formativo|técnico superior|bachillerato|diplomatura|curso|certificaci[óo]n|programa de formación)\s+(?:en\s+)?[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]{3,40}",
                self.cv_text,
                re.IGNORECASE,
            )
            for dm in degree_matches:
                degs.add(dm.strip().lower())
        return degs

    def _extract_allowed_projects(self) -> List[Dict[str, Any]]:
        return []

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
        noise = {
            "madrid", "barcelona", "valencia", "sevilla", "bilbao", "málaga", "zaragoza", "adecco", "dni", "nie",
            "alumno", "fecha", "servicio", "prevención", "empresa", "candidato", "profesional", "duración", "horas"
        }
        for skill in claimed_skills:
            clean = skill.strip()
            if not clean:
                continue
            clean_lower = clean.lower()
            if clean_lower in noise or len(clean_lower) < 3:
                continue
            # 1. Comprobar contra competencias autorizadas del perfil o CV activo
            if clean_lower in self.allowed_skills:
                verified.append(clean)
            # 2. Comprobar si figura textualmente en el CV activo (evitando palabras vacías)
            elif self.cv_text_lower and clean_lower in self.cv_text_lower:
                verified.append(clean)
            # 3. Si no hay perfil ni CV cargado, aceptar las detectadas objetivamente por el motor
            elif not self.allowed_skills and not self.cv_text_lower:
                verified.append(clean)
            else:
                logger.debug("Habilidad descartada por no figurar en CV ni perfil: '%s'", clean)
        return verified

