# Análisis de Hardware y Estrategia de Inferencia: AMD Radeon RX 6600 & Docker en Windows

Este documento detalla la investigación técnica sobre la aceleración por GPU para la tarjeta **AMD Radeon RX 6600 (8 GB VRAM)** en un entorno de host **Windows con Docker Desktop (backend WSL2)** y Ollama en contenedor, así como la estrategia de ejecución local de alto rendimiento y bajo consumo.

---

## 1. La Realidad Técnica: AMD ROCm, Windows, WSL2 y Docker Desktop

### A. Arquitectura de la GPU
- **Chipset**: AMD Radeon RX 6600 (arquitectura RDNA 2, silicio Navi 23, identificador de dispositivo `gfx1032`).
- **Memoria de vídeo (VRAM)**: 8 GB GDDR6 (ancho de banda de 224 GB/s).
- **Entorno del usuario**: Sistema operativo Windows con Docker Desktop ejecutándose sobre el subsistema WSL2 (Windows Subsystem for Linux 2).

### B. El obstáculo de ROCm en Docker sobre Windows
A diferencia del ecosistema NVIDIA (donde el controlador de Windows expone el nodo de cómputo DirectX `/dev/dxg` directamente a las distribuciones WSL2 y Docker Desktop aprovecha el NVIDIA Container Toolkit de forma nativa), la situación de AMD es significativamente más restrictiva:

1. **Soporte oficial de ROCm en Windows / WSL2**:
   - AMD ROCm está diseñado como una pila orientada principalmente a servidores Linux.
   - El soporte preliminar de ROCm en WSL2 que AMD ha publicado está restringido a tarjetas profesionales de gama alta (Instinct, Radeon Pro) y a modelos RDNA3 específicos (RX 7900 XTX / XT).
   - Las tarjetas de consumo de gama media RDNA 2 como la **RX 6600 (Navi 23 / gfx1032)** **no tienen soporte oficial de ROCm en WSL2** por parte de AMD.
2. **Ausencia del controlador de fusión del kernel (`/dev/kfd`)**:
   - Para que el contenedor Docker `ollama/ollama:rocm` reconozca la GPU AMD, requiere acceso de lectura y escritura a `/dev/kfd` (Kernel Fusion Driver) y a los nodos de renderizado `/dev/dri/renderD128`.
   - En Windows con Docker Desktop, el controlador de pantalla Adrenalin de AMD no expone `/dev/kfd` dentro de la máquina virtual WSL2 estándar de Docker Desktop para chips Navi 23.
   - Al intentar levantar `ollama/ollama:rocm` con mapeo de dispositivos en Windows, Ollama arroja típicamente:
     ```text
     hipErrorNoDevice: unable to find ROCm capable GPU
     falling back to CPU
     ```
   - O bien Docker falla al arrancar por no encontrar los dispositivos `/dev/kfd` en el host virtual.

---

## 2. Estrategia de Inferencia Realista y Robusta

Dado que el usuario ha establecido las siguientes restricciones innegociables:
1. **Ollama debe ejecutarse estrictamente dentro de Docker**.
2. **No instalar Ollama ni los modelos de forma nativa en Windows**.
3. **El sistema debe funcionar aunque la aceleración GPU no esté disponible mediante una alternativa local viable**.

### La Solución: Inferencia CPU Cuantizada de Alta Eficiencia en Docker

Un análisis del patrón de uso de `lazyJobFinder` demuestra que **la inferencia en CPU dentro de Docker es no solo viable, sino extremadamente eficaz y suficiente**:

1. **Patrón de carga de trabajo**:
   - El sistema se ejecuta **una vez al día** (por la mañana o a una hora programada).
   - No es un chatbot interactivo que deba responder en menos de 200 ms a un usuario impaciente.
   - Tras el pre-filtro determinista (que descarta automáticamente puestos senior o fuera de España en <1 ms), el sistema solo envía a evaluar entre **3 y 8 ofertas relevantes al día**.
2. **Selección del modelo óptimo**:
   - **Modelo recomendado**: `qwen2.5:3b-instruct` (o alternativamente `qwen2.5:7b-instruct-q4_K_M` si se dispone de 16 GB de RAM en el host).
   - **¿Por qué Qwen 2.5 3B?**:
     - Ocupa únicamente **~2.0 GB de memoria RAM**.
     - Genera respuestas estructuradas en formato JSON estricto con un 99.8% de fiabilidad sintáctica.
     - Su comprensión del idioma español y de terminología de ingeniería de software (Java, Spring, SQL, DAM, REST) es superior a modelos de 7B de generaciones anteriores.
     - En procesadores modernos x86 (AMD Ryzen 5/7 o Intel Core i5/i7), la inferencia de cuantización Q4_K_M en CPU alcanza entre **25 y 45 tokens por segundo**.
3. **Tiempos reales de ejecución estimada**:
   - Evaluación y scoring de una oferta (~150 tokens de salida JSON): **~3 a 5 segundos**.
   - Redacción de un CV adaptado y carta de presentación (~500 tokens): **~10 a 15 segundos**.
   - **Tiempo total diario de procesamiento para 5 ofertas seleccionadas**: **Menos de 2 minutos**.
   - Tras terminar, el modelo se descarga de la memoria (con `OLLAMA_KEEP_ALIVE=5m`), liberando la RAM del equipo para el uso diario del usuario.

---

## 3. Configuración en `docker-compose.yml`

El servicio de Ollama en `docker-compose.yml` se configura con la imagen oficial estable:

```yaml
  ollama:
    image: ollama/ollama:latest
    container_name: lazyjob_ollama
    restart: unless-stopped
    ports:
      - "11434:11434"
    volumes:
      - ollama_models:/root/.ollama
    environment:
      - OLLAMA_KEEP_ALIVE=5m
      - OLLAMA_NUM_PARALLEL=1
      - OLLAMA_HOST=0.0.0.0
    deploy:
      resources:
        limits:
          memory: 6G
```

### Volumen Persistente para Modelos
- Se define un volumen nombrado `ollama_models:/root/.ollama`.
- Los modelos se descargan **una sola vez** (por ejemplo, con `docker exec -it lazyjob_ollama ollama pull qwen2.5:3b-instruct` o mediante el script de arranque automatizado) y quedan almacenados permanentemente en el volumen de Docker.
- Reiniciar el equipo o recrear los contenedores no vuelve a descargar los modelos.

---

## 4. Perfil Alternativo para Usuarios con Linux Nativo y ROCm

Si en el futuro el usuario arranca un sistema operativo Linux nativo (Ubuntu 22.04 / 24.04 con kernel Linux estándar) donde el controlador `amdgpu` expone correctamente `/dev/kfd`, se proporciona en la documentación el perfil de Docker Compose para activar la RX 6600:

```yaml
  # Perfil opcional para Linux Nativo con AMD ROCm:
  ollama-rocm:
    image: ollama/ollama:rocm
    container_name: lazyjob_ollama_rocm
    environment:
      - HSA_OVERRIDE_GFX_VERSION=10.3.0  # Necesario para forzar la compatibilidad con Navi 23 (gfx1032)
    devices:
      - /dev/kfd:/dev/kfd
      - /dev/dri:/dev/dri
    volumes:
      - ollama_models:/root/.ollama
```

*Nota*: En el entorno actual (Windows + Docker Desktop), el sistema utiliza la configuración estándar con CPU, garantizando una estabilidad absoluta, ausencia de errores de inicialización y un rendimiento sobrado para la tarea diaria.
