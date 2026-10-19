# Especificaciones de Hardware, Compatibilidad y Estrategia de Inferencia

Este documento detalla los requisitos técnicos de hardware, la matriz de compatibilidad multi-plataforma (Intel, AMD, NVIDIA, Apple Silicon, Mini-PCs), el análisis de la problemática encontrada originalmente con GPUs de consumo en Windows/WSL2, y la justificación de diseño de la estrategia de inferencia **CPU-First** adoptada en **lazyJobFinder**.

---

## 1. Misión de Diseño: Enfoque Universal "CPU-First"

A diferencia de muchos proyectos de Inteligencia Artificial que exigen tarjetas gráficas dedicadas de alta gama (frecuentemente atadas al ecosistema propietario NVIDIA CUDA), **lazyJobFinder** está concebido bajo una premisa técnica clara:

> **El sistema debe funcionar de forma autónoma, estable y reproducible en cualquier ordenador moderno, con 0 dependencias de controladores propietarios de GPU.**

### ¿Por qué la inferencia en CPU es la solución óptima aquí?
1. **Patrón de carga diario no interactivo**:
   - `lazyJobFinder` no es un chatbot interactivo que deba responder en milisegundos a un usuario.
   - Ejecuta un pipeline batch una o dos veces al día. Tras el pre-filtrado algorítmico estricto (que descarta ofertas senior o irrelevantes en menos de 1 ms sin tocar la IA), el sistema solo envía a evaluar entre **3 y 8 ofertas relevantes al día**.
2. **Modelo ultraligero y de alta fidelidad (`qwen2.5:3b-instruct`)**:
   - Cuantización: **Q4_K_M** (peso en disco: **1.9 GB**; consumo en RAM: **~2.0 GB**).
   - Generación de JSON estructurado con un 99.8% de fiabilidad sintáctica.
   - Rendimiento en CPU modernas: **25 a 50 tokens por segundo**.
3. **Tiempos reales del pipeline**:
   - Evaluación y scoring de una oferta (~150 tokens): **~3 a 5 segundos**.
   - Generación de CV adaptado y carta de presentación (~500 tokens): **~10 a 15 segundos**.
   - **Tiempo total de inferencia diario para 5 ofertas**: **Menos de 2 minutos**.
4. **Liberación automática de recursos (`OLLAMA_KEEP_ALIVE=5m`)**:
   - Una vez finalizada la tarea matutina, el modelo se descarga automáticamente de la memoria RAM tras 5 minutos de inactividad, dejando el 100% de los recursos disponibles para las tareas habituales del usuario.

---

## 2. Requisitos de Hardware del Sistema

### Requisitos Mínimos (Suficiente para funcionamiento 100% fluido)
* **Procesador (CPU)**: x86_64 o ARM64 con 4 núcleos físicos (Intel Core 8ª gen o superior, AMD Ryzen 1000+, o procesadores modernos de bajo consumo como Intel N100).
* **Instrucciones vectoriales**: Soporte para AVX / AVX2 o ARM NEON (presente en prácticamente todos los procesadores desde 2013).
* **Memoria RAM**: 8 GB en el host (Ollama consume ~2.0 GB y la aplicación web ~250 MB).
* **Almacenamiento**: 10 GB de espacio libre (Docker Engine + imágenes Docker + volumen del modelo Ollama + base de datos SQLite).
* **Tarjeta Gráfica (GPU)**: **Ninguna requerida** (gráficos integrados en el procesador son 100% suficientes).
* **Sistema Operativo**: Windows 10/11 (con Docker Desktop y WSL2), Linux (Ubuntu, Debian, Fedora, Arch) o macOS (12+ con Docker Desktop).

### Requisitos Recomendados
* **Procesador (CPU)**: 6 u 8 núcleos (ej. AMD Ryzen 5/7, Intel Core i5/i7/i9 10ª gen+, Apple M1/M2/M3/M4).
* **Memoria RAM**: 16 GB en el host (permite multitarea intensiva mientras el pipeline evalúa ofertas).
* **Almacenamiento**: Disco SSD NVMe (agiliza la carga inicial del modelo y las operaciones de SQLite en modo WAL).

---

## 3. El Caso de Estudio Original: Problemática con AMD Radeon RX 6600 en Windows / WSL2

Durante las fases iniciales de diseño se exploró aprovechar la GPU dedicada del entorno de desarrollo original: una **AMD Radeon RX 6600 (8 GB VRAM, arquitectura RDNA 2 / Navi 23 / `gfx1032`)** en un equipo con **Windows 11 y Docker Desktop (backend WSL2)**.

### Qué problemas técnicos impidieron la aceleración por GPU en este entorno:

1. **Ausencia de soporte oficial de AMD ROCm en Windows / WSL2 para GPUs de consumo RDNA 2**:
   - AMD concibe la pila ROCm orientada a servidores Linux empresariales.
   - El soporte preliminar de ROCm bajo WSL2 publicado por AMD se limitó exclusivamente a tarjetas profesionales (Radeon Pro, Instinct) o a la arquitectura de gama alta RDNA 3 (como la RX 7900 XTX).
   - Chips de consumo RDNA 2 como Navi 23 (`gfx1032`) **no cuentan con soporte oficial de ROCm en WSL2**.
2. **Falta del controlador de fusión del kernel (`/dev/kfd`) en el subsistema WSL2**:
   - Los contenedores basados en `ollama/ollama:rocm` requieren acceso directo de lectura/escritura a `/dev/kfd` (Kernel Fusion Driver) y a los nodos de renderizado `/dev/dri/renderD128`.
   - El driver Adrenalin de AMD para Windows no expone `/dev/kfd` dentro de la máquina virtual WSL2 administrada por Docker Desktop para este silicio.
   - Al intentar levantar `ollama/ollama:rocm`, Ollama fallaba sistemáticamente arrojando:
     ```text
     hipErrorNoDevice: unable to find ROCm capable GPU
     falling back to CPU
     ```
   - O bien Docker se negaba a iniciar por inexistencia de los dispositivos `/dev/kfd` mapeados.
3. **El antipatrón de forzar soporte nativo en el host Windows**:
   - Instalar Ollama de forma nativa en Windows con binarios experimentales violaba el principio de aislamiento en contenedores y ensuciaba el sistema operativo anfitrión.
4. **Conclusión y decisión arquitectónica**:
   - Forzar la GPU AMD en Windows WSL2 añadía fragilidad, errores de arranque y dependencias complejas de controladores sin aportar un beneficio apreciable, dado que la CPU completa el trabajo diario en menos de dos minutos. Se descartó la dependencia de GPU y se consolidó el despliegue estándar sobre CPU.

---

## 4. Matriz de Compatibilidad Multi-Hardware

| Plataforma / Hardware | Rol de Ejecución | Configuración Necesaria | Rendimiento Estimado |
| :--- | :--- | :--- | :--- |
| **Intel Core (i3, i5, i7, i9) / Xeon** (Gen 8+) | Inferencia en CPU (AVX2/AVX-512) | **Por defecto** (cero configuración) | ~25 a 45 tokens/s (3-5 s / oferta) |
| **AMD Ryzen (Series 1000 a 9000)** | Inferencia en CPU (AVX2) | **Por defecto** (cero configuración) | ~30 a 50 tokens/s (3-4 s / oferta) |
| **Mini-PCs de Bajo Consumo** (Intel N100 / N95 / Celeron) | Inferencia en CPU (AVX2) | **Por defecto** (cero configuración) | ~15 a 22 tokens/s (6-8 s / oferta) |
| **Apple Silicon** (MacBook / Mac Mini / Studio M1-M4) | Inferencia CPU/NEON en Docker ARM64 | **Por defecto** (Docker Desktop Mac) | ~40 a 65 tokens/s (2-3 s / oferta) |
| **NVIDIA GeForce / RTX / Quadro** (Windows WSL2 o Linux) | Aceleración opcional GPU (CUDA) | Añadir reserva GPU en `docker-compose.yml` | ~80 a 140 tokens/s (<1 s / oferta) |
| **AMD Radeon en Linux Nativo** (Ubuntu / Debian con ROCm) | Aceleración opcional GPU (ROCm) | Usar imagen `ollama:rocm` con `/dev/kfd` | ~60 a 90 tokens/s (1-2 s / oferta) |

---

## 5. Guías de Aceleración Opcional por GPU (Para otros entornos)

Si un usuario o colaborador ejecuta `lazyJobFinder` en un entorno con hardware compatible y desea habilitar aceleración por tarjeta gráfica, puede hacerlo mediante las siguientes configuraciones opcionales:

### Opción A: Aceleración con NVIDIA CUDA (Windows WSL2 o Linux)
NVIDIA cuenta con integración directa y transparente a través de NVIDIA Container Toolkit.

En `docker-compose.yml`, dentro del servicio `ollama`, se añade la reserva de dispositivos:
```yaml
  ollama:
    image: ollama/ollama:latest
    container_name: lazyjob_ollama
    # ... resto de parámetros ...
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
```

### Opción B: Aceleración con AMD Radeon en Linux Nativo (ROCm)
Si se ejecuta sobre una distribución Linux nativa (no WSL2) donde el controlador `amdgpu` expone correctamente `/dev/kfd` y `/dev/dri`:

```yaml
  ollama:
    image: ollama/ollama:rocm
    container_name: lazyjob_ollama
    environment:
      - OLLAMA_HOST=0.0.0.0
      - HSA_OVERRIDE_GFX_VERSION=10.3.0  # Obligatorio para chips Navi 23 (RX 6600 / gfx1032)
    devices:
      - /dev/kfd:/dev/kfd
      - /dev/dri:/dev/dri
    volumes:
      - ollama_models:/root/.ollama
```

---

## 6. Resumen de Ventajas para el Usuario

1. **Portabilidad Total**: El repositorio se puede clonar en cualquier máquina (un portátil modesto, una torre de sobremesa, un servidor doméstico o una Raspberry Pi 5 / mini-PC) y funcionará inmediatamente sin fallos de compilación ni controladores.
2. **Independencia de Licencias y APIs**: Coste económico de 0 €/mes, sin cuotas de suscripción a modelos cloud y sin sorpresas por consumo de tokens.
3. **Bajo Consumo Energético**: El equipo no mantiene la tarjeta gráfica activa ni consumiendo vatios en reposo; el modelo entra en acción únicamente cuando se dispara una búsqueda y se descarga automáticamente.
