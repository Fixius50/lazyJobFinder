# lazyJobFinder

> **Buscador autónomo, local y gratuito (0 €/mes) de ofertas de empleo con IA local y alertas opcionales para cualquier perfil profesional.**

**lazyJobFinder** se ejecuta de forma autónoma en tu propio equipo mediante contenedores Docker. Escanea múltiples portales de empleo en España (LinkedIn, Indeed, Glassdoor, Google Jobs, InfoJobs y Tecnoempleo), deduplica vacantes repetidas, evalúa su afinidad mediante un modelo de lenguaje local (Ollama) sin enviar jamás tus datos personales a servicios cloud de pago, redacta cartas de presentación a medida y centraliza todo en un panel web moderno con notificaciones opcionales por Telegram.


## 🛡️ Privacidad y Seguridad

1. **100% Local:** Tus currículums, datos personales y notas jamás se envían a servidores externos ni a modelos de IA en la nube.
2. **Puertos enlazados a 127.0.0.1:** La API y los servicios se vinculan estrictamente a localhost para evitar exposición en redes locales o públicas.
3. **Cero Telemetría:** Sin recopilación de métricas, cookies de seguimiento ni rastreo de terceros.

---

## ✨ Características Principales

- 🤖 **Inteligencia Artificial 100% Local (0 €/mes sin costes ocultos)**: Todo el procesamiento (análisis del CV, puntuación de afinidad laboral y redacción de cartas de presentación) se ejecuta directamente en tu ordenador con Ollama (`qwen2.5:3b-instruct` cuantizado en CPU Q4_K_M). Cero suscripciones mensuales, cero claves de pago (OpenAI, Claude o Gemini) y cero fugas de datos personales a la nube.
- 🎯 **Universal para Cualquier Sector y Profesión**: 100% neutral y sin sesgos artificiales. Diseñado tanto para logística, almacén, transporte, sanidad, administración y hostelería, como para diseño, educación, ventas, oficios técnicos o tecnología. La IA analiza las competencias reales que figuren en tu currículum sin encasillarte.
- ⚡ **Extracción Única y Caché en SQLite (`cv_cache`)**: Sube tu currículum en formato PDF, TXT o Markdown. El texto se extrae e indexa una única vez y queda persistido en la base de datos local SQLite (`data/lazyjobfinder.db`). Sin archivos residuales en disco, con previsualización inmediata y comprobaciones de afinidad instantáneas.
- 🔄 **Dinamismo Inteligente según tu CV**:
  - **Sin CV activo:** El panel se mantiene limpio y ordenado con una guía orientativa, ocultando filtros irrelevantes y sin lanzar búsquedas a ciegas.
  - **Con CV activo:** El sistema extrae automáticamente las palabras clave de empleo adecuadas a tu perfil y contrasta las vacantes contra tu experiencia y formación real.
- 🔍 **Rastreo Multi-Portal con Deduplicación Inteligente**: Explora las plataformas de empleo más utilizadas del mercado (Indeed España, LinkedIn, Glassdoor, Google Jobs e InfoJobs API). Su algoritmo difuso (RapidFuzz) detecta y unifica ofertas idénticas publicadas a la vez en varios sitios para que nunca veas vacantes repetidas.
- ⚖️ **Scoring Objetivo y Garantía Anti-Alucinaciones**: Evalúa de 0 a 100 la compatibilidad del puesto respecto a los requisitos obligatorios y valorables de la oferta. No inventa empresas ni competencias que no tengas; si faltan requisitos, te lo indica con total transparencia.
- ✍️ **Cartas de Presentación y Documentación Adaptada**: Genera automáticamente cartas de motivación personalizadas para cada vacante, respetando tus fortalezas reales y listas para descargar en Markdown o PDF profesional limpio.
- 💻 **Panel Web Todo-en-Uno (http://localhost:8000)**: Interfaz gráfica ágil desarrollada en Next.js y servida por FastAPI:
  - Barra de control de CV compacta e integrada en la cabecera (selector rápido, previsualizador de texto, subida y eliminación).
  - Vaciado de historial rápido con modal de confirmación directo.
  - Filtros instantáneos por afinidad (Excelente, Buena, Media) y modalidad laboral (Remoto, Híbrido, Presencial).
  - Consola de logs y monitor de salud de servicios en tiempo real vía Server-Sent Events (SSE).
- 🔥 **Auto-Recarga en Caliente (Hot-Reload)**: Modifica código en `src/` y el backend se reinicia automáticamente en memoria en milisegundos sin reiniciar contenedores Docker.
- 📱 **Canal Telegram Desacoplado**: Recibe opcionalmente un resumen matutino con las mejores ofertas del día y los documentos adjuntos en tu teléfono móvil.
- 📦 **Instaladores Autónomos y Portabilidad**: Paquetes de instalación listos para usar en **Windows** e instaladores ejecutables para **GNU/Linux**.

---

## 📦 Instalación y Uso para Usuarios Finales (Sin Programar)

Si no eres programador o solo quieres probar la aplicación en tu equipo, **no necesitas instalar Python, Node.js ni configurar dependencias**.

### 1. Requisito Único
- **Docker Desktop** (en Windows/macOS) o **Docker Engine + Docker Compose v2** (en Linux) instalado y abierto.  
  *(Si no lo tienes, descárgalo gratis desde [docker.com](https://www.docker.com/products/docker-desktop/)).*

---

### 2. Pasos para Probar en Windows
1. Descarga el paquete **lazyJobFinder-1.0.0-windows-x64.zip** desde [GitHub Releases](https://github.com/Fixius50/lazyJobFinder/releases).
2. Descomprímelo en cualquier carpeta de tu ordenador (por ejemplo, en tu Escritorio o Documentos).
3. Haz doble clic en **launch.bat** (o ejecuta install.bat la primera vez).
4. **El script se encarga de todo de forma automática:**
   - Detecta si Docker Desktop está abierto (si no, te avisa claramente con instrucciones).
   - Prepara el entorno seguro y aislado.
   - Descarga los contenedores oficiales y el modelo de IA local (qwen2.5:3b-instruct) la primera vez.
   - En cuanto todo esté listo, **abrirá tu navegador automáticamente en http://localhost:8000**.
5. Para detener el sistema al terminar, haz doble clic en **stop.bat** o cierra la terminal.

---

### 3. Pasos para Probar en GNU/Linux
1. Descarga **lazyJobFinder-1.0.0-linux-x64.tar.gz** (o el instalador autoextraíble .run) desde [GitHub Releases](https://github.com/Fixius50/lazyJobFinder/releases).
2. Descomprime y accede a la carpeta:
`ash
tar -xzf lazyJobFinder-1.0.0-linux-x64.tar.gz
cd lazyJobFinder-1.0.0-linux-x64
`
3. Ejecuta el script de inicio:
`ash
chmod +x launch.sh stop.sh installer.sh
./launch.sh
`
4. El script configurará los servicios y abrirá tu navegador en http://localhost:8000. Para apagarlo, ejecuta ./stop.sh.

---

## 🛠️ Cómo Compilar los Paquetes Tú Mismo (Desarrolladores)

Todo el código para compilar tus propios paquetes está en [packaging/](./packaging):
- [packaging/build_release.py](./packaging/build_release.py): Orquestador maestro que audita el código, valida las capas y genera los paquetes finales.
- [packaging/windows/](./packaging/windows): Scripts de Windows (installer.iss, install.bat, launch.bat, stop.bat).
- [packaging/linux/](./packaging/linux): Scripts de GNU/Linux (installer.sh, launch.sh, stop.sh).

Para compilar los instaladores localmente:
`cmd
# Desde Windows usando el menú de start.bat (Opción [2]):
.\start.bat 2

# O invocando directamente el orquestador Python:
python packaging/build_release.py --skip-docker --skip-model
`
*(Los paquetes generados se depositan automáticamente en la carpeta local dist/ junto con sus hashes SHA256SUMS.txt).*

---

## 📋 Requisitos del Sistema

1. **Docker Desktop** (en Windows con backend WSL2) o **Docker Engine + Docker Compose v2** (en Linux).
2. **Mínimo 4 GB de memoria RAM** disponibles para contenedores Docker.
3. **Mínimo 8 GB de espacio libre en disco** para imágenes de Docker y el modelo local de IA.

---

## 🚀 Inicio Rápido en Windows (`start.bat`)

El proyecto incluye un lanzador simplificado [`start.bat`](./start.bat) que automatiza todo el ciclo de vida:

Haz doble clic en `start.bat` o ejecútalo en tu terminal:

```cmd
.\start.bat
```

Se abrirá el menú interactivo unificado:

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
2. Inicia Docker Desktop si estaba cerrado y espera a que el motor esté operativo.
3. Levanta los contenedores en segundo plano.
4. Comprueba si el modelo `qwen2.5:3b-instruct` ya existe en Ollama; si ya está descargado, **no gasta ancho de banda volviéndolo a descargar**.
5. Espera a que el backend esté listo y abre automáticamente tu navegador en **`http://localhost:8000`**.
6. Al pulsar cualquier tecla en la consola o pulsar `[Q]`, **detiene ordenadamente todos los contenedores** para liberar la memoria RAM.

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

## 💼 Cómo Usarlo con tu Perfil

lazyJobFinder no requiere editar archivos YAML ni configurar plantillas complejas:

### 1. Cargar tu Currículum en el Panel Web
1. Abre **`http://localhost:8000`** en tu navegador.
2. En la barra superior, pulsa el botón **Subir CV** y selecciona tu archivo (`.pdf`, `.md` o `.txt`).
3. El sistema extrae el texto, lo guarda en la caché de SQLite y detecta automáticamente las palabras clave óptimas para tu búsqueda de empleo.
4. Puedes pulsar el botón del ojo para previsualizar el texto extraído que utilizará la IA.

### 2. Personalizar Ajustes de Búsqueda (Opcional)
- Desde la pestaña **Ajustes** del panel web, puedes afinar los términos de búsqueda, ubicaciones (ej. *"Madrid"*, *"Remoto"*, *"España"*), antigüedad de las ofertas (horas) y el límite de resultados por portal.
- Toda la configuración se guarda de forma persistente y transparente en la base de datos SQLite (`data/lazyjobfinder.db`).

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
├── data/                     # Base de datos SQLite (lazyjobfinder.db) y CVs subidos (excluido de git)
├── docs/                     # Documentación técnica, arquitectura y guías de hardware
├── packaging/                # Infraestructura de empaquetado y creador de instaladores
│   ├── build_release.py      # Orquestador maestro de builds y auditoría de seguridad
│   ├── compose.release.yaml  # Docker Compose de producción para distribución
│   ├── windows/              # Scripts e instalador Inno Setup para Windows (.exe, .zip)
│   └── linux/                # Scripts e instalador autoextraíble para Linux (.run, .tar.gz)
├── dist/                     # Carpeta de salida con los instaladores generados localmente (excluida de git)
├── src/                      # Código fuente del backend Python (FastAPI, conectores, IA)
│   ├── __init__.py           # Único __init__.py centralizado con exportaciones perezosas (PEP 562)
│   ├── models.py             # Modelos canónicos Pydantic V2 (Fuente Única de Verdad)
│   ├── database.py           # Gestor SQLite con PRAGMAs en memoria, sqlite-utils y FTS5
│   ├── api/                  # Endpoints REST (jobs, cv, settings, system)
│   ├── connectors/           # Conectores multi-portal (LinkedIn, Indeed, InfoJobs, Glassdoor, etc.)
│   ├── evaluator/            # Scoring universal, anti-alucinación y cliente Ollama
│   ├── scheduler/            # Planificador diario de ejecuciones
│   └── tailoring/            # Extractor con caché SQLite, validador de CV y cartas de presentación
├── web/                      # Frontend Next.js 14 + Tailwind CSS (SPA)
├── Dockerfile                # Imagen optimizada con frontend estático pre-integrado
├── docker-compose.yml        # Orquestador Docker local para desarrollo
└── start.bat                 # Lanzador rápido interactivo para Windows
```

---

