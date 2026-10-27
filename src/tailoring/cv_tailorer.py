"""Módulo de adaptación honesta del CV con validación estricta por código (anti-alucinación)."""

import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple
import yaml

from ..evaluator.ollama_client import OllamaClient
from .verifier import ProfileVerifier

logger = logging.getLogger("lazyJobFinder.tailoring.cv")


class CVTailorer:
    """Adapta el enfoque del CV para una vacante específica asegurando que cada dato esté certificado por el perfil."""

    def __init__(self, profile: Optional[Dict[str, Any]] = None, ollama_client: Optional[OllamaClient] = None):
        from .cv_reader import get_active_profile
        self.profile = profile if profile is not None else get_active_profile()
        self.ollama = ollama_client or OllamaClient()
        self.verifier = ProfileVerifier(self.profile)

    def tailor(
        self,
        job: Dict[str, Any],
        eval_result: Dict[str, Any],
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Genera una versión en Markdown del CV adaptada honestamente al puesto,
        validando mediante código que no se introduzcan alucinaciones ni afirmaciones falsas.
        """
        from .cv_reader import get_active_profile
        if self.profile is None:
            self.profile = get_active_profile()
            self.verifier = ProfileVerifier(self.profile)

        candidato = self.profile.get("candidato", {})
        nombre = (candidato.get("nombre_completo") or "").strip()
        titulo_base = (candidato.get("titulo_profesional") or self.profile.get("primary_role") or "").strip()
        email = (candidato.get("email") or "").strip()
        telefono = (candidato.get("telefono") or "").strip()
        ciudad = (candidato.get("ciudad") or "").strip()
        linkedin = (candidato.get("linkedin") or "").strip()
        github = (candidato.get("github") or "").strip()

        raw_matched = eval_result.get("matched_skills", [])
        # 1. Validar por código que las habilidades coincidentes existan en el perfil
        verified_skills = self.verifier.validate_matched_skills(raw_matched)

        # 2. Adaptar y sanitizar el resumen profesional
        raw_summary = self._generate_adapted_summary(job, verified_skills)
        sanitized_summary, corrections = self.verifier.sanitize_summary(
            generated_summary=raw_summary,
            matched_skills=verified_skills,
            company=job.get("company", "la empresa"),
            job_title=job.get("title", "Puesto"),
        )

        # 3. Reordenar proyectos canónicos por relevancia (sin alterar su contenido)
        ordered_projects, project_reasons = self._order_projects_by_relevance(job, verified_skills)

        # 4. Construir el documento Markdown adaptado usando únicamente campos verificados
        cv_md = self._render_markdown_cv(
            nombre=nombre,
            titulo=titulo_base,
            email=email,
            telefono=telefono,
            ciudad=ciudad,
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
                "Validado algorítmicamente contra el perfil acreditado del candidato mediante ProfileVerifier. "
                "Los datos académicos, empresas y tecnologías son inmutables."
            ),
        }

        return cv_md, diff_audit

    def _generate_adapted_summary(self, job: Dict[str, Any], verified_skills: List[str]) -> str:
        """Intenta generar un resumen enfocado mediante el LLM local a partir de hechos atómicos aprobados."""
        atomic_facts = self.verifier.get_approved_atomic_facts()
        job_title = job.get("title", "")
        company = job.get("company", "")

        titulo_candidato = atomic_facts.get("candidato", {}).get("titulo") or self.profile.get("candidato", {}).get("titulo_profesional", "Profesional")
        skills_str = ", ".join(verified_skills) if verified_skills else "competencias acreditadas"

        prompt = (
            f"Eres un asistente de redacción curricular que opera bajo una estricta política de veracidad.\n\n"
            f"### DATOS DEL CANDIDATO (ÚNICA FUENTE DE VERDAD):\n"
            f"- Especialidad o Perfil: {titulo_candidato}.\n"
            f"- Trayectoria y Experiencia: {atomic_facts.get('experiencia_comercial_previa', 'Formación y competencias acreditadas')}.\n"
            f"- Competencias demostrables afines al puesto: {skills_str}.\n"
            f"- Resumen base aprobado: '{self.profile.get('resumen_base', '').strip()}'\n\n"
            f"### VACANTE:\n"
            f"- Puesto: {job_title}\n"
            f"- Empresa: {company}\n\n"
            f"INSTRUCCIONES:\n"
            f"Redacta un resumen profesional enfocado (máximo 4 líneas) que destaque honestamente las competencias del candidato afines a la vacante.\n"
            f"REGLA ESTRICTA: No inventes puestos, empresas pasadas, años de experiencia ni cualificaciones no acreditadas en el currículum.\n"
            f"Devuelve ÚNICAMENTE el texto redactado del resumen profesional, sin introducciones ni comentarios."
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
            f"Proyecto '{p.get('nombre', 'Proyecto')}' en posición #{idx+1} por relevancia de stack ({', '.join(p.get('tecnologias', []))})"
            for idx, p in enumerate(ordered)
        ]
        return ordered, reasons

    def _render_markdown_cv(
        self,
        nombre: str,
        titulo: str,
        email: str,
        telefono: str,
        ciudad: str,
        linkedin: str,
        github: str,
        summary: str,
        projects: List[Dict[str, Any]],
        matched_skills: List[str],
    ) -> str:
        blocks = []

        # 1. Cabecera (Nombre, Título, Contacto, Enlaces)
        header_lines = []
        if nombre:
            header_lines.append(f"# {nombre}")
        if titulo:
            header_lines.append(f"**{titulo}**")

        contact_parts = [p for p in [ciudad, email, telefono] if p]
        if contact_parts:
            header_lines.append(" | ".join(contact_parts))

        links = []
        if linkedin:
            links.append(f"[LinkedIn]({linkedin})")
        if github:
            links.append(f"[GitHub]({github})")
        if links:
            header_lines.append(" | ".join(links))

        if header_lines:
            blocks.append("\n".join(header_lines))

        # 2. Resumen / Perfil Profesional
        clean_sum = (summary or "").strip()
        if clean_sum:
            blocks.append(f"## Perfil Profesional\n{clean_sum}")

        # 3. Formación Académica
        form_list = self.profile.get("formacion", [])
        if form_list:
            form_lines = ["## Formación Académica"]
            for form in form_list:
                if isinstance(form, dict):
                    t = form.get("titulo", "")
                    inst = form.get("institucion", "")
                    fecha = form.get("fecha_fin", "")
                    if not t and not inst:
                        continue
                    form_lines.append(f"- **{t or 'Titulación'}**")
                    meta = " | ".join([p for p in [inst, fecha] if p])
                    if meta:
                        form_lines.append(f"  *{meta}*")
                    modulos = form.get("modulos_destacados", [])
                    if modulos and isinstance(modulos, list):
                        form_lines.append(f"  - Módulos clave: {', '.join(str(m) for m in modulos)}")
                elif isinstance(form, str) and form.strip():
                    form_lines.append(f"- {form.strip()}")
            if len(form_lines) > 1:
                blocks.append("\n".join(form_lines))

        # 4. Experiencia Laboral
        exp_list = self.profile.get("experiencia_laboral", [])
        if exp_list:
            exp_lines = ["## Experiencia Laboral"]
            for exp in exp_list:
                if isinstance(exp, dict):
                    puesto = exp.get("puesto", "")
                    empresa = exp.get("empresa", "")
                    periodo = exp.get("periodo", "")
                    if not puesto and not empresa:
                        continue
                    head = puesto or "Puesto"
                    exp_line = f"- **{head}**"
                    if empresa:
                        exp_line += f" — *{empresa}*"
                    if periodo:
                        exp_line += f" ({periodo})"
                    exp_lines.append(exp_line)
                    if exp.get("ubicacion"):
                        exp_lines.append(f"  *{exp.get('ubicacion')}*")
                    if exp.get("descripcion"):
                        exp_lines.append(f"  {exp.get('descripcion').strip()}")
                    techs_exp = exp.get("tecnologias", [])
                    if techs_exp:
                        exp_lines.append(f"  - Tecnologías: {', '.join(str(t) for t in techs_exp)}")
            if len(exp_lines) > 1:
                blocks.append("\n".join(exp_lines))

        # 5. Competencias Profesionales y Técnicas
        techs = self.profile.get("competencias_tecnicas", {})
        comp_lines = ["## Competencias Profesionales Destacadas"]
        if isinstance(techs, dict):
            for cat, items in techs.items():
                if isinstance(items, list) and items:
                    cat_label = cat.replace("_", " ").title()
                    clean_items = [item.get("nombre") if isinstance(item, dict) else str(item) for item in items if item]
                    if clean_items:
                        comp_lines.append(f"- **{cat_label}:** {', '.join(clean_items)}")
        elif isinstance(techs, list) and techs:
            comp_lines.append(f"- **Competencias Principales:** {', '.join(str(t) for t in techs if t)}")

        if matched_skills:
            comp_lines.append(f"- **Coincidencias clave con la vacante:** {', '.join(matched_skills)}")

        if len(comp_lines) > 1:
            blocks.append("\n".join(comp_lines))

        # 6. Proyectos Destacados
        if projects:
            proj_lines = ["## Proyectos Destacados (Selección Relevante)"]
            for p in projects:
                if isinstance(p, dict):
                    tech_list = p.get("tecnologias", [])
                    tech_str = ", ".join(str(t) for t in tech_list if t) if isinstance(tech_list, list) else str(tech_list)
                    proj_lines.append(f"### {p.get('nombre', 'Proyecto')}")
                    if tech_str:
                        proj_lines.append(f"*Tecnologías: {tech_str}*")
                    if p.get("descripcion"):
                        proj_lines.append(p.get("descripcion", "").strip())
                    for logro in p.get("logros", []):
                        if logro:
                            proj_lines.append(f"- {logro}")
            if len(proj_lines) > 1:
                blocks.append("\n".join(proj_lines))

        # 7. Idiomas
        idiomas = self.profile.get("idiomas", [])
        if idiomas:
            idi_lines = ["## Idiomas"]
            for idi in idiomas:
                if isinstance(idi, dict) and idi.get("idioma"):
                    idi_lines.append(f"- **{idi.get('idioma')}:** {idi.get('nivel', '')}")
                elif isinstance(idi, str) and idi.strip():
                    idi_lines.append(f"- {idi.strip()}")
            if len(idi_lines) > 1:
                blocks.append("\n".join(idi_lines))

        return "\n\n---\n\n".join(blocks).strip()
