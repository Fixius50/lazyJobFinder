"""Renderizador tipográfico de documentos PDF ATS-friendly utilizando ReportLab con plantillas controladas."""

import html
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("lazyJobFinder.tailoring.pdf")


def clean_filename(name: str) -> str:
    """Sanitiza nombres de archivo para evitar caracteres no válidos en el sistema de archivos."""
    clean = re.sub(r"[^\w\s-]", "", name).strip().lower()
    return re.sub(r"[-\s]+", "_", clean)


class PDFRenderer:
    """
    Compila documentos en PDF pulidos mediante plantillas 100% controladas por código.
    El modelo LLM NO controla el diseño, la tipografía ni los márgenes.
    Conserva siempre el archivo Markdown editable original y el JSON de diferencias.
    """

    def __init__(self, base_output_dir: Optional[str] = None):
        self.output_dir = base_output_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "data",
            "documents",
        )
        os.makedirs(self.output_dir, exist_ok=True)

    def render_cv_and_letter(
        self,
        job: Dict[str, Any],
        cv_md: str,
        diff_audit: Dict[str, Any],
        letter_md: str,
    ) -> Dict[str, str]:
        """
        Renderiza tanto el CV adaptado como la carta de presentación, guardando:
        - PDF del CV
        - Markdown del CV (editable)
        - PDF de la Carta
        - Markdown de la Carta (editable)
        - JSON de Auditoría de diferencias (diff)
        """
        job_id = job.get("id", 0)
        company_clean = clean_filename(job.get("company", "empresa"))
        folder_name = f"{job_id}_{company_clean}"
        job_folder = os.path.join(self.output_dir, folder_name)
        os.makedirs(job_folder, exist_ok=True)

        cv_pdf_path = os.path.join(job_folder, f"CV_{company_clean}.pdf")
        cv_md_path = os.path.join(job_folder, f"CV_{company_clean}.md")
        letter_pdf_path = os.path.join(job_folder, f"Carta_{company_clean}.pdf")
        letter_md_path = os.path.join(job_folder, f"Carta_{company_clean}.md")
        diff_path = os.path.join(job_folder, "cambios_cv.json")

        # 1. Guardar archivos Markdown y auditoría JSON (el original base queda intacto en config/)
        with open(cv_md_path, "w", encoding="utf-8") as f:
            f.write(cv_md)

        with open(letter_md_path, "w", encoding="utf-8") as f:
            f.write(letter_md)

        with open(diff_path, "w", encoding="utf-8") as f:
            json.dump(diff_audit, f, ensure_ascii=False, indent=2)

        # 2. Compilar PDFs mediante la plantilla rígida ReportLab
        self._compile_markdown_to_pdf(cv_md, cv_pdf_path, title=f"CV - {job.get('company')}")
        self._compile_markdown_to_pdf(
            letter_md, letter_pdf_path, title=f"Carta de Presentación - {job.get('company')}"
        )

        logger.info("Documentos guardados en %s (PDFs y Markdown editables)", job_folder)

        return {
            "cv_pdf_path": cv_pdf_path,
            "cv_md_path": cv_md_path,
            "letter_pdf_path": letter_pdf_path,
            "letter_md_path": letter_md_path,
            "diff_path": diff_path,
            "folder": job_folder,
        }

    def _compile_markdown_to_pdf(self, md_content: str, output_pdf_path: str, title: str = "") -> None:
        """Parsea el contenido y aplica la plantilla tipográfica rígida de ReportLab."""
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
            from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer
        except ImportError:
            logger.error("ReportLab no está instalado. Creando archivo .txt de respaldo.")
            with open(output_pdf_path.replace(".pdf", ".txt"), "w", encoding="utf-8") as f:
                f.write(md_content)
            return

        doc = SimpleDocTemplate(
            output_pdf_path,
            pagesize=A4,
            leftMargin=50,
            rightMargin=50,
            topMargin=45,
            bottomMargin=45,
            title=title,
            author="lazyJobFinder",
        )

        styles = getSampleStyleSheet()

        # Plantilla tipográfica controlada 100% por código
        style_title = ParagraphStyle(
            "DocTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#1A202C"),
            spaceAfter=3,
        )

        style_subtitle = ParagraphStyle(
            "DocSubtitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#2B6CB0"),
            spaceAfter=3,
        )

        style_contact = ParagraphStyle(
            "DocContact",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#4A5568"),
            spaceAfter=8,
        )

        style_h2 = ParagraphStyle(
            "DocH2",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11.5,
            leading=15,
            textColor=colors.HexColor("#2D3748"),
            spaceBefore=8,
            spaceAfter=4,
            keepWithNext=True,
        )

        style_h3 = ParagraphStyle(
            "DocH3",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#1A202C"),
            spaceBefore=5,
            spaceAfter=2,
            keepWithNext=True,
        )

        style_body = ParagraphStyle(
            "DocBody",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13.5,
            textColor=colors.HexColor("#2D3748"),
            spaceAfter=5,
        )

        style_bullet = ParagraphStyle(
            "DocBullet",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13.5,
            textColor=colors.HexColor("#2D3748"),
            leftIndent=14,
            spaceAfter=3,
        )

        story = []
        lines = md_content.split("\n")

        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue

            if line.startswith("# "):
                text = line[2:].strip()
                story.append(Paragraph(html.escape(text), style_title))
            elif line.startswith("## "):
                text = line[3:].strip()
                story.append(
                    HRFlowable(
                        width="100%",
                        thickness=0.8,
                        color=colors.HexColor("#CBD5E0"),
                        spaceBefore=7,
                        spaceAfter=5,
                    )
                )
                story.append(Paragraph(html.escape(text), style_h2))
            elif line.startswith("### "):
                text = line[4:].strip()
                story.append(Paragraph(html.escape(text), style_h3))
            elif line.startswith("---"):
                pass
            elif line.startswith("- ") or line.startswith("* "):
                bullet_text = line[2:].strip()
                bullet_html = self._safe_md_to_html(bullet_text)
                story.append(Paragraph(f"• {bullet_html}", style_bullet))
            elif line.startswith("**") and " | " in line:
                contact_html = self._safe_md_to_html(line)
                story.append(Paragraph(contact_html, style_contact))
            else:
                body_html = self._safe_md_to_html(line)
                story.append(Paragraph(body_html, style_body))

            i += 1

        doc.build(story)

    def _safe_md_to_html(self, text: str) -> str:
        """
        Escapa caracteres XML para evitar que ReportLab falle con parse errors (&, <, >),
        y traduce selectivamente negritas y cursivas.
        """
        # 1. Extraer enlaces y convertirlos antes de escapar
        links = []
        def _save_link(m):
            links.append(m.group(1))
            return f"__LINK_{len(links)-1}__"

        text = re.sub(r"\[(.*?)\]\(.*?\)", _save_link, text)

        # 2. Escapar caracteres HTML básicos para seguridad de ReportLab
        escaped = html.escape(text)

        # 3. Restaurar enlaces como texto subrayado
        for idx, l_text in enumerate(links):
            escaped = escaped.replace(f"__LINK_{idx}__", f"<u>{html.escape(l_text)}</u>")

        # 4. Traducir negritas **texto** -> <b>texto</b>
        escaped = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", escaped)

        # 5. Traducir cursivas *texto* -> <i>texto</i>
        escaped = re.sub(r"\*(.*?)\*", r"<i>\1</i>", escaped)

        return escaped
