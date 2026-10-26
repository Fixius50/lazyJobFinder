"""Tests para el validador de perfil y extractor de competencias (ProfileVerifier).

Valida que:
1. Extrae competencias técnicas y profesionales de formatos estructurados (bloques clave: valor, listas con comas, etc.).
2. No descarta habilidades reales de candidatos ni se queda vacío ante formatos sin viñetas.
"""

import unittest
from src.tailoring.verifier import ProfileVerifier


class TestProfileVerifier(unittest.TestCase):
    def test_skills_extraction_from_key_value_blocks(self):
        """Verifica la extracción de competencias en formato de categoría con dos puntos y comas."""
        cv_text = """
        Roberto Monedero
        Valdemoro (Madrid)
        Técnico Superior en Desarrollo de Aplicaciones Multiplataforma (DAM)

        APTITUDES E IDIOMAS
        Desarrollo backend: Java, Spring Boot, Node.js, NestJS, PHP, APIs REST y microservicios.
        Desarrollo frontend: React, TypeScript, JavaScript, HTML5 y CSS3.
        Desarrollo móvil: Android con Java.
        Bases de datos e integración: SQL, MySQL, Oracle PL/SQL, NoSQL, Redis, Postman.
        Sistemas y herramientas: AWS, Docker, Git, GitHub, Linux, Windows.

        EDUCACIÓN
        2023 - 2026 | Grado Superior DAM
        """

        verifier = ProfileVerifier({}, cv_text=cv_text)
        skills = verifier.allowed_skills

        # Comprobar que se han extraído las tecnologías nucleares
        self.assertIn("java", skills)
        self.assertIn("spring boot", skills)
        self.assertIn("react", skills)
        self.assertIn("typescript", skills)
        self.assertIn("docker", skills)
        self.assertIn("sql", skills)
        self.assertIn("mysql", skills)
        self.assertIn("git", skills)

    def test_skills_extraction_universal_for_other_sectors(self):
        """Verifica la universalidad para perfiles de otros sectores (ej. logística o sanidad)."""
        cv_logistica = """
        Juan Pérez
        Mozo de almacén y logística

        COMPETENCIAS Y HABILIDADES
        Maquinaria: carretilla elevadora, traspaleta eléctrica, apilador.
        Herramientas: pistola de radiofrecuencia, SAP Logística, lectores de códigos de barras.
        Prevención: PRL básico, manipulación manual de cargas.
        """

        verifier = ProfileVerifier({}, cv_text=cv_logistica)
        skills = verifier.allowed_skills

        self.assertIn("carretilla elevadora", skills)
        self.assertIn("traspaleta eléctrica", skills)
        self.assertIn("sap logística", skills)

    def test_validate_matched_skills_filters_noise(self):
        """Verifica que validate_matched_skills filtre palabras vacías y acepte habilidades del CV."""
        cv_text = "Experiencia con React, Python y Docker en Madrid."
        verifier = ProfileVerifier({}, cv_text=cv_text)

        claimed = ["React", "Python", "Madrid", "Docker", "InexistenteTecnologia"]
        matched = verifier.validate_matched_skills(claimed)

        self.assertIn("React", matched)
        self.assertIn("Python", matched)
        self.assertIn("Docker", matched)
        self.assertNotIn("Madrid", matched, "Ciudades no deben considerarse competencias.")
        self.assertNotIn("InexistenteTecnologia", matched, "Habilidades ausentes del CV no deben validarse.")


if __name__ == "__main__":
    unittest.main()
