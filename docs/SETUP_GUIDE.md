# Guía de Instalación y Despliegue: lazyJobFinder (0 €/mes)

Esta guía explica paso a paso cómo poner en marcha **lazyJobFinder** en tu equipo con Windows y Docker Desktop, utilizando tu bot de Telegram como interfaz de control diario y ejecutando la IA 100% en local dentro de Docker.

---

## 1. Requisitos Previos

1. **Docker Desktop para Windows** instalado y en ejecución (con backend WSL2 activado).
2. **Conexión a Internet** para la primera descarga de las imágenes Docker, el modelo de Ollama y la búsqueda de ofertas.
3. **Una cuenta de Telegram**.

---

## ⚡ Método Rápido Automatizado: Lanzador `start.bat` (Recomendado en Windows)

Si estás en Windows, puedes iniciar todo el sistema con un solo comando o haciendo doble clic sobre [`start.bat`](../start.bat):

```cmd
.\start.bat
```

Presenta un menú simplificado y directo:
- **`[1] Arrancar lazyJobFinder`**: 
  1. Comprueba y crea `.env` automáticamente si no existe.
  2. Arranca Docker Desktop si estaba cerrado y espera a que el motor esté listo.
  3. Levanta los contenedores con Compose.
  4. Comprueba si el modelo local `qwen2.5:3b-instruct` ya existe en Ollama (si ya está, no gasta ancho de banda volviéndolo a descargar).
  5. Espera a que la API esté lista y abre tu navegador en `http://localhost:8000`.
  6. Al presionar cualquier tecla en la ventana o pulsar `Q`, detiene automáticamente los contenedores liberando la memoria RAM.
- **`[2] Empaquetar Distribución e Instaladores`**: Ejecuta la suite de distribución (`packaging/build_release.py`) con auditoría de seguridad previa para crear instaladores de Windows y Linux.
- **`[Q] Salir`**: Detiene los contenedores y sale limpiamente.

---

## 2. Paso 1: Configurar tu Búsqueda y Perfil

lazyJobFinder es **universal**: no está limitado al sector tecnológico, sino que sirve para cualquier disciplina (marketing, administración, diseño, educación, salud, programación, etc.).

1. **Desde la Web (`http://localhost:8000`)**:
   - Ve a la pestaña **Currículum Activo**, pulsa **Subir CV** y carga tu currículum en PDF, Markdown o TXT. El sistema extraerá y previsualizará el texto.
   - Si no subes un CV o seleccionas *"Sin CV"*, el sistema mantendrá todas las ofertas descubiertas sin descartar ninguna.
   - En la pestaña **Ajustes**, ajusta tus palabras clave de búsqueda y ubicaciones deseadas.
2. **Desde los archivos de configuración (Opcional)**:
   - Puedes editar `config/settings.yaml` para afinar términos de búsqueda, ubicaciones, horarios de ejecución y exclusiones.
   - Puedes completar `config/profile.yaml` con tus datos estructurados si deseas mayor fidelidad en cartas de presentación.

---

## 3. Paso 2: Crear tu Bot de Telegram y Obtener Credenciales (Opcional)

Si deseas recibir notificaciones matutinas en el móvil con los PDFs generados:

1. Abre Telegram y busca el contacto oficial **@BotFather**.
2. Envía el comando `/newbot`.
3. Sigue las instrucciones: elige un nombre visible (ej. `Mi Asistente de Empleo`) y un nombre de usuario que termine en `bot` (ej. `mi_empleo_bot`).
4. **Guarda el Token**: BotFather te responderá con un token HTTP similar a `7123456789:AAH...v8Z`. Este es tu `TELEGRAM_BOT_TOKEN`.
5. **Obtener tu Chat ID personal**:
   - En Telegram, busca el bot **@userinfobot** y pulsa *Iniciar*.
   - Te responderá con tu `Id` numérico (ej. `123456789`). Este es tu `TELEGRAM_ALLOWED_USER_ID`.
   - *Importante*: Abre una conversación con tu nuevo bot recién creado y pulsa *Iniciar* (`/start`) para que el bot tenga permiso para contactarte.

---

## 4. Paso 3: Configurar las Variables de Entorno

En la raíz del proyecto `lazyJobFinder`, el archivo `.env` se crea automáticamente a partir de `.env.example`. Puedes editarlo:

```ini
# Configuración de Telegram (Opcional - dejar vacío si solo se usa el panel web)
TELEGRAM_BOT_TOKEN=tu_token_aqui_obtenido_de_botfather
TELEGRAM_ALLOWED_USER_ID=tu_id_numerico_de_usuario

# Configuración de Ollama (en Docker)
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=qwen2.5:3b-instruct

# Horario de Ejecución Diaria Automática (formato 24h)
SCHEDULE_HOUR=08
SCHEDULE_MINUTE=30

# Umbral Mínimo de Puntuación para Notificar (0 a 100)
MIN_SCORE_THRESHOLD=65

# Opcional: InfoJobs API (developer.infojobs.net)
# Si se deja en blanco, el sistema utiliza Tecnoempleo RSS, Indeed, LinkedIn, Glassdoor y Google
INFOJOBS_CLIENT_ID=
INFOJOBS_CLIENT_SECRET=
```

---

## 5. Paso 4: Arrancar Manualmente con Docker Compose (Linux/macOS o CLI)

Si no utilizas `start.bat`:

```bash
# 1. Iniciar los contenedores
docker compose up -d

# 2. Descargar el modelo de IA en Ollama (solo la primera vez)
docker compose exec ollama ollama pull qwen2.5:3b-instruct

# 3. Acceder al panel web
# Navega a http://localhost:8000
```

---

## 6. Paso 5: Uso Diario

### Panel Web Unificado (`http://localhost:8000`)
- **Candidaturas**: Listado con filtros, puntuación de afinidad, justificación de la IA, requisitos que cumples y faltan, y enlaces a la vacante original.
- **Currículum Activo**: Carga, borrado y previsualización de CVs con selector dinámico.
- **Servicios y Logs**: Monitor en vivo de contenedores y consola de logs por SSE.
- **Ajustes**: Configuración ágil de parámetros de búsqueda.

### Telegram (Si está configurado)
- Notificación diaria a la hora programada con las mejores ofertas y cartas de presentación en PDF adjuntas.
- Comandos interactivos: `/buscar` (ejecución manual inmediata con cooldown de 5 min), `/estado`, `/ultimas`, `/config` y `/ayuda`.

---

## 7. Mantenimiento y Respaldos

- **Ver logs del sistema**:
  ```bash
  docker compose logs -f lazyjobfinder
  ```
- **Detener los servicios**:
  ```bash
  docker compose down
  # o docker compose stop
  ```
- **Copia de seguridad**:
  - Tu base de datos y currículums residen en `./data`.
  - Tus ajustes y perfil residen en `./config`.
  - Respaldar estas dos carpetas mantiene intacto tu historial y configuraciones.
