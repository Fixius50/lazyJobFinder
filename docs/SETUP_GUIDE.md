# Guía de Instalación y Despliegue: lazyJobFinder (0 €/mes)

Esta guía explica paso a paso cómo poner en marcha **lazyJobFinder** en tu equipo con Windows y Docker Desktop, utilizando tu bot de Telegram como interfaz de control diario y ejecutando la IA 100% en local dentro de Docker.

---

## 1. Requisitos Previos

1. **Docker Desktop para Windows** instalado y en ejecución (con backend WSL2 activado).
2. **Conexión a Internet** para la primera descarga de las imágenes Docker, el modelo de Ollama y la búsqueda de ofertas.
3. **Una cuenta de Telegram**.

---

## 2. Paso 1: Crear tu Bot de Telegram y Obtener Credenciales (2 minutos)

1. Abre Telegram y busca el contacto oficial **@BotFather**.
2. Envía el comando `/newbot`.
3. Sigue las instrucciones: elige un nombre visible (ej. `Mi Asistente de Empleo`) y un nombre de usuario que termine en `bot` (ej. `robert_job_bot`).
4. **Guarda el Token**: BotFather te responderá con un token HTTP similar a `7123456789:AAH...v8Z`. Este es tu `TELEGRAM_BOT_TOKEN`.
5. **Obtener tu Chat ID personal**:
   - En Telegram, busca el bot **@userinfobot** y pulsa *Iniciar*.
   - Te responderá con tu `Id` numérico (ej. `123456789`). Este es tu `TELEGRAM_ALLOWED_USER_ID`.
   - *Importante*: Abre una conversación con tu nuevo bot recién creado y pulsa *Iniciar* (`/start`) para que el bot tenga permiso para enviarte mensajes y archivos.

---

## 3. Paso 2: Configurar las Variables de Entorno

En la raíz del proyecto `lazyJobFinder`, copia el archivo `.env.example` como `.env`:

```bash
cp .env.example .env
```

Edita `.env` con tus credenciales:

```ini
# Configuración Obligatoria de Telegram
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

# Opcional: InfoJobs API (Gratuita en developer.infojobs.net)
# Si se dejan en blanco, el sistema utiliza Tecnoempleo RSS, Indeed, LinkedIn y Glassdoor
INFOJOBS_CLIENT_ID=
INFOJOBS_CLIENT_SECRET=
```

---

## 4. Paso 3: Personalizar tu Perfil Profesional Real

El sistema incluye una plantilla en `config/profile.yaml` configurada para un perfil titulado de **Desarrollo de Aplicaciones Multiplataforma (DAM)**:

1. Abre `config/profile.yaml`.
2. Verifica y ajusta tus datos:
   - Nombre completo, correo, teléfono y enlaces (LinkedIn, GitHub).
   - Tus tecnologías dominadas: Java, SQL, PL/SQL, NoSQL, HTML, CSS, JavaScript, PHP, Linux, REST APIs.
   - Los proyectos reales que desarrollaste en el ciclo DAM (por ejemplo, tu proyecto final de ciclo o aplicaciones prácticas).
   - Preferencias de ubicación: Ciudad, si aceptas trabajo en remoto, híbrido o presencial.
3. *Garantía de honestidad*: Todo lo que esté en `profile.yaml` será utilizado para destacar tu candidatura. Lo que no esté en este archivo, el sistema **nunca lo inventará**.

---

## 5. Paso 4: Arrancar los Contenedores con Docker Compose

Ejecuta en la terminal de la raíz del proyecto:

```bash
docker compose up -d
```

Docker Compose levantará dos contenedores:
1. `lazyjob_ollama`: Motor de inferencia local con volumen persistente `ollama_models`.
2. `lazyjob_app`: El servicio de búsqueda, base de datos SQLite, renderizador documental y bot de Telegram.

### Descarga del Modelo Local de Ollama (Solo la primera vez)

Para descargar el modelo recomendado `qwen2.5:3b-instruct` (~2.0 GB) dentro del volumen persistente de Docker:

```bash
docker exec -it lazyjob_ollama ollama pull qwen2.5:3b-instruct
```

*Nota*: Una vez descargado, el modelo se mantiene guardado en el volumen persistente aunque apagues el equipo o recrees los contenedores.

---

## 6. Paso 5: Uso Diario a través de Telegram

Una vez arrancado, el sistema funciona de manera 100% autónoma en segundo plano. No necesitas abrir ninguna interfaz web.

### Notificación Diaria Automática
- Cada mañana a la hora configurada (ej. 08:30), recibirás en Telegram:
  - Un mensaje por cada oferta relevante con puntuación >= 65.
  - La puntuación de afinidad (ej. 85/100).
  - Los puntos fuertes y requisitos que cumples con tu formación DAM.
  - Los requisitos que te faltan.
  - El enlace directo a la oferta original.
  - **Archivos adjuntos**: El CV adaptado en PDF (`CV_Empresa.pdf`) y la Carta de presentación en PDF (`Carta_Empresa.pdf`).

### Comandos de Telegram Disponibles

Puedes interactuar con tu bot en cualquier momento:

- `/buscar`: Ejecuta una búsqueda y evaluación inmediata bajo demanda sin esperar a la hora programada.
- `/estado`: Muestra el diagnóstico del sistema (conexión con Ollama, modelo activo, ofertas registradas en la base de datos y fecha del último escaneo).
- `/ultimas`: Muestra el listado de las mejores ofertas encontradas en los últimos días.
- `/config`: Muestra los filtros actuales (palabras clave, ubicaciones, umbral de puntuación).
- `/ayuda`: Muestra la lista de comandos disponibles.

---

## 7. Mantenimiento y Recuperación ante Errores

- **Ver logs del sistema**:
  ```bash
  docker compose logs -f lazyjob_app
  ```
- **Reiniciar el sistema**:
  ```bash
  docker compose restart
  ```
- **Detener los contenedores**:
  ```bash
  docker compose down
  ```
- **Copia de seguridad**:
  - Tu base de datos y documentos generados están en la carpeta local `./data`.
  - Tu configuración está en `./config`.
  - Respaldar estas dos carpetas asegura la persistencia total de tu historial.
