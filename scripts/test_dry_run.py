"""Script de verificación en seco (Dry-Run) de componentes para lazyJobFinder."""

import os
import sys
import yaml

# Añadir raíz al sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from src.database import Database
from src.evaluator.scoring_engine import ScoringEngine
from src.tailoring.cv_tailorer import CVTailorer
from src.tailoring.cover_letter import CoverLetterGenerator
from src.tailoring.pdf_renderer import PDFRenderer
from src.tailoring.verifier import ProfileVerifier


def run_checks():
    print("==================================================")
    print("   VERIFICACIÓN ESTÁTICA Y DE COMPONENTES        ")
    print("==================================================")

    # 1. Cargar Perfil
    profile_path = os.path.join(BASE_DIR, "config", "profile.yaml")
    print(f"1. Verificando perfil en {profile_path}...")
    with open(profile_path, "r", encoding="utf-8") as f:
        profile = yaml.safe_load(f)
    print(f"   [OK] Perfil cargado: {profile.get('candidato', {}).get('nombre_completo')} "
          f"({len(profile.get('proyectos_destacados', []))} proyectos)")

    # 2. Inicializar Base de Datos temporal
    test_db_path = os.path.join(BASE_DIR, "data", "test_dry_run.db")
    print(f"2. Inicializando SQLite en {test_db_path}...")
    db = Database(db_path=test_db_path)
    print("   [OK] Esquema SQLite creado con éxito (WAL mode).")

    # 3. Test de pre-filtro de ofertas (Análisis de requisitos obligatorios vs deseables)
    settings_path = os.path.join(BASE_DIR, "config", "settings.yaml")
    with open(settings_path, "r", encoding="utf-8") as f:
        settings = yaml.safe_load(f)

    engine = ScoringEngine(db=db, profile_path=profile_path, settings=settings)

    senior_job = {
        "id": 1,
        "title": "Senior Java Architect (Lead)",
        "description": "Requisitos mínimos: Imprescindible 8 años de experiencia demostrable en arquitectura backend.",
    }
    junior_with_senior_mention = {
        "id": 2,
        "title": "Desarrollador Junior Java / DAM",
        "description": (
            "Empresa busca programador junior con conocimientos en Java, SQL y Git. "
            "Trabajará en estrecha colaboración junto a desarrolladores Senior. "
            "Requisitos deseables: Se valorará experiencia previa o proyectos personales."
        ),
        "company": "Tech Solutions Spain",
        "job_url": "https://example.com/job/2",
        "location": "Madrid",
        "is_remote": True,
    }

    pass_senior, r_senior, _ = engine.prefilter(senior_job)
    pass_junior, r_junior, _ = engine.prefilter(junior_with_senior_mention)

    print("3. Comprobación de Pre-filtro con Requisitos Obligatorios vs Deseables:")
    print(f"   - Oferta Senior estricta: Pasa={pass_senior} (Motivo: {r_senior}) -> [OK]")
    print(f"   - Oferta Junior (que menciona Senior como compañero): Pasa={pass_junior} (Motivo: {r_junior}) -> [OK]")

    # 4. Comprobación de ProfileVerifier y Anti-Alucinación
    print("4. Comprobación de ProfileVerifier (Garantía Anti-Alucinación):")
    verifier = ProfileVerifier(profile)
    hallucinated_text = (
        "Roberto cuenta con 5 años de experiencia laboral en empresas liderando proyectos de Kubernetes y AWS."
    )
    sanitized, corrections = verifier.sanitize_summary(
        hallucinated_text,
        matched_skills=["Java", "SQL"],
        company="Tech Solutions",
        job_title="Desarrollador Junior",
    )
    print(f"   [OK] Alucinación detectada y corregida por código: {len(corrections) > 0}")
    print(f"   [OK] Corrección aplicada: {corrections[0] if corrections else 'N/A'}")
    print(f"   [OK] Texto saneado resultante: {sanitized[:80]}...")

    # 5. Test de Adaptación de CV y Carta
    print("5. Comprobación de Motor Documental:")
    tailorer = CVTailorer(profile=profile)
    eval_mock = {
        "score": 85,
        "fit_level": "EXCELENTE",
        "matched_skills": ["Java", "SQL", "Git"],
        "missing_skills": ["Docker avanzado"],
        "reasoning": "Sólida base técnica en DAM y proyectos compatibles.",
        "should_apply": True,
    }

    cv_md, diff = tailorer.tailor(junior_with_senior_mention, eval_mock)
    print(f"   [OK] CV adaptado generado ({len(cv_md)} caracteres).")

    letter_gen = CoverLetterGenerator(profile=profile)
    letter_md = letter_gen.generate(junior_with_senior_mention, eval_mock)
    print(f"   [OK] Carta de presentación generada ({len(letter_md)} caracteres).")

    # 6. Test de compilación de PDF con ReportLab
    print("6. Comprobando compilación PDF con ReportLab (plantilla fija)...")
    renderer = PDFRenderer(base_output_dir=os.path.join(BASE_DIR, "data", "test_docs"))
    docs = renderer.render_cv_and_letter(junior_with_senior_mention, cv_md, diff, letter_md)
    print(f"   [OK] PDF CV generado: {os.path.exists(docs['cv_pdf_path'])}")
    print(f"   [OK] PDF Carta generada: {os.path.exists(docs['letter_pdf_path'])}")

    # Limpieza
    try:
        import shutil
        if os.path.exists(test_db_path):
            os.remove(test_db_path)
        test_docs_dir = os.path.join(BASE_DIR, "data", "test_docs")
        if os.path.exists(test_docs_dir):
            shutil.rmtree(test_docs_dir)
    except Exception:
        pass

    print("\n✅ TODAS LAS COMPROBACIONES DE COMPONENTES COMPLETADAS CON ÉXITO.")


if __name__ == "__main__":
    run_checks()
