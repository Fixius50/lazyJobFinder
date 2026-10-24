# Guia de Contexto Tecnico para Agentes de IA

Si eres un modelo de Inteligencia Artificial que trabaja en este repositorio, consulta las reglas maestras detalladas del proyecto en:

- Reglas maestras: .agents/rules/project_rules.md
- Documento de arquitectura: docs/AI_SYSTEM_OVERVIEW.md

---

## Directrices Fundamentales

1. Coste 0 EUR/mes: No introduzcas dependencias ni llamadas a APIs comerciales de pago de IA (cero OpenAI, Anthropic, Claude o servicios cloud). Inferencia 100% local con Ollama (`qwen2.5:3b-instruct` en CPU Q4_K_M).
2. Sistema 100% Global y Agnóstico de Profesión: Prohibido categorizar o filtrar por sectores ("tecnología vs no tecnología"). El sistema es universal para cualquier oficio (mozo de almacén, fontanero, sanitario, administrativo, hostelería, transporte, informática, etc.).
3. Cero Plantillas Fijas ni Perfiles Impuestos: `config/profile.yaml` y `config/settings.yaml` no contienen datos de desarrollador prefijados ni términos fijos. La única fuente de verdad es el CV activo que el usuario sube o selecciona.
4. Dinamismo Autónomo según CV Activo: Al subir o elegir un CV, el sistema extrae automáticamente mediante IA los términos reales de búsqueda laboral y los sincroniza con el motor de descubrimiento.
5. Comportamiento Sin CV: Si no hay CV activo, los filtros laterales se ocultan y no se lanzan búsquedas en portales hasta que se aporte un currículum.
6. Fuentes Globales Activas por Defecto: Se priorizan portales universales para todos los sectores (JobSpy con Indeed, LinkedIn, Glassdoor, Google Jobs e InfoJobs). Portales exclusivos de un único sector (ej. Tecnoempleo) permanecen desactivados por defecto.
7. Veracidad Factual por Código: `ProfileVerifier` valida algorítmicamente contra el texto real del CV activo aportado. Jamás inventar titulaciones, maquinaria o experiencia ausente.
8. UX Fluida y Mantenimiento Directo: Controles de CV unificados en una sola línea en la cabecera. El vaciado de historial opera con modal directo de confirmación (sin requerir escribir frases de texto).
9. Auto-Recarga en Caliente: El backend vigila cambios en `src/` y reinicia el proceso automáticamente.
10. Prohibición de Testeo por Navegador: Jamás utilizar subagentes de navegador automatizado para testeo del sistema.
11. Ciclo de Vida de CVs Desacoplado: Búsqueda únicamente al subir nuevo CV; cambio de CV en el desplegable no relanza llamadas externas; eliminación en cascada de ofertas en SQLite.
12. Centralización Estricta de `__pycache__`: Todo el bytecode reside exclusivamente en `.cache/pycache/` (`PYTHONPYCACHEPREFIX` y `sitecustomize.py`). Cero carpetas `__pycache__` en el árbol de código.
13. UI con Unidades Relativas y Alias `@/...`: En Tailwind/CSS solo unidades relativas (`text-2xs`, `text-3xs`, `rem`, `em`, `clamp()`). Cero `px` arbitrarios (`text-[10px]`, `text-[11px]`). Importaciones frontend exclusivamente con alias `@/...` sin rutas relativas (`./`, `../`).
14. Cero Archivos Puente o Redundantes: Prohibidos archivos pasarela dedicados a re-exportar, re-importar o redirigir rutas estáticamente.
15. CSS Moderno y Centralizado: `globals.css` utiliza variables fluidas, `clamp()`, `color-mix()`, `@supports (backdrop-filter: ...)` y `@media (prefers-reduced-motion)`.
16. Cero Mocks o Fallbacks Silenciosos: Comunicación directa y verídica con FastAPI y SQLite local. Si un servicio cae, mostrar el error real de forma transparente para permitir reintento.
17. SPA de Página Única y Terminal en Modal: La app se centra exclusivamente en "Candidaturas" en `/`. El monitoreo de contenedores Docker y pipeline se abre mediante modal interactivo (`TerminalLogsDialog`) desde la cabecera.

