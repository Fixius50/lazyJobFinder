# Contributing Guide

Gracias por tu interés en contribuir a **lazyJobFinder**.

## Stack Tecnológico

- **Backend**: Python 3.11+, FastAPI, Pydantic V2, SQLite, sqlite-utils, ReportLab.
- **Motor IA**: Ollama (`qwen2.5:3b-instruct` cuantizado en CPU Q4_K_M).
- **Frontend**: Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS, Leaflet.
- **Infraestructura**: Docker & Docker Compose.

## Normas del Proyecto

Antes de enviar cualquier aportación, consulta obligatoriamente [`.agents/rules/project_rules.md`](../.agents/rules/project_rules.md):
1. **Universalidad Total**: El sistema debe permanecer 100% agnóstico al oficio o carrera profesional del candidato. Queda prohibido introducir sesgos artificiales hacia ningún sector.
2. **Inferencia Local a Coste Cero (0 €/mes)**: Prohibido introducir APIs cloud de pago (OpenAI, Claude, etc.).
3. **Bytecode Centralizado**: Todo el bytecode de Python se agrupa exclusivamente en `src/__pycache__/`.
4. **Punto de Entrada Unificado**: `src/__init__.py` es el único `__init__.py` del backend con importaciones perezosas (PEP 562).

## Flujo de Desarrollo Local

1. Clona el repositorio:
   ```bash
   git clone https://github.com/robermonal/lazyJobFinder.git
   cd lazyJobFinder
   ```
2. Ejecuta el entorno completo con el lanzador interactivo:
   ```cmd
   start.bat
   ```
3. Ejecuta la suite de pruebas unitarias dentro del contenedor:
   ```bash
   docker exec lazyjob_app python -m unittest discover tests
   ```

