# lazyJobFinder

Sistema local, autonomo y gratuito (0 EUR/mes) de busqueda, evaluacion de afinidad ATS y adaptacion de candidaturas de empleo para desarrolladores de software.

lazyJobFinder se ejecuta localmente mediante contenedores Docker. Escanea multiples portales de empleo en Espana, deduplica las ofertas, evalua su afinidad tecnica mediante un modelo de lenguaje local (Ollama) sin enviar datos a APIs externas de pago, genera documentos PDF adaptados y centraliza todo en un panel web interactivo y notificaciones opcionales en Telegram.

---

## Caracteristicas del Sistema

- Inferencia 100% Local (Coste 0 EUR/mes): Evaluacion, scoring y redaccion procesados integramente en tu equipo con Ollama (`qwen2.5:3b-instruct` en CPU Q4_K_M). Cero dependencias de OpenAI, Anthropic o servicios cloud de pago.
- Multi-Portal con Aislamiento de Fallos: Conectores independientes para Tecnoempleo (RSS oficial), InfoJobs (API de desarrolladores) y JobSpy (Indeed Espana, LinkedIn, Glassdoor y Google Jobs). Si un portal falla o aplica rate-limit, los demas continuan sin interrupcion.
- Deduplicacion Inteligente: Algoritmo difuso basado en RapidFuzz (`url_hash` y `content_fingerprint`) que detecta y agrupa vacantes duplicadas publicadas en multiples plataformas.
- Garantia Anti-Alucinacion: El generador contrasta estrictamente cada oferta con tu perfil real (`config/profile.yaml`). No inventa empresas ni competencias inexistentes. Si faltan tecnologias exigidas, las penaliza en el scoring y las lista de forma transparente.
- Documentos PDF Profesionales: Compilacion rigida con ReportLab (`pdf_renderer.py`). El modelo LLM no altera el diseno ni el formato visual del PDF. El CV base (`config/cv_base.md`) permanece inmutable como lectura canonica.
- Base de Datos SQLite en modo WAL: Persistencia transaccional local con Write-Ahead Logging para lecturas y escrituras concurrentes de alta velocidad.
- Panel Web SPA Unificado: Interfaz grafica moderna en Next.js con Tailwind CSS relativo, separacion de pantalla fluida (maximo 5vw), filtros deslizantes de puntuacion, selector de modalidad (presencial, teletrabajo o hibrido), subida y previsualizacion de CV, monitorizacion Docker y consola de logs en vivo por Server-Sent Events (SSE).
- Canal Telegram Desacoplado: Opcion de recibir alertas matutinas con los PDFs adjuntos en el movil, sin dependencia obligatoria del bot para operar el sistema.

---

## Requisitos Previos

1. Docker Desktop instalado y en ejecucion (con motor WSL2 en Windows).
2. Git instalado.
3. Node.js 18+ y npm (requerido unicamente si deseas ejecutar el panel web en modo desarrollo en el puerto 3000; no es necesario si usas el modo unificado de Docker en el puerto 8000).

---

## Como Arrancarlo

### Paso 1: Clonar y configurar variables de entorno

Clona el repositorio y genera tu archivo `.env` a partir de la plantilla:

```bash
cp .env.example .env
```

Edita `.env` con tus preferencias basicas. Las credenciales de Telegram o InfoJobs son opcionales; si no las configuras, el sistema funcionara en modo 100% local a traves del panel web.

```ini
# Configuracion minima opcional
DATABASE_PATH=data/lazyjobfinder.db
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:3b-instruct

# Opcional: Telegram (dejar vacio si solo usas el panel web)
TELEGRAM_BOT_TOKEN=
TELEGRAM_ALLOWED_USER_ID=
```

---

### Paso 2: Ejecucion en Windows con el lanzador `start.bat`

El repositorio incluye el script `start.bat`, disenado para automatizar la deteccion de Docker Desktop, arrancar contenedores, sincronizar puertos y abrir la interfaz.

#### Opcion A: Modo Interactivo (Recomendado)
Haz doble clic en `start.bat` o ejecutalo en tu terminal:

```cmd
.\start.bat
```

Se mostrara un menu numerado donde podras elegir la opcion deseada:
- `[1]` Arrancar TODO unificado: Levanta Ollama, la base de datos y la aplicacion web lista en `http://localhost:8000`.
- `[2]` Arrancar solo Docker: Levanta los servicios en segundo plano sin abrir terminales adicionales.
- `[3]` Arrancar Panel Web en Modo Desarrollo: Inicia Next.js en `http://localhost:3000` con hot-reload.
- `[4]` Diagnostico de estado: Comprueba la conexion de Docker, Ollama y el backend FastAPI.
- `[5]` Descargar modelo IA: Descarga el modelo `qwen2.5:3b-instruct` en Ollama.
- `[6]` Detener servicios: Apaga todos los contenedores de manera limpia.
- `[7]` Reconstruir y Actualizar TODO: Recompila el panel web (Next.js) a estatico y reconstruye la imagen Docker del backend sin cache para aplicar cambios recientes.

#### Opcion B: Comandos Directos por Linea de Comandos (CLI)
Puedes invocar las acciones directamente con flags:

```cmd
# Arrancar todo el sistema unificado
.\start.bat --all

# Reconstruir y actualizar frontend y backend con los ultimos cambios de codigo
.\start.bat --build

# Arrancar unicamente los contenedores Docker
.\start.bat --docker

# Iniciar el panel web de desarrollo en puerto 3000
.\start.bat --web

# Verificar estado y conectividad de los servicios
.\start.bat --status

# Descargar o actualizar el modelo en Ollama
.\start.bat --pull

# Detener todos los contenedores
.\start.bat --stop
```

---

### Paso 3: Ejecucion Manual en Linux o Mac (Docker Compose)

Si trabajas en Linux o macOS, puedes arrancar el entorno mediante Docker Compose directamente:

```bash
# 1. Levantar contenedores en segundo plano
docker compose up -d

# 2. Descargar el modelo de IA en el contenedor de Ollama
docker compose exec ollama ollama pull qwen2.5:3b-instruct

# 3. Comprobar que el servicio responde
curl http://localhost:8000/api/health
```

Accede a la interfaz web en tu navegador en:
`http://localhost:8000`

---

## Puertos y Direcciones del Sistema

- `http://localhost:8000`: Panel Web de Administracion y API REST de FastAPI (produccion y Docker unificado).
- `http://localhost:8000/api/docs`: Documentacion interactiva Swagger / OpenAPI del backend.
- `http://localhost:3000`: Servidor de desarrollo Next.js (unicamente al ejecutar `start.bat --web` o `npm run dev`).
- `http://localhost:11434`: Motor de inferencia Ollama local.

---

## Estructura del Proyecto

```
lazyJobFinder/
├── .agents/                  # Reglas del proyecto para agentes y desarrollo
│   └── rules/
│       └── project_rules.md  # Normas de arquitectura, anti-alucinacion y frontend
├── config/
│   ├── profile.yaml          # Perfil profesional canónico (habilidades y proyectos reales)
│   ├── settings.yaml         # Parametros de busqueda, umbrales y programacion
│   ├── shared_constants.json # Contrato unificado de estados y portales
│   └── cv_base.md            # Curriculo base de referencia (solo lectura)
├── data/                     # Volumen persistente local
│   ├── documents/            # Carpetas con los PDFs y Markdown generados
│   ├── uploaded_cvs/         # CVs alternativos subidos desde la interfaz
│   └── lazyjobfinder.db      # Base de datos SQLite WAL
├── docs/                     # Documentacion tecnica en profundidad
├── src/
│   ├── api/                  # Backend FastAPI (rutas de jobs, cv, system, settings)
│   ├── connectors/           # Conectores de empleo (Tecnoempleo, InfoJobs, JobSpy)
│   ├── evaluator/            # Scoring ATS y cliente estructurado Ollama JSON
│   ├── scheduler/            # Planificador APScheduler con recuperacion de ejecuciones
│   ├── tailoring/            # Renderizador PDF ReportLab y lector de CV multiformato
│   ├── telegram_bot/         # Bot opcional de notificaciones Telegram
│   ├── database.py           # Gestor SQLite con deduplicacion difusa
│   └── main.py               # Orquestador principal de procesos
├── web/                      # Frontend Next.js 14 + Tailwind CSS
│   ├── src/app/              # Dashboard SPA principal y paginas estaticas
│   ├── src/components/
│   │   ├── ui/               # Primitivas visuales (botones, badges, tooltips)
│   │   ├── features/         # Componentes organizados por dominio (jobs, services, cv)
│   │   └── views/            # Vistas principales integradas
│   ├── src/lib/              # Cliente de API y utilidades
│   └── src/types/            # Tipos e interfaces TypeScript estructurados
├── start.bat                 # Lanzador de inicio rapido multifuncion para Windows
├── docker-compose.yml        # Orquestacion de contenedores Docker
└── Dockerfile                # Imagen Docker optimizada para Python 3.11
```

---

## Flujo de Trabajo y Uso Diario

1. Abre el panel web en `http://localhost:8000` (o `http://localhost:3000` en desarrollo).
2. Pestana Candidaturas:
   - Visualiza ofertas encontradas, puntuacion de afinidad y estado.
   - Ajusta el slider de afinidad minima (`0% a 100%`) para filtrar ofertas aptas.
   - Filtra por modalidad: Presencial, Teletrabajo (100% Remoto) o Hibrido.
   - Sube o cambia tu CV activo en el panel lateral; el sistema calculara la afinidad contra el CV seleccionado.
   - Previsualiza y descarga los PDFs adaptados de CV y carta generados por ReportLab.
3. Pestana Configuracion y Servicios:
   - Configura terminos de busqueda, ubicaciones, filtros de exclusion y umbrales minimos.
   - Monitorea el estado de Ollama y de la aplicacion en tiempo real.
   - Revisa la consola de logs en vivo transmitida por SSE sin recargar la pagina.
   - Ejecuta limpiezas de historial con confirmacion protegida cuando desees reiniciar las ofertas.
4. Boton Escanear Ahora: Ubicado en la cabecera superior para disparar el pipeline de busqueda bajo demanda en cualquier momento.
