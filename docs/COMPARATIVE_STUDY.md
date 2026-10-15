# Estudio Comparativo de Proyectos y Tecnologías para Búsqueda Automatizada de Empleo

Este documento recoge la investigación exhaustiva, el contraste con el código real, las dependencias, la viabilidad técnica y las decisiones de diseño para construir **lazyJobFinder**: un sistema autónomo, local y gratuito (0 €/mes) de búsqueda de empleo para un perfil junior de desarrollo de software (DAM) en España.

---

## 1. Análisis y Contraste de Proyectos Open Source

Se han analizado en profundidad los proyectos propuestos, contrastando sus capacidades reales frente a las necesidades del sistema:

| Proyecto | Repositorio / Stack | Conectores & Fuentes | Soporte España & Junior | Integración Ollama / Local | Generación CV / Carta | Notificaciones & Automatización | Facilidad Docker & Dependencias | Licencia & Mantenimiento |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **JobNavigator** | `vesaias/JobNavigator`<br>(FastAPI, React/Vite, Postgres, Caddy) | JobSpy (LinkedIn, Indeed, ZipRecruiter, Google) + 11 ATS endpoints (Workday, Greenhouse, etc.). | Bueno para agregadores globales. En España cubre LinkedIn/Indeed. Requiere filtrar por país en config. | Sí, soporta Ollama como backend además de OpenAI/Anthropic. | Sí, adapta CV y genera cartas mediante prompts en LLM. | Telegram integrado para alertas. Búsquedas programadas mediante cron interno. | **Muy pesado**: 4+ contenedores (Postgres, FastAPI backend, Vite frontend, Caddy, Playwright). Alto uso de RAM (~3-4 GB). | MIT. Activo y bien mantenido, pero diseñado como plataforma web visual completa. |
| **job_scout** | `SebasVA7X/job_scout` / variantes `santipalenque` (Python) | Scrapers básicos web o APIs como Serper / Remotive / YC Jobs. | Limitado en España. Muy enfocado a puestos remotos USA/Global. | Pobre o nulo por defecto: suele depender de APIs de pago como Anthropic (Claude) o OpenAI. | Cartas básicas generadas por prompts de agente. | Sin bot de Telegram estructurado (logs o dashboards web locales). | Scripts Python sueltos o contenedores ligeros. | MIT / Apache. Proyectos experimentales con baja cadencia de mantenimiento. |
| **jobsearch-mcp** | `TadMSTR/jobsearch-mcp`<br>(FastMCP, Python) | Adzuna, Remotive, WeWorkRemotely, USAJobs, Jobicy. Fallback a JobSpy opcional. | **Bajo en España**: USAJobs y Remotive no tienen oferta junior local española. Adzuna requiere API key comercial. | Integrado para embeddings (`bge-m3` en Ollama), pero el scoring y tailoring dependen obligatoriamente de Claude Haiku (Anthropic API). | Genera resúmenes estructurados y diferencias de CV (`tailor_resume`). No genera PDFs formateados listos para entrega. | Sin Telegram. Envía alertas por email SMTP (`job-watcher`). | Requiere Postgres 16, Qdrant, Valkey (Redis), y servidor MCP. 4 contenedores adicionales. | MIT. Muy bien estructurado como protocolo MCP, pero pensado para clientes tipo LibreChat/Claude Desktop. |
| **job-pipeline** | `Ayushman-Raghav/job-pipeline`<br>(Python/Airflow o scripts) | Scripts de scraping específicos para bolsas de empleo en India/EE.UU. | Nulo para el mercado español (InfoJobs, Tecnoempleo). | No optimizado para Ollama. | Plantillas estáticas sin personalización contextual por IA local. | Notificaciones básicas o logs. | Desigual, a menudo sin Docker Compose cerrado. | MIT. Repositorio académico / portafolio con escaso mantenimiento. |
| **JobOps** | `DaKheera47/job-ops`<br>(TypeScript, Node.js, SQLite, Python, Tectonic LaTeX) | Scraping de LinkedIn, Indeed, Glassdoor, Adzuna, Hiring Cafe, startup.jobs. | Aceptable a través de Indeed y LinkedIn España. Sin InfoJobs ni Tecnoempleo nativo. | Sí, admite Ollama o LM Studio junto a proveedores cloud. | **Excelente motor documental**: compila PDFs profesionales mediante Tectonic (LaTeX). | Webhooks y soporte inicial de bot de Telegram. Orientado principalmente a UI web. | Contenedor único con Node + Python + Tectonic. Relativamente pesado (~2 GB imagen). | MIT. Muy activo y con gran comunidad (800+ usuarios). |
| **JobSync** | `Gsync/jobsync`<br>(Next.js, Prisma, SQLite, Tailwind) | Agregación manual y escaneo asistido. | Neutro (depende de lo que introduzca el usuario). | Admite Ollama, DeepSeek y OpenAI. | Revisión y feedback de CV; no adapta y exporta PDFs terminados automáticamente en segundo plano. | No incluye bot de Telegram completo como interfaz exclusiva. | Docker Compose simple (Next.js + SQLite). | MIT. Es un panel de control / CRM personal para candidaturas, no un robot autónomo headless. |
| **JobSpy** *(Motor base)* | `cullenwatson/JobSpy`<br>(Python puro) | LinkedIn, Indeed, Glassdoor, Google Jobs, ZipRecruiter. | **Sobresaliente**: Soporta `country_indeed='spain'`, localización de ciudades españolas y filtros por horas (`hours_old`). | Es una librería de extracción pura: no interactúa con LLMs, se integra limpiamente con cualquier pipeline. | N/A (responsabilidad desacoplada). | N/A (responsabilidad desacoplada). | **Cero servicios externos**: librería Python instalable vía `pip`. Cero bases de datos obligatorias. | MIT. Mantenimiento muy activo por la comunidad. |

### Conclusiones y Decisión de Reutilización
1. **Descarte de arquitecturas web monolíticas**: *JobNavigator* y *JobOps* duplican servicios pesados (Next.js, React, Caddy, Postgres, Redis) diseñados para una interfaz gráfica que el usuario no desea utilizar.
2. **Reutilización del motor de extracción**: Adoptamos `python-jobspy`, pero **desacoplando cada portal individualmente** (Indeed, LinkedIn, Glassdoor, Google Jobs) para que el bloqueo de uno no cancele los demás.
3. **Reutilización del concepto de diferencias auditadas**: Adoptamos la técnica de *jobsearch-mcp* de registrar un JSON con los cambios precisos de adaptación del CV, pero asegurando el procesamiento 100% local en Ollama y la compilación directa a PDF con ReportLab.

---

## 2. Investigación de Tecnologías Especializadas

### A. REA — Reverse Engineer Anything (`morluto/rea` / `Opiuz/REA`)
- **Evaluación**: Diseñado para ingeniería inversa de binarios, APKs y análisis de tráfico de red privado mediante MCP.
- **Veredicto para producción**: **DESCARTADO**. Añadiría más de 3 GB de dependencias forenses (radare2, Ghidra, Java) sin aportar valor a un pipeline de empleo que ya cuenta con APIs oficiales (InfoJobs), sindicación abierta (Tecnoempleo RSS) y librerías de scraping probadas (JobSpy).

### B. RAG y Embeddings vs. Reglas Estructuradas + Prompting Directo
- **Evaluación**: Un currículum junior de DAM tiene ~1.000 tokens. Entra holgadamente en la ventana de contexto de modelos locales modernos (4k a 32k tokens).
- **Riesgos de RAG**: Bases vectoriales (Qdrant, Chroma) confunden semánticamente tecnologías distintas (Java vs. JavaScript) y añaden 1.5 GB de RAM para el motor vectorial y el modelo de embedding.
- **Veredicto**: **Adopción de Enfoque Híbrido Determinista + LLM Directo**:
  - Pre-filtro determinista por código que distingue requisitos obligatorios vs. deseables e indicios de seniority.
  - Inyección del perfil canónico completo inmutable.
  - Validación algorítmica estricta mediante `ProfileVerifier` para impedir que el LLM introduzca habilidades no documentadas.

### C. MCP (Model Context Protocol) vs. Código Python Determinista
- Para un servicio de ejecución programada diaria y entrega por Telegram, un loop agéntico de MCP es innecesario, impredecible y consume tokens excesivos en CPU. Un pipeline Python modular es robusto, testeable y directo.

---

## 3. Matriz de Privacidad y Costes

| Servicio / Conector | Coste Mensual | ¿Requiere Claves / Registro? | ¿Qué información sale del equipo? | Nivel de Riesgo de Fallo |
| :--- | :--- | :--- | :--- | :--- |
| **Tecnoempleo RSS** | 0 € | **No** (Público y abierto) | Petición HTTP GET con término de búsqueda (ej. `junior java`). Ningún dato personal. | Muy bajo. Si falla HTTP 500, se aísla sin interrumpir. |
| **InfoJobs API** | 0 € | **Sí** (Client ID/Secret gratuitos en `developer.infojobs.net`) | Petición HTTP GET con término de búsqueda. Ningún dato personal ni CV. | Nulo si está configurado; si faltan claves, se desactiva limpiamente. |
| **Indeed (JobSpy)** | 0 € | **No** | Término de búsqueda y ubicación España. | Bajo / Medio (posible rate-limit si se abusa). |
| **LinkedIn (JobSpy)** | 0 € | **No** | Término de búsqueda y ubicación España. | Medio (LinkedIn bloquea IPs si hay scraping agresivo; aislado por código). |
| **Glassdoor / Google** | 0 € | **No** | Término de búsqueda y ubicación España. | Bajo / Medio. |
| **Ollama (Docker)** | 0 € | **No** (100% local) | **Cero datos salen del equipo**. Todo el procesamiento de CV y cartas es local. | Nulo (funciona offline en el contenedor). |
| **Telegram Bot** | 0 € | **Sí** (Token de BotFather) | Mensajes y archivos PDF enviados directamente al chat privado del usuario. | Bajo (alta disponibilidad de la API de Telegram). |
