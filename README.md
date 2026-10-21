# lazyJobFinder

> **Buscador autónomo, local y gratuito (0 €/mes) de ofertas de empleo con IA y Telegram para cualquier profesional.**

**lazyJobFinder** se ejecuta de forma autónoma en tu propio ordenador mediante contenedores Docker. Escanea múltiples portales de empleo en España (Tecnoempleo, InfoJobs, Indeed, LinkedIn, Glassdoor y Google Jobs), deduplica ofertas repetidas, evalúa su afinidad mediante un modelo de lenguaje local (Ollama) sin enviar datos personales a APIs externas de pago, adapta cartas de presentación y centraliza todo en un panel web moderno con notificaciones opcionales por Telegram.

---

## ✨ Características Principales

- **Inferencia IA 100% Local (Coste 0 €/mes):** Evaluación, scoring y redacción procesados íntegramente en tu equipo con Ollama (`qwen2.5:3b-instruct` en CPU Q4_K_M). Cero dependencias de OpenAI, Anthropic o servicios cloud de pago.
- **Universal para Cualquier Profesión:** Admite cualquier tipo de currículum y carrera laboral (tecnología, administración, marketing, diseño, salud, educación, etc.).
- **Modo Cero Filtro o Filtro Inteligente:**
  - **Sin CV activo:** El sistema conserva **todas** las ofertas descubiertas sin descartes para que no te pierdas ninguna vacante.
  - **Con CV activo (PDF, Markdown o TXT):** La IA evalúa la afinidad contra tu experiencia real, asigna una puntuación del 0 al 100 y genera documentos ATS adaptados.
- **Multi-Portal con Aislamiento de Fallos:** Conectores independientes para Tecnoempleo (RSS oficial), InfoJobs (API oficial) y JobSpy (Indeed España, LinkedIn, Glassdoor y Google Jobs). Si un portal falla o aplica rate-limit, los demás continúan sin interrupción.
- **Deduplicación Inteligente:** Algoritmo difuso basado en RapidFuzz (`url_hash` y `content_fingerprint`) que detecta y agrupa vacantes idénticas publicadas en diferentes portales.
- **Garantía Anti-Alucinación:** No inventa empresas ni competencias inexistentes. Si faltan requisitos exigidos, los detecta con honestidad y los expone transparentemente.
- **Documentos Profesionales:** Compilación de cartas de presentación y CV adaptados mediante plantillas fijas y ReportLab, asegurando maquetación cuidada.
- **Panel Web Unificado en http://localhost:8000:** Interfaz visual completa desarrollada en Next.js y servida directamente por el backend FastAPI:
  - Filtros interactivos por afinidad y modalidad (Remoto, Híbrido, Presencial).
  - Gestor de CV con subida local (PDF, MD, TXT), borrado y previsualización del texto extraído.
  - Monitorización en tiempo real de servicios (Docker y Ollama) y consola de logs en vivo vía SSE.
  - Configuración rápida de términos de búsqueda, ubicaciones y umbrales.
- **Canal Telegram Desacoplado:** Opción de recibir alertas matutinas en el móvil con los documentos adjuntos, sin ser obligatorio para operar el sistema.
- **Sistema de Empaquetado y Distribución:** Generador automatizado de instaladores para **Windows** (`.exe` y `.zip` portable) y **GNU/Linux** (`.run` ejecutable y `.tar.gz`) con auditoría de seguridad previa y verificación SHA-256.

---

## 📋 Requisitos del Sistema

1. **Docker Desktop** (en Windows con motor WSL2) o **Docker Engine + Docker Compose v2** (en Linux).
2. **Mínimo 4 GB de RAM** disponibles para contenedores Docker.
3. **Mínimo 8 GB de espacio en disco** para imágenes y modelos de IA locales.

---

## 🚀 Inicio Rápido en Windows (`start.bat`)

El proyecto incluye un lanzador simplificado [`start.bat`](./start.bat) que automatiza todo:

Haz doble clic en `start.bat` o ejecútalo en la terminal:

```cmd
.\start.bat
```

Se abrirá el menú unificado:

```text
=====================================================================
                lazyJobFinder - Lanzador Principal
       Sistema Local, Autónomo y Gratuito de Búsqueda de Empleo
=====================================================================

Selecciona qué deseas ejecutar:

  [1] Arrancar lazyJobFinder (Todo unificado en http://localhost:8000)
  [2] Empaquetar Distribución e Instaladores (Windows y Linux)
  [Q] Salir (Detiene los servicios en ejecución)
```

### ¿Qué hace la Opción [1]?
1. Comprueba y crea tu archivo `.env` automáticamente si falta.
2. Inicia Docker Desktop si estaba cerrado y espera a que el motor esté listo.
3. Levanta los contenedores en segundo plano.
4. Comprueba si el modelo `qwen2.5:3b-instruct` ya existe en Ollama; si ya está, **no lo vuelve a descargar**.
5. Espera a que el backend responda y abre automáticamente tu navegador en **`http://localhost:8000`**.
6. Al pulsar cualquier tecla en la consola o pulsar `[Q]`, **detiene automáticamente todos los contenedores** para no consumir memoria.

---

## 🐧 Inicio en GNU/Linux y macOS

Si utilizas Linux o macOS, puedes arrancarlo mediante Docker Compose estándar:

```bash
# 1. Preparar archivo de entorno
cp .env.example .env

# 2. Levantar los contenedores en segundo plano
docker compose up -d

# 3. Descargar el modelo de IA en Ollama (solo la primera vez)
docker compose exec ollama ollama pull qwen2.5:3b-instruct

# 4. Abrir en el navegador
xdg-open http://localhost:8000 || open http://localhost:8000
```

---

## 💼 Cómo Adaptarlo a tu Perfil

lazyJobFinder se adapta a cualquier profesional en dos sencillos pasos:

### 1. Términos de Búsqueda
En la pestaña **Ajustes** del panel web (o editando [`config/settings.yaml`](./config/settings.yaml)), indica los puestos y ubicaciones que te interesan:
```yaml
busqueda:
  terminos:
    - "Diseñador Gráfico"
    - "Marketing Digital"
  ubicaciones:
    - "Spain"
    - "Remoto"
  antiguedad_horas: 48
  limite_por_fuente: 15
```

### 2. Cargar tu Currículum
1. Ve a la sección **Currículum Activo** en el panel web.
2. Pulsa el botón **Subir CV** y selecciona tu archivo (`.pdf`, `.md` o `.txt`).
3. El sistema extraerá el texto de forma segura y local.
4. Selecciona tu CV en el desplegable. A partir de ese momento, la IA evaluará las ofertas contrastándolas con tu currículum real.
5. *¿Prefieres no filtrar?* Deja seleccionado **"Sin CV (Sin filtrado de ofertas)"** y se guardarán todas las ofertas descubiertas.

---

## 📦 Empaquetado y Creación de Instaladores

lazyJobFinder cuenta con un orquestador completo para generar distribuciones independientes para usuarios finales:

```cmd
# Desde Windows con start.bat
.\start.bat --package

# O directamente con Python
python packaging/build_release.py
```

### Opciones del empaquetador:
- `--platform {all,windows,linux}`: Elige la plataforma de destino.
- `--version 1.0.0`: Define la versión semántica.
- `--skip-docker`: Genera los paquetes de scripts e instaladores sin compilar las imágenes Docker.
- `--skip-model`: Genera paquetes ligeros dejando la descarga del modelo para el primer arranque del usuario.

### Artefactos generados en `dist/`:
- **Windows:** Instalador guiado Inno Setup (`.exe`) y paquete portable (`.zip`) con instalador autónomo `install.bat`.
- **Linux:** Instalador ejecutable autoextraíble (`.run`) y tarball (`.tar.gz`) con instalador interactivo `installer.sh`.
- **Aislamiento Estricto por Proyecto:** Cada instalación genera y mantiene su propio identificador único `COMPOSE_PROJECT_NAME`, asegurando que redes, volúmenes y contenedores no interfieran entre instalaciones concurrentes.
- **Auditoría Profunda de Seguridad:** Inspección recursiva de las capas internas de Docker (`layer.tar`), verificación exhaustiva de los blobs del modelo Ollama contra el manifiesto y validación criptográfica de ida y vuelta de `SHA256SUMS.txt`.
- **Garantía Anti-Fuga:** Las imágenes se construyen desde un contexto aislado con plantillas limpias, impidiendo que tus credenciales o CV personales se empaqueten en la distribución.

---

## 🧭 Puertos y Direcciones Locales

| Servicio | URL | Descripción |
| :--- | :--- | :--- |
| **Panel Web Unificado** | `http://localhost:8000` | Interfaz gráfica SPA de control y gestión |
| **Documentación API** | `http://127.0.0.1:8000/api/docs` | Swagger interactivo de FastAPI |
| **Motor Ollama** | `http://localhost:11434` | API de inferencia de modelos IA locales |
| **Panel Dev (Opcional)** | `http://localhost:3000` | Entorno de desarrollo Next.js con hot-reload (`npm run dev`) |

---

## 📁 Estructura del Repositorio

```
lazyJobFinder/
├── config/                   # Configuración activa del usuario (settings, perfil)
├── data/                     # Base de datos SQLite, CVs subidos y documentos (excluido de git)
├── docs/                     # Documentación técnica y guías de arquitectura
├── packaging/                # Infraestructura de empaquetado e instaladores
│   ├── build_release.py      # Orquestador maestro de builds
│   ├── compose.release.yaml  # Docker Compose de producción para usuarios
│   ├── config-templates/     # Plantillas limpias sin datos personales
│   ├── windows/              # Scripts e instalador Inno Setup para Windows
│   └── linux/                # Scripts e instalador autoextraíble para Linux
├── src/                      # Código fuente del backend Python (FastAPI, conectores, IA)
│   ├── api/                  # Endpoints REST (jobs, cv, settings, system)
│   ├── connectors/           # Conectores multi-portal (Tecnoempleo, InfoJobs, JobSpy)
│   ├── evaluator/            # Scoring universal y cliente de Ollama
│   ├── scheduler/            # Planificador diario de ejecuciones
│   └── tailoring/            # Extractor multiformato de CV y generador de cartas
├── web/                      # Frontend Next.js 14 + Tailwind CSS
├── dist/                     # Paquetes e instaladores generados listos para distribuir
├── Dockerfile                # Imagen optimizada con frontend pre-integrado
├── docker-compose.yml        # Orquestador Docker local para desarrollo
└── start.bat                 # Lanzador rápido unificado para Windows
```

---

## 🛡️ Privacidad y Seguridad

1. **100% Local:** Tus currículums, datos personales y notas jamás se envían a servidores de terceros ni a modelos de IA en la nube.
2. **Puertos enlazados a 127.0.0.1:** La API y los servicios se vinculan estrictamente a localhost para evitar exposición en redes locales o públicas.
3. **Cero Telemetría:** Sin recopilación de métricas, cookies de seguimiento ni dependencias ocultas.
