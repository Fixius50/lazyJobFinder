# MEMORIA TÉCNICA DEL PROGRAMA DE ORDENADOR

**Título de la obra:** lazyJobFinder  
**Autor:** Roberto Monedero Alonso  
**Tipo de obra:** Programa de ordenador (Software)  
**Carácter:** Obra inédita (no divulgada con anterioridad a la presente solicitud)  

---

## 1. Breve descripción del programa

lazyJobFinder es un sistema informático autónomo de ámbito local y de coste cero destinado a la búsqueda, extracción, agregación, deduplicación, evaluación de afinidad curricular mediante inteligencia artificial local y redacción automatizada de documentos laborales personalizados (currículum vitae y cartas de motivación) para cualquier categoría o perfil profesional del mercado laboral.

El programa realiza las siguientes funciones nucleares:
1. **Descubrimiento y extracción de ofertas:** Rastreo concurrente y estructurado en portales de empleo de ámbito nacional (LinkedIn, Indeed, Glassdoor, Google Jobs, InfoJobs y Tecnoempleo).
2. **Deduplicación multifactor:** Algoritmos de normalización de URLs (url_hash), huella digital semántica canónica (content_fingerprint) y cotejo de similitud difusa mediante distancia de Levenshtein (RapidFuzz).
3. **Evaluación de afinidad mediante IA local soberana:** Integración con modelos de lenguaje locales ejecutados en CPU bajo el motor Ollama (qwen2.5:3b-instruct), analizando de forma estricta las competencias acreditadas en el currículum del usuario sin alucinación ni transmisión de datos externos.
4. **Motor documental tipográfico:** Generación y maquetación algorítmica de documentos PDF ATS-friendly y Markdown mediante la biblioteca tipográfica ReportLab.
5. **Persistencia y gestión de estado:** Almacenamiento relacional local sobre SQLite optimizado con auto-migración dinámica, índice de búsqueda full-text FTS5 y caché de extracción.
6. **Interfaz de usuario web SPA:** Panel de control de página única desarrollado con Next.js y Tailwind CSS con filtros multicriterio en tiempo real, geolocalización y visor de logs.

---

## 2. Lenguajes de programación

- **Python 3.11:** Lógica de backend, conectores de red, persistencia en base de datos, integración con motor LLM y renderizado tipográfico de documentos PDF.
- **TypeScript / JavaScript (ES2022+):** Lógica del cliente web, gestión de estado reactivo y llamadas a la API REST.
- **SQL (Dialecto SQLite):** Definición de esquemas, consultas relacionales, agregaciones analíticas e indexación full-text FTS5.
- **HTML5 y CSS3 (Tailwind CSS):** Estructura y presentación visual de la interfaz de usuario.
- **Shell Scripting (Batch / Bash):** Automatización de orquestación, arranque y empaquetado (.bat para Windows y .sh para entornos UNIX).

---

## 3. Entorno operativo y de ejecución

- **Sistemas operativos compatibles:** Microsoft Windows 10/11 (64-bit), GNU/Linux (kernel 5.x o superior en distribuciones x86_64 y aarch64) y macOS (12 o superior).
- **Entorno de ejecución / Runtime:** Python 3.11+, Node.js 18+ (para transpilación estática), Docker Engine 24+ y Docker Compose v2.
- **Arquitectura de hardware mínima:** CPU x86_64 o ARM64 con soporte de instrucciones AVX2/NEON, 4 GB de memoria RAM y 2 GB de almacenamiento disponible.

---

## 4. Diagrama de flujo del sistema

[Inicio / Temporizador o Petición Manual]
        │
        ▼
[Extracción de CV Activo] ──► [Caché SQLite cv_cache]
        │
        ▼
[Descubrimiento en Portales de Empleo] (JobSpy, InfoJobs API, Tecnoempleo)
        │
        ▼
[Filtro de Deduplicación] ──► (Hash URL + Huella semántica + RapidFuzz)
        │
        ├─ ¿Oferta ya existe? ──► [Actualizar trazabilidad / Omitir]
        ▼
[Inserción de Ofertas Nuevas en SQLite (tabla jobs)]
        │
        ▼
[Motor de Scoring e Inferencia IA Local (Ollama - CPU)]
        │
        ▼
[Evaluación ATS JSON] (Puntuación 0-100, fortalezas, carencias, fit_level)
        │
        ├─ ¿Afinidad >= Umbral (65%)?
        │       ├─ SÍ ──► [Generación de CV y Carta adaptada PDF/MD con ReportLab]
        │       │             │
        │       │             ▼
        │       │       [Registro en tabla generated_documents]
        │       │             │
        │       │             ▼
        │       │       [Notificación Telegram opcional con adjuntos]
        │       │
        │       └─ NO ──► [Registro de puntuación y marcado descartado]
        ▼
[Presentación en Interfaz Web SPA (http://localhost:8000)]
        │
        ▼
[Fin del ciclo de ejecución]

---

## 5. Listado de ficheros del código fuente

lazyJobFinder/
├── src/                    (Código fuente del backend: FastAPI, IA local, SQLite y conectores)
├── web/                    (Código fuente del frontend: SPA en Next.js, React y Tailwind CSS)
├── tests/                  (Batería completa de pruebas unitarias y de integración)
├── packaging/              (Scripts de despliegue, empaquetado e instalación para Windows y Linux)
├── docs/                   (Documentación técnica, manual de arquitectura y memoria de registro)
├── docker-compose.yml      (Orquestación multi-contenedor de servicios y motor LLM local)
├── Dockerfile              (Especificación de compilación de la imagen del contenedor)
├── start.bat               (Lanzador automatizado interactivo de un solo clic para Windows)
├── sitecustomize.py        (Configuración de entorno de ejecución y caché unificada de bytecode)
├── CITATION.cff            (Metadatos formales de autoría y citación del software)
├── LICENSE                 (Términos legales de licenciamiento Mozilla Public License 2.0)
└── README.md               (Guía general de arquitectura, instalación y uso)