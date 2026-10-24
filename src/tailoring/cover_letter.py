"""Generador de cartas de presentación honestas y personalizadas en español."""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from ..evaluator.ollama_client import OllamaClient
from .verifier import ProfileVerifier

logger = logging.getLogger("lazyJobFinder.tailoring.cover_letter")


class CoverLetterGenerator:
    """Genera cartas de presentación profesionales y sobrias adaptadas a cada vacante."""

    def __init__(self, profile: Dict[str, Any], ollama_client: Optional[OllamaClient] = None):
        self.profile = profile
        self.ollama = ollama_client or OllamaClient()
        self.verifier = ProfileVerifier(profile)

    def generate(self, job: Dict[str, Any], eval_result: Dict[str, Any]) -> str:
        """Genera el texto completo de la carta de presentación en formato Markdown validando afirmaciones."""
        candidato = self.profile.get("candidato", {})
        nombre = candidato.get("nombre_completo", "Candidato")
        email = candidato.get("email", "contacto@candidato.com")
        telefono = candidato.get("telefono", "")
        ciudad = candidato.get("ciudad", "España")
        fecha_actual = datetime.now().strftime("%d de %B de %Y")

        empresa = job.get("company", "Equipo de Selección")
        puesto = job.get("title", "Puesto Ofertado")
        
        # Validar que solo se presuman habilidades reales
        atomic_facts = self.verifier.get_approved_atomic_facts()
        raw_matched = eval_result.get("matched_skills", [])
        verified_matched = self.verifier.validate_matched_skills(raw_matched)
        missing = eval_result.get("missing_skills", [])
        titulo_candidato = atomic_facts["candidato"]["titulo"]
        skills_str = ", ".join(verified_matched) if verified_matched else "competencias funcionales y formativas acreditadas"

        # Intento con LLM local guiado estrictamente por hechos atómicos aprobados
        prompt = (
            f"Redacta una carta de presentación formal y profesional en español para una candidatura de empleo.\n\n"
            f"### HECHOS ATÓMICOS APROBADOS DEL CANDIDATO (ÚNICA FUENTE DE VERDAD):\n"
            f"- Nombre: {nombre}\n"
            f"- Especialidad o Titulación: {titulo_candidato}.\n"
            f"- Historial y Experiencia: {atomic_facts['experiencia_comercial_previa']}.\n"
            f"- Competencias demostrables que coinciden con la vacante: {skills_str}.\n\n"
            f"### DATOS DE LA VACANTE:\n"
            f"- Puesto: {puesto}\n"
            f"- Empresa a la que postula: {empresa}\n"
            f"- Requisitos adicionales donde manifiesta total disposición para aprender: {', '.join(missing[:2]) or 'nuevas herramientas y procedimientos'}.\n\n"
            f"DIRECTRICES DE VERACIDAD:\n"
            f"1. Estructura en 3 o 4 párrafos claros y directos (máximo 250 palabras).\n"
            f"2. Expresa motivación genuina por el proyecto de {empresa} y por consolidar la carrera profesional en {puesto}.\n"
            f"3. Resalta la base formativa y profesional sólida adquirida y los proyectos prácticos realizados.\n"
            f"4. PROHIBIDO inventar empresas pasadas ficticias o atribuir años de experiencia laboral comercial previa inexistentes.\n"
            f"5. Tono humilde, profesional, resolutivo y entusiasta por seguir aprendiendo.\n"
            f"Devuelve ÚNICAMENTE el cuerpo de la carta en español."
        )

        try:
            body_text = self.ollama.generate(
                prompt=prompt,
                format_json=False,
                temperature=0.1,
                timeout=50,
            )
            cleaned_body = body_text.strip().strip('"')
            is_valid, violations = self.verifier.validate_concrete_assertions(cleaned_body, target_company=empresa)
            if is_valid and len(cleaned_body) > 100:
                return self._assemble_letter(
                    nombre=nombre,
                    email=email,
                    telefono=telefono,
                    ciudad=ciudad,
                    empresa=empresa,
                    puesto=puesto,
                    fecha=fecha_actual,
                    body=cleaned_body,
                )
            else:
                logger.warning("Carta generada por LLM rechazada por afirmaciones no respaldadas: %s", violations)
        except Exception as e:
            logger.debug("Generación de carta por LLM falló, usando plantilla determinista: %s", e)

        # Plantilla determinista de respaldo 100% verídica y adaptable a cualquier profesión
        tech_ref = f"{', '.join(verified_matched[:3])}" if verified_matched else "las competencias requeridas"
        perfil_desc = titulo_candidato or "mi perfil formativo y profesional"
        fallback_body = (
            f"Estimado/a responsable de selección de {empresa},\n\n"
            f"Me pongo en contacto con ustedes con motivo de la vacante de {puesto}. Tras revisar con detalle los requisitos de la oferta, "
            f"considero que mi preparación como {perfil_desc} "
            f"y los proyectos prácticos realizados con {tech_ref} me permiten ofrecer una base sólida, dedicación y muchas ganas "
            f"de aportar valor a su organización.\n\n"
            f"A lo largo de mi trayectoria he profundizado en las metodologías, procedimientos y herramientas propias de este ámbito, "
            f"priorizando el rigor, el trabajo bien hecho y la colaboración fluida en equipo.\n\n"
            f"Me motiva especialmente incorporarme a {empresa} por la proyección de sus proyectos y la posibilidad de seguir creciendo "
            f"en un entorno profesional de primer nivel. Cuento con una alta capacidad de aprendizaje, actitud proactiva y total disposición "
            f"para dominar con rapidez cualquier procedimiento específico que el puesto requiera.\n\n"
            f"Agradezco de antemano el tiempo dedicado a valorar mi candidatura y quedo a su entera disposición para mantener una "
            f"entrevista en la que poder profundizar en mis motivaciones.\n\n"
            f"Atentamente,\n"
            f"{nombre}"
        )

        return self._assemble_letter(
            nombre=nombre,
            email=email,
            telefono=telefono,
            ciudad=ciudad,
            empresa=empresa,
            puesto=puesto,
            fecha=fecha_actual,
            body=fallback_body,
        )

    def _assemble_letter(
        self,
        nombre: str,
        email: str,
        telefono: str,
        ciudad: str,
        empresa: str,
        puesto: str,
        fecha: str,
        body: str,
    ) -> str:
        return f"""# Carta de Presentación

**De:** {nombre}  
**Contacto:** {email} | {telefono} | {ciudad}  
**Para:** Departamento de Selección / {empresa}  
**Referencia:** Candidatura para {puesto}  
**Fecha:** {fecha}  

---

{body.strip()}
"""
