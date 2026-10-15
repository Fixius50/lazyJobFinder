"""Módulo de adaptación honesta del CV con validación estricta por código (anti-alucinación)."""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple
import yaml

from ..evaluator.ollama_client import OllamaClient
from .verifier import ProfileVerifier

logger = logging.getLogger("lazyJobFinder.tailoring.cv")


class CVTailorer:
    """Adapta el enfoque del CV para una vacante específica asegurando que cada dato esté certificado por el perfil."""

    def __init__(self, profile: Dict[str, Any], ollama_client: Optional[OllamaClient] = None):
        self.profile = profile
        self.ollama = ollama_client or OllamaClient()
        self.verifier = ProfileVerifier(profile)

    def tailor(
        self,
        job: Dict[str, Any],
        eval_result: Dict[str, Any],
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Genera una versión en Markdown del CV adaptada honestamente al puesto,
        validando mediante código que no se introduzcan alucinaciones ni afirmaciones falsas.
        """
        candidato = self.profile.get("candidato", {})
        nombre = candidato.get("nombre_completo", "Roberto")
        titulo_base = candidato.get("titulo_profesional", "Desarrollador de Software Junior (DAM)")
        email = candidato.get("email", "tu_email@ejemplo.com")
        telefono = candidato.get("telefono", "+34 600 000 000")
        linkedin = candidato.get("linkedin", "")
        github = candidato.get("github", "")

        raw_matched = eval_result.get("matched_skills", [])
        # 1. Validar por código que las habilidades coincidentes existan en el perfil
        verified_skills = self.verifier.validate_matched_skills(raw_matched)

        # 2. Adaptar y sanitizar el resumen profesional
        raw_summary = self._generate_adapted_summary(job, verified_skills)
        sanitized_summary, corrections = self.verifier.sanitize_summary(
            generated_summary=raw_summary,
            matched_skills=verified_skills,
            company=job.get("company", "la empresa"),
            job_title=job.get("title", "Desarrollador"),
        )

        # 3. Reordenar proyectos canónicos por relevancia (sin alterar su contenido)
        ordered_projects, project_reasons = self._order_projects_by_relevance(job, verified_skills)

        # 4. Construir el documento Markdown adaptado usando únicamente campos verificados
        cv_md = self._render_markdown_cv(
            nombre=nombre,
            titulo=titulo_base,
            email=email,
            telefono=telefono,
            linkedin=linkedin,
            github=github,
            summary=sanitized_summary,
            projects=ordered_projects,
            matched_skills=verified_skills,
        )

        # 5. Generar registro de auditoría de diferencias (diff)
        diff_audit = {
            "puesto": job.get("title"),
            "empresa": job.get("company"),
            "resumen_original": self.profile.get("resumen_base", "").strip(),
            "resumen_adaptado": sanitized_summary.strip(),
            "competencias_destacadas": verified_skills,
            "reordenacion_proyectos": project_reasons,
            "correcciones_anti_alucinacion": corrections or ["Ninguna (contenido 100% fiel al perfil)"],
            "garantia_honestidad": (
                "Validado algorítmicamente contra config/profile.yaml mediante ProfileVerifier. "
                "Los datos académicos, empresas y tecnologías son inmutables."
            ),
        }

        return cv_md, diff_audit

    def _generate_adapted_summary(self, job: Dict[str, Any], verified_skills: List[str]) -> str:
        """Intenta generar un resumen enfocado mediante el LLM local a partir de hechos atómicos aprobados."""
        atomic_facts = self.verifier.get_approved_atomic_facts()
        job_title = job.get("title", "")
        company = job.get("company", "")

        prompt = (
            f"Eres un asistente de redacción curricular que opera bajo una política de CERO ALUCINACIONES.\n\n"
            f"### HECHOS ATÓMICOS APROBADOS (ÚNICA FUENTE DE VERDAD):\n"
            f"- Titulación: Formación Profesional de Grado Superior en DAM (2024).\n"
            f"- Historial comercial: {atomic_facts['experiencia_comercial_previa']}.\n"
            f"- Competencias verificadas para este puesto: {', '.join(verified_skills) or 'Java, SQL y arquitectura POO'}.\n"
            f"- Resumen base aprobado: '{self.profile.get('resumen_base', '').strip()}'\n\n"
            f"### VACANTE:\n"
            f"- Puesto: {job_title}\n"
            f"- Empresa: {company}\n\n"
            f"INSTRUCCIONES:\n"
            f"Reformula y enfoca el resumen (máximo 4 líneas) resaltando honestamente las competencias DAM que encajan.\n"
            f"PROHIBICIÓN ESTRICTA: No inventes empresas donde supuestamente trabajó, ni años de experiencia laboral, "
            f"ni titulaciones universitarias, ni tecnologías ajenas.\n"
            f"Devuelve ÚNICAMENTE el texto redactado del resumen sin comentarios."
        )

        try:
            adapted = self.ollama.generate(
                prompt=prompt,
                format_json=False,
                temperature=0.1,
                timeout=45,
            )
            cleaned = adapted.strip().strip('"')
            if len(cleaned) > 50:
                return cleaned
        except Exception as e:
            logger.debug("Generación de resumen por LLM falló, usando plantilla canónica: %s", e)

        # Fallback canónico verificado
        return self.verifier._build_canonical_summary(verified_skills, company, job_title)

    def _order_projects_by_relevance(
        self, job: Dict[str, Any], verified_skills: List[str]
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Reordena los proyectos para situar en primer lugar aquellos con más coincidencias técnicas."""
        projects = list(self.profile.get("proyectos_destacados", []))
        desc_lower = (job.get("description", "") + " " + job.get("title", "")).lower()

        scored_projects = []
        for p in projects:
            score = 0
            p_techs = [t.lower() for t in p.get("tecnologias", [])]
            for t in p_techs:
                if t in desc_lower:
                    score += 2
                if any(m.lower() in t for m in verified_skills):
                    score += 1
            scored_projects.append((score, p))

        scored_projects.sort(key=lambda x: x[0], reverse=True)
        ordered = [p for _, p in scored_projects]

        reasons = [
            f"Proyecto '{p['nombre']}' en posición #{idx+1} por relevancia de stack ({', '.join(p.get('tecnologias', []))})"
            for idx, p in enumerate(ordered)
        ]
        return ordered, reasons

    def _render_markdown_cv(
        self,
        nombre: str,
        titulo: str,
        email: str,
        telefono: str,
        linkedin: str,
        github: str,
        summary: str,
        projects: List[Dict[str, Any]],
        matched_skills: List[str],
    ) -> str:
        links = []
        if linkedin:
            links.append(f"[LinkedIn]({linkedin})")
        if github:
            links.append(f"[GitHub]({github})")
        links_str = " | ".join(links)

        md = f"""# {nombre}
**{titulo}**  
España | {email} | {telefono}  
{links_str}

---

## Perfil Profesional
{summary}

---

## Formación Académica
"""
        for form in self.profile.get("formacion", []):
            md += f"- **{form.get('titulo')}**  \n"
            md += f"  *{form.get('institucion')}* | {form.get('fecha_fin')}  \n"
            modulos = form.get("modulos_destacados", [])
            if modulos:
                md += f"  - Módulos clave: {', '.join(modulos)}\n"

        md += "\n---\n\n## Competencias Técnicas Destacadas\n"
        techs = self.profile.get("competencias_tecnicas", {})
        lenguajes = [l.get("nombre") if isinstance(l, dict) else l for l in techs.get("lenguajes", [])]
        dbs = techs.get("bases_de_datos", [])
        tools = techs.get("herramientas_y_entornos", [])

        md += f"- **Lenguajes:** {', '.join(lenguajes)}\n"
        md += f"- **Bases de Datos:** {', '.join(dbs)}\n"
        md += f"- **Herramientas y Entornos:** {', '.join(tools)}\n"
        if matched_skills:
            md += f"- **Coincidencias clave con la vacante:** {', '.join(matched_skills)}\n"

        md += "\n---\n\n## Proyectos Destacados (Selección Relevante)\n"
        for p in projects:
            tech_str = ", ".join(p.get("tecnologias", []))
            md += f"### {p.get('nombre')}\n"
            md += f"*Tecnologías: {tech_str}*\n"
            md += f"{p.get('descripcion', '').strip()}\n"
            for logro in p.get("logros", []):
                md += f"- {logro}\n"
            md += "\n"

        md += "---\n\n## Idiomas\n"
        for idi in self.profile.get("idiomas", []):
            md += f"- **{idi.get('idioma')}:** {idi.get('nivel')}\n"

        return md.strip()
