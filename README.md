# lazyJobFinder 🚀

**Sistema local, gratuito (0 €/mes) y autónomo de búsqueda de empleo para desarrolladores junior (DAM).**

`lazyJobFinder` es una solución diseñada para ejecutarse en segundo plano dentro de **Docker Compose**, buscando ofertas de empleo en España, evaluando su compatibilidad técnica con tu formación real mediante un **modelo de lenguaje local (Ollama en Docker)**, adaptando tu currículum y redactando cartas de presentación sin inventar datos, y enviándote cada mañana un informe completo con los **documentos PDF adjuntos directamente a tu Telegram**.

---

## 🌟 Características Principales

- **Inferencia 100% Local (0 €/mes en IA)**: No utiliza APIs de IA de pago (cero OpenAI, Anthropic o servicios cloud de inferencia). Todo el análisis del CV, el scoring y la redacción se procesan en local dentro de Docker.
- **Canales de Notificación y Gestión Independientes**:
  - **Panel Web de Administración SPA (Next.js 14 + TypeScript)**: Interfaz moderna, fluida y con CSS 100% relativo (`rem`, `%`, `flex`, `grid`, `dvh`). Sin paneles laterales intrusivos ni recargas lentas de página; navegación instantánea por pestañas (Candidaturas, Búsqueda y CV, Servicios y Logs en vivo vía SSE, y Configuración). Opera con **cero llamadas a servicios externos**.
  - **Bot de Telegram (Opcional y Desacoplado)**: Notificaciones matutinas en el móvil con los PDFs adjuntos. *(Nota de privacidad: la entrega final por Telegram transmite los archivos a través de la infraestructura externa de Telegram)*. Puede desactivarse independientemente manteniendo el panel web 100% local.
- **Lanzador Unificado del Sistema (`start.bat`)**:
  - Script único nativo para Windows con menú interactivo (`choice` instantáneo) y flags directos por CLI (`--all`, `--docker`, `--web`, `--status`, `--pull`, `--stop`).
  - **Resolución dinámica de Docker Desktop**: Detecta rutas absolutas y relativas del ejecutable en el SO, inicia el servicio automáticamente si está apagado y bloquea la ejecución hasta que el motor de contenedores responde.
  - **Sincronización activa con el backend**: Espera activamente a que la API FastAPI en `http://127.0.0.1:8000/api/health` esté respondiendo antes de arrancar Next.js, eliminando errores de proxy `ECONNREFUSED`.
- **Extracción y Lectura Documental Multiformato (`cv_reader.py`)**:
  - Soporte nativo para currículums en **PDF** (usando `pypdf` con fallback heurístico por streams), **Markdown (.md)** y **Texto (.txt)** hasta 5 MB.
  - Previsualizador en pantalla en la interfaz web para inspeccionar exactamente qué texto extrae el motor antes de evaluar afinidad.
- **Conectores Multi-Fuente con Aislamiento de Fallos**:
  - **Tecnoempleo**: Canales RSS oficiales y abiertos especializados en IT en España (100% legal, 0 credenciales).
  - **InfoJobs**: Conexión con la API REST oficial de desarrolladores (`developer.infojobs.net`).
  - **JobSpy**: Agregación de **Indeed España**, **LinkedIn**, **Glassdoor** y **Google Jobs**, ejecutados en sub-bloques independientes para que el rate-limit de una fuente no interrumpa las demás.
- **Deduplicación Difusa Multi-Campo (`RapidFuzz`)**: Combina similitud ponderada de empresa, título, descripción y ubicación (≥85%) para enlazar duplicados entre portales (ej. Indeed y LinkedIn) sin eliminar registros, preservando el historial y registrando fuentes alternativas.
- **Salidas Estructuradas Nativas (Ollama + Pydantic v2)**: Utiliza esquemas JSON Schema (`model_json_schema()`) impuestos token a token por la gramática llama.cpp de Ollama, evitando dependencias pesadas y garantizando tipos y rangos estrictos (0-100).
- **Filtrado Inteligente (Obligatorio vs. Deseable)**: No descarta ofertas a ciegas por contener palabras como «senior» o «lead». Distingue si la palabra aparece en el puesto objetivo o como mención a compañeros de equipo, y separa requisitos obligatorios de deseables o valorables.
- **Garantía Anti-Alucinación por Código (`ProfileVerifier`)**: Mantiene un perfil canónico inmutable (`config/profile.yaml`) y el CV original intacto (`config/cv_base.md`). Opera con hechos atómicos aprobados: la IA solo puede seleccionar y ordenar hechos, sin inventar empresas, experiencia laboral comercial, titulaciones ni competencias. Si se detecta cualquier afirmación indebida, recurre de inmediato a la plantilla canónica certificada.
- **Seguridad en Profundidad (Prompt Shield & Rate Limit)**: Higienización heurística de descripciones externas no confiables (`<untrusted_job_description>`) para mitigar inyecciones de prompts; autorización estricta en Telegram (`allowed_user_id > 0`) y cooldown obligatorio de 5 minutos en `/buscar` para proteger los recursos del hardware.
- **Documentos Profesionales ATS-Friendly**: Compila PDFs limpios y sobrios con **ReportLab** siguiendo una plantilla tipográfica rígida controlada por código (el LLM jamás altera el diseño ni la maquetación). Conserva siempre los archivos Markdown editables y un registro `cambios_cv.json` de diferencias.
- **Persistencia y Esquema Unificado**: Base de datos SQLite con modo **WAL (Write-Ahead Logging)**, esquema canónico consolidado (`src/migrations/sql/schema.sql`), registro en `pipeline_runs`, recuperación de tareas interrumpidas por reinicios (`recover_interrupted_runs`) y recuperación matutina en el arranque (`catch-up`).

---

## 🏗 Arquitectura del Sistema

```
lazyJobFinder/
├── config/
│   ├── profile.yaml          # Perfil canónico inmutable (formación DAM, proyectos reales, stack)
│   ├── settings.yaml         # Configuración de búsqueda, ubicaciones, filtros y horarios
│   ├── shared_constants.json # Contrato unificado de estados, fuentes y umbrales (Front y Back)
│   └── cv_base.md            # Currículum base original inalterable
├── data/                     # Volumen persistente local
│   ├── documents/            # Carpetas organizadas con los PDFs, Markdown y diffs generados
│   ├── uploaded_cvs/         # Currículums subidos por el usuario (PDF/MD/TXT)
│   └── lazyjobfinder.db      # Base de datos SQLite (jobs, evaluaciones, documentos, runs, logs)
├── docs/                     # Documentación técnica completa
│   ├── AI_SYSTEM_OVERVIEW.md # Base de conocimiento exhaustiva para IAs y desarrolladores
│   ├── ARCHITECTURE.md       # Diseño de componentes, flujos y garantías de veracidad
│   ├── COMPARATIVE_STUDY.md  # Comparativa razonada de proyectos (JobNavigator, JobOps, MCP, etc.)
│   ├── HARDWARE_AMD_RX6600.md# Análisis de GPU AMD RX 6600, Docker WSL2 e inferencia CPU
│   ├── SOURCES_SPAIN.md      # Verificación de fuentes de empleo en España
│   └── SETUP_GUIDE.md        # Guía detallada de despliegue paso a paso
├── src/
│   ├── api/                  # API REST local (FastAPI en 127.0.0.1:8000)
│   │   ├── routes/           # Rutas modulares: system, cv, jobs, settings, maintenance
│   │   └── server.py         # Servidor FastAPI con streaming SSE y CORS local
│   ├── connectors/           # Conectores independientes (Tecnoempleo, InfoJobs, JobSpy)
│   ├── evaluator/            # Pre-filtro determinista, ProfileVerifier y cliente Ollama JSON
│   ├── migrations/           # Migrador transaccional y esquema canónico (schema.sql)
│   ├── tailoring/            # Adaptadores de CV/carta, cv_reader (PDF/MD/TXT) y PDF ReportLab
│   ├── telegram_bot/         # Bot interactivo de Telegram con autenticación estricta
│   ├── scheduler/            # Planificador APScheduler con prevención de solapamientos y catch-up
│   ├── shared_constants.py   # Vinculación Python del contrato unificado compartido
│   ├── database.py           # Persistencia SQLite WAL, deduplicación entre portales y runs
│   └── main.py               # Punto de entrada y orquestador de ciclo de vida
├── web/                      # Panel de Administración Web SPA (Next.js 14 + Tailwind CSS)
│   ├── src/app/              # Enrutador App de Next.js (Dashboard SPA centralizado)
│   ├── src/components/views/ # Vistas modulares fluidas: candidaturas, búsqueda/CV, docker, ajustes
│   └── src/lib/              # Cliente de API tipado y constantes sincronizadas
├── start.bat                 # Lanzador unificado todo en uno para Windows (interactivo y CLI)
├── docker-compose.yml        # Orquestación de Ollama (CPU cuantizada) y lazyJobFinder
├── Dockerfile                # Imagen Python 3.11 slim optimizada
└── requirements.txt          # Dependencias exactas verificadas (incluye pypdf)
```

---

## ⚡ Inicio Rápido (Despliegue Rápido o en 5 Pasos)

### Opción Rápida: Lanzador Único Todo en Uno (`start.bat`)
Haz doble clic en `start.bat` o ejecútalo desde el terminal:
```cmd
.\start.bat
```
El script comprueba requisitos (.env, Node.js, Docker), levanta los contenedores, verifica/descarga el modelo de Ollama, abre el navegador en `http://localhost:3000` e inicia el panel web.

---

### Despliegue Manual Paso a Paso:

### 1. Clonar el Repositorio y Configurar Variables
Copia el archivo de plantilla `.env.example` como `.env`:
```bash
cp .env.example .env
```

Configura tus credenciales en `.env`:
- `TELEGRAM_BOT_TOKEN`: Token obtenido de [@BotFather](https://t.me/BotFather).
- `TELEGRAM_ALLOWED_USER_ID`: Tu ID de Telegram obtenido de [@userinfobot](https://t.me/userinfobot) (garantiza acceso exclusivo).
- `OLLAMA_BASE_URL`: `http://ollama:11434`
- `OLLAMA_MODEL`: `qwen2.5:3b-instruct` (recomendado: 2 GB RAM, 30+ tokens/s en CPU).

### 2. Personalizar tu Perfil Profesional Real
Edita `config/profile.yaml` con tus datos de contacto, proyectos del ciclo DAM y competencias reales. El sistema usará estos datos como verdad absoluta.

### 3. Arrancar con Docker Compose
```bash
docker compose up -d
```

### 4. Descargar el Modelo Local de Ollama (Solo una vez)
Descarga el modelo ligero y optimizado en el volumen persistente de Docker:
```bash
docker exec -it lazyjob_ollama ollama pull qwen2.5:3b-instruct
```

### 5. Controlar desde Telegram (Opcional)
Abre tu bot en Telegram y envía `/start`.
- Puedes consultar el estado del sistema con `/estado`.
- Puedes lanzar un escaneo inmediato con `/buscar`.
- Cada mañana a la hora configurada (por defecto 08:30h), recibirás las ofertas del día junto a sus PDFs listos para enviar.

### 6. Acceder al Panel de Administración Web (Next.js)
El backend FastAPI arranca automáticamente en el puerto `8000` (`http://127.0.0.1:8000/api/docs`). Para iniciar la interfaz gráfica:
```bash
cd web
npm install
npm run dev
```
Abre tu navegador en `http://localhost:3000`:
- **Control**: Monitoriza la salud de Ollama y la app, arranca/detiene contenedores y revisa logs en vivo vía SSE.
- **Búsqueda y CV**: Sube un CV personalizado en PDF/MD/TXT (hasta 5 MB) sin alterar el perfil maestro y lanza búsquedas manuales con cerrojo anti-concurrencia.
- **Candidaturas**: Filtra y consulta ofertas de SQLite, visualiza el razonamiento del modelo y descarga tus CVs y cartas adaptadas en PDF.
- **Configuración**: Activa o desactiva de forma desacoplada la persistencia en interfaz y el bot de Telegram, edita términos de búsqueda y ejecuta tareas de mantenimiento seguro.

---

## 💻 Hardware: AMD Radeon RX 6600 & Windows WSL2

El entorno de trabajo utiliza Windows con Docker Desktop (WSL2) y una tarjeta gráfica **AMD Radeon RX 6600 (8 GB VRAM)**:
- **Realidad técnica**: AMD ROCm no ofrece compatibilidad oficial para GPUs de consumo RDNA 2 (Navi 23 / gfx1032) dentro de contenedores WSL2 en Windows, debido a la falta de mapeo del controlador de fusión `/dev/kfd` en el kernel virtual de Docker Desktop.
- **Estrategia adoptada**: El contenedor Ollama se ejecuta de forma predeterminada mediante **inferencia cuantizada en CPU (Q4_K_M)** con el modelo `qwen2.5:3b-instruct`.
- **Rendimiento estimado**: En un procesador multinúcleo x86 moderno, la inferencia en CPU alcanza entre **25 y 40 tokens/segundo**. Evaluar una oferta toma ~3-5 segundos y generar los documentos ~12 segundos. Un lote diario de 5 ofertas se completa en menos de 2 minutos sin saturar la máquina ni requerir drivers experimentales.

---

## 🔒 Matriz de Costes y Privacidad

| Operación | Destino de los Datos | ¿Qué sale del equipo? | Coste Mensual |
| :--- | :--- | :--- | :--- |
| **Búsqueda de Ofertas** | Tecnoempleo RSS, InfoJobs, Indeed, LinkedIn | Términos de búsqueda (ej. `junior java`) y ubicación `Spain`. **Cero datos personales**. | **0 €** |
| **Evaluación y Scoring** | Contenedor local `ollama` | **Nada**. Todo el procesamiento ocurre en localhost dentro de Docker. | **0 €** |
| **Adaptación de CV / Carta** | Contenedor local `ollama` y ReportLab | **Nada**. Los archivos PDF y Markdown se guardan en el disco local `./data/documents`. | **0 €** |
| **Notificaciones y Documentos** | API externa de Telegram | Mensaje de resumen y PDFs transmitidos cifrados por HTTPS a través de servidores de Telegram a tu chat privado. | **0 €** |

---

## 📄 Licencia

Este proyecto está bajo la licencia [MIT](LICENSE).
