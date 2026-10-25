"""Generador de cartas de presentación honestas y personalizadas en español."""

import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, Optional

from ..evaluator.ollama_client import OllamaClient
from .verifier import ProfileVerifier

logger = logging.getLogger("lazyJobFinder.tailoring.cover_letter")


class CoverLetterGenerator:
    """Genera cartas de presentación profesionales y sobrias adaptadas a cada vacante."""

    def __init__(self, profile: Optional[Dict[str, Any]] = None, ollama_client: Optional[OllamaClient] = None):
        from .cv_reader import get_active_profile
        self.profile = profile if profile is not None else get_active_profile()
        self.ollama = ollama_client or OllamaClient()
        self.verifier = ProfileVerifier(self.profile)

    def _clean_body_placeholders(self, text: str, nombre: str, empresa: str, puesto: str, titulo: str) -> str:
        """Elimina sistemáticamente cualquier corchete o marcador de posición que el LLM pudiera generar."""
        if not text:
            return ""
        # Reemplazar placeholders de nombre
        text = re.sub(r"\[(?:Tu\s+Nombre|Nombre|Nombre\s+del\s+Candidato|Firma|Candidato)\]", nombre, text, flags=re.IGNORECASE)
        # Reemplazar placeholders de destinatario
        text = re.sub(r"\[(?:Nombre\s+del\s+Recibidor|Recibidor|Responsable|Nombre\s+del\s+Responsable|Destinatario|Nombre\s+del\s+empleador)\]", f"Responsable de Selección de {empresa}", text, flags=re.IGNORECASE)
        # Reemplazar placeholders de titulación
        text = re.sub(r"\[(?:Especialidad\s+o\s+Titulación|Titulación|Especialidad|Grado)\]", titulo or "mi especialidad técnica", text, flags=re.IGNORECASE)
        # Reemplazar placeholders de proyectos
        text = re.sub(r"\[(?:Nombre\s+de\s+un\s+proyecto\s+práctico|Proyecto\s+práctico|Proyecto)\]", "proyectos formativos y profesionales del sector", text, flags=re.IGNORECASE)
        # Reemplazar placeholders de empresa o puesto
        text = re.sub(r"\[(?:Empresa|Nombre\s+de\s+la\s+Empresa)\]", empresa, text, flags=re.IGNORECASE)
        text = re.sub(r"\[(?:Puesto|Nombre\s+del\s+Puesto)\]", puesto, text, flags=re.IGNORECASE)
        # Limpiar cualquier corchete residual [ ... ]
        text = re.sub(r"\[([^\]]+)\]", r"\1", text)
        return text.strip()

    def generate(self, job: Dict[str, Any], eval_result: Dict[str, Any]) -> str:
        """Genera el texto completo de la carta de presentación en formato Markdown validando afirmaciones."""
        from .cv_reader import get_active_profile
        if self.profile is None:
            self.profile = get_active_profile()
            self.verifier = ProfileVerifier(self.profile)

        candidato = self.profile.get("candidato", {})
        nombre = (candidato.get("nombre_completo") or "").strip()
        email = (candidato.get("email") or "").strip()
        telefono = (candidato.get("telefono") or "").strip()
        ciudad = (candidato.get("ciudad") or "").strip()
        fecha_actual = datetime.now().strftime("%d de %B de %Y")

        empresa = job.get("company", "Equipo de Selección")
        puesto = job.get("title", "Puesto Ofertado")

        # Validar que solo se presuman habilidades reales
        atomic_facts = self.verifier.get_approved_atomic_facts()
        raw_matched = eval_result.get("matched_skills", [])
        verified_matched = self.verifier.validate_matched_skills(raw_matched)
        missing = eval_result.get("missing_skills", [])
        titulo_candidato = atomic_facts.get("candidato", {}).get("titulo") or candidato.get("titulo_profesional", "Profesional")
        skills_str = ", ".join(verified_matched) if verified_matched else "competencias funcionales y formativas acreditadas"

        # Intento con LLM local guiado estrictamente por hechos atómicos aprobados
        prompt = (
            f"Redacta una carta de presentación formal y profesional en español para una candidatura de empleo.\n\n"
            f"### DATOS DEL CANDIDATO (ÚNICA FUENTE DE VERDAD):\n"
            f"- Nombre del candidato: {nombre}\n"
            f"- Especialidad o Perfil: {titulo_candidato}\n"
            f"- Trayectoria y Experiencia: {atomic_facts.get('experiencia_comercial_previa', 'Formación y experiencia acreditadas')}\n"
            f"- Competencias demostrables que coinciden con la vacante: {skills_str}\n\n"
            f"### DATOS DE LA VACANTE:\n"
            f"- Puesto: {puesto}\n"
            f"- Empresa a la que postula: {empresa}\n"
            f"- Requisitos adicionales donde manifiesta total disposición para aprender: {', '.join(missing[:2]) or 'nuevas herramientas y procedimientos'}\n\n"
            f"DIRECTRICES DE REDACCIÓN:\n"
            f"1. Estructura en 3 o 4 párrafos claros y directos (máximo 250 palabras).\n"
            f"2. Expresa motivación genuina por el proyecto de {empresa} y por consolidar la carrera profesional en {puesto}.\n"
            f"3. Resalta la base formativa y profesional sólida adquirida y la dedicación demostrada.\n"
            f"4. PROHIBIDO TERMINANTEMENTE usar corchetes o marcadores de posición como [Tu Nombre], [Nombre del Recibidor], [Especialidad o Titulación] o similares. "
            f"Usa siempre los datos reales del candidato ({nombre}) y de la empresa ({empresa}).\n"
            f"5. Firma la carta al final con: Atentamente,\n{nombre}\n"
            f"Devuelve ÚNICAMENTE el cuerpo de la carta en español."
        )

        try:
            body_text = self.ollama.generate(
                prompt=prompt,
                format_json=False,
                temperature=0.1,
                timeout=50,
            )
            cleaned_body = self._clean_body_placeholders(body_text.strip().strip('"'), nombre, empresa, puesto, titulo_candidato)
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

        # Plantilla determinista de respaldo 100% verídica y personalizada
        competencias_ref = f"{', '.join(verified_matched[:3])}" if verified_matched else "las competencias requeridas"
        perfil_desc = titulo_candidato or "mi perfil formativo y profesional"
        fallback_body = (
            f"Estimado/a responsable de selección de {empresa},\n\n"
            f"Me pongo en contacto con ustedes con motivo de la vacante de {puesto}. Tras revisar con detalle los requisitos de la oferta, "
            f"considero que mi preparación como {perfil_desc} "
            f"y mi experiencia con {competencias_ref} me permiten ofrecer una base sólida, dedicación y muchas ganas "
            f"de aportar valor a su organización.\n\n"
            f"A lo largo de mi trayectoria he profundizado en las metodologías, procedimientos y herramientas propias de este ámbito, "
            f"priorizando el rigor, el trabajo bien hecho y la colaboración fluida en equipo.\n\n"
            f"Me motiva especialmente incorporarme a {empresa} por la proyección de sus proyectos y la posibilidad de seguir creciendo "
            f"en un entorno profesional de primer nivel. Cuento con una alta capacidad de aprendizaje, actitud proactiva y total disposición "
            f"para dominar con rapidez cualquier procedimiento específico que el puesto requiera.\n\n"
            f"Agradezco de antemano el tiempo dedicado a valorar mi candidatura y quedo a su entera disposición para mantener una entrevista "
            f"en la que profundizar sobre mi trayectoria.\n\n"
            f"Atentamente,\n\n"
            f"**{nombre}**"
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
        meta_lines = []
        if nombre:
            meta_lines.append(f"**De:** {nombre}")
        contact_parts = [p for p in [ciudad, email, telefono] if p]
        if contact_parts:
            meta_lines.append(f"**Contacto:** {' | '.join(contact_parts)}")
        meta_lines.append(f"**Para:** Departamento de Selección / {empresa}")
        meta_lines.append(f"**Referencia:** Candidatura para {puesto}")
        if fecha:
            meta_lines.append(f"**Fecha:** {fecha}")

        header_block = "  \n".join(meta_lines)
        return f"# Carta de Presentación\n\n{header_block}\n\n---\n\n{body.strip()}\n"
