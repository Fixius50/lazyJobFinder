# Guia de Contexto Tecnico para Agentes de IA

Si eres un modelo de Inteligencia Artificial que trabaja en este repositorio, consulta las reglas detalladas del proyecto en:

- Reglas maestras: .agents/rules/project_rules.md
- Documento de arquitectura: docs/AI_SYSTEM_OVERVIEW.md

---

## Directrices Fundamentales

1. Coste 0 EUR/mes: No introduzcas dependencias ni llamadas a APIs de pago de IA (cero OpenAI, Anthropic, Claude o servicios cloud).
2. Inferencia Ollama en Docker: La inferencia se realiza 100% en local dentro del contenedor `lazyjob_ollama` mediante CPU cuantizada (Q4_K_M) con el modelo `qwen2.5:3b-instruct`.
3. Privacidad y Persistencia Soberana: Toda la evaluacion, deduplicacion y persistencia en SQLite WAL opera de forma local. El bot de Telegram es opcional y desacoplado.
4. Veracidad Factual por Codigo: Todo contenido generado debe verificarse algoritmicamente mediante `ProfileVerifier` (`src/tailoring/verifier.py`) contra `config/profile.yaml`. Se prohibe alucinar experiencia laboral comercial o tecnologias ausentes en el perfil.
5. Deduplicacion entre Portales: El esquema SQLite almacena `url_hash` y `content_fingerprint` (`src/database.py`) para evitar duplicados entre portales (ej. Indeed y LinkedIn).
6. Documentos Controlados: Los PDFs se generan mediante plantillas fijas en ReportLab (`src/tailoring/pdf_renderer.py`). El LLM jamas controla el layout ni el diseno visual. El CV base (`config/cv_base.md`) es estrictamente de solo lectura.
7. Aislamiento de Conectores: Cada portal de busqueda opera de forma independiente para que fallos de red o rate-limits en uno no cancelen las demas fuentes.
8. Arquitectura Frontend: Interfaz SPA fluida construida en Next.js con Tailwind CSS relativo, separacion lateral global de como maximo 5vw, modularizacion en `src/types/`, `src/components/ui/`, `src/components/features/` y `src/components/views/`. Uso de `InfoTooltip` para mantener cabeceras limpias sin parrafos redundantes.
9. Dualidad de Canales: El panel web local (FastAPI en puerto 8000 / Next.js en puerto 3000) es el centro de control principal. El bot de Telegram es un canal de entrega opcional que puede habilitarse o inhabilitarse desde los ajustes sin afectar a la web.
