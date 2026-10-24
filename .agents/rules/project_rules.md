# Reglas del Proyecto - lazyJobFinder

Este documento establece las normas obligatorias de desarrollo, arquitectura y comportamiento para cualquier modificación en el repositorio lazyJobFinder.

---

## 1. Universalidad Global y Neutralidad Profesional
- **Agnóstico a la profesión**: El sistema es 100% universal para cualquier oficio o carrera (mozo de almacén, carretillero, repartidor, sanitario, administrativo, hostelería, mantenimiento, diseño, abogacía, desarrollo de software, etc.).
- **Prohibido el sesgo sectorial**: Queda estrictamente prohibido introducir discriminaciones o clasificaciones artificiales (ej. variables tipo `is_tech_role`, bifurcaciones que favorezcan a la informática sobre otros sectores o listas fijas de profesiones).
- **Cero plantillas fijas impuestas**: Ni `config/profile.yaml` ni `config/settings.yaml` deben contener datos de prueba, perfiles de desarrollador DAM ni listas de términos fijos por defecto. El sistema debe operar limpio desde el primer momento.

---

## 2. El CV Activo como Única Fuente de Verdad y Dinamismo de Búsqueda
- **Extracción abierta y dinámica**: Al subir o seleccionar un CV (PDF, Markdown o TXT), la IA analiza el texto de forma abierta y extrae de 2 a 4 términos reales de búsqueda de empleo habituales en España que se correspondan estrictamente con la capacitación demostrada en el documento.
- **Sincronización automática**: Los términos extraídos se sincronizan en memoria y en la configuración (`settings.yaml`) para alimentar los escáneres en portales de empleo.
- **Veracidad factual**: Las competencias, titulaciones e historial laboral se validan exclusivamente contra el texto del CV activo aportado mediante `ProfileVerifier`. Jamás se inventan datos ni se mezclan perfiles de diferentes oficios.

---

## 3. Comportamiento Ante Ausencia de CV
- **Sin CV activo seleccionado**:
  - La vista principal de candidaturas muestra un estado vacío instructivo.
  - La barra lateral de filtros queda oculta.
  - No se lanzan búsquedas en portales ni se muestran ofertas contrastadas hasta que el usuario suba o seleccione un currículum en la cabecera.

---

## 4. Conectores Globales vs Portales Temáticos
- **Portales globales activos por defecto**: JobSpy (Indeed España, LinkedIn, Glassdoor, Google Jobs) e InfoJobs API son las fuentes primarias porque cubren todas las profesiones y sectores del mercado laboral.
- **Portales de nicho o exclusivos**: Conectores específicos de un solo sector (como Tecnoempleo RSS, exclusivo de TI) permanecen desactivados por defecto en `settings.yaml` (`habilitado: false`) para no contaminar búsquedas de candidatos de otros oficios.

---

## 5. Inferencia Local y Coste Cero (0 €/mes)
- Prohibido introducir dependencias, librerías o llamadas a APIs comerciales o de pago (OpenAI, Anthropic, Claude, Gemini Cloud, etc.).
- Toda la inferencia de Inteligencia Artificial se ejecuta de forma local y soberana mediante Ollama dentro del contenedor `lazyjob_ollama`.
- El modelo predeterminado es `qwen2.5:3b-instruct` ejecutándose en CPU cuantizada (Q4_K_M).
- No presupongas aceleración GPU ROCm en Docker Desktop para Windows.

---

## 6. Privacidad y Canales Desacoplados
- Toda la evaluación, scoring y almacenamiento en base de datos SQLite en modo WAL se realiza localmente en la máquina del usuario.
- El canal de notificación de Telegram es complementario y desacoplado: su activación o desactivación en la configuración no altera el funcionamiento del panel web local ni la persistencia de datos.

---

## 7. Control Rígido de Documentos PDF
- Los documentos adaptados (CV y cartas de motivación) se compilan exclusivamente mediante ReportLab (`src/tailoring/pdf_renderer.py`) con una plantilla de diseño e ingeniería tipográfica rígida controlada por código.
- El modelo LLM únicamente aporta los fragmentos de texto verificados; jamás controla el layout, márgenes, tipografías ni estructura visual del PDF.
- Todos los documentos generados se respaldan en disco tanto en formato PDF como en Markdown editable junto a un registro JSON de cambios.

---

## 8. Aislamiento Estricto de Conectores y Deduplicación
- Cada portal de empleo debe ejecutarse aislado en su propio bloque `try/except`. Un error de conexión o rate-limit en un portal jamás debe cancelar el escaneo en los restantes conectores.
- Para evitar ofertas repetidas publicadas simultáneamente en múltiples sitios (ej. Indeed y LinkedIn), el sistema calcula un `url_hash` y una huella digital difusa `content_fingerprint` con RapidFuzz.

---

## 9. Experiencia de Usuario (Frontend y Mantenimiento)
- **Barra de CV en cabecera**: Todos los controles del currículum (etiqueta, tooltip informativo, selector desplegable, ojo de previsualización, botón de subida y botón de borrado) deben ubicarse en una única línea compacta junto al título principal (`Candidaturas y Ofertas`).
- **Mantenimiento simplificado**: El botón y modal de "Vaciar Historial" no debe obligar al usuario a escribir frases de texto de confirmación; debe mostrar un diálogo claro con opciones directas de "Cancelar" y "Sí, Vaciar Historial".
- **CSS fluido y relativo**: Sin anchos fijos tipo `max-w-7xl`; separación lateral global de máximo 5vw (`px-4 sm:px-[3vw] lg:px-[5vw]`).
- **Tooltips contextuales**: Uso del componente `InfoTooltip` (`(?)`) para explicaciones sin sobrecargar la pantalla con párrafos largos.

---

## 10. Auto-Recarga en Caliente (Hot-Reload)
- El backend ejecuta una tarea en segundo plano que vigila los archivos `.py` en `src/`. Cuando se modifica código fuente, el proceso se reinicia automáticamente en memoria en milisegundos, reflejando cambios sin requerir reinicios manuales de contenedores Docker.

---

## 11. Prohibición de Testeo por Navegador
- Queda terminantemente prohibido utilizar subagentes o herramientas automatizadas de control de navegador para realizar pruebas o testeos. Las validaciones se efectúan mediante scripts, endpoints y comandos de terminal.

---

## 12. Ciclo de Vida de CVs y Vinculación Estricta de Ofertas
- **Desacoplamiento de `settings.yaml`**: `settings.yaml` no requiere términos de búsqueda fijos (`busqueda.terminos: []`). Los términos de búsqueda pertenecen a cada CV y se extraen/guardan de forma dinámica en `data/active_cv.json` sin reescribir la configuración global del sistema.
- **Búsqueda únicamente al subir**: El rastreo automático en portales se ejecuta exclusivamente al subir un nuevo archivo CV.
- **Cambio de CV sin re-escaneo**: Al seleccionar en el desplegable un CV ya existente, no se realiza ninguna llamada externa a portales; la interfaz filtra localmente las ofertas que ya se trajeron para ese CV (`WHERE cv_filename = :cv`).
- **Eliminación en cascada**: Al borrar un CV, se eliminan del almacenamiento local tanto el archivo físico como todas las ofertas vinculadas a dicho CV en la base de datos SQLite.
- **Extracción única y caché multinivel (Cero re-parseos)**: El archivo físico del CV (PDF, MD, TXT) se parsea una única vez cuando se sube o se modifica. Su texto se almacena en caché en memoria RAM (`_CV_TEXT_CACHE`) y en disco (`.extracted_<cv>.txt`). Queda terminantemente prohibido re-parsear el documento en consultas de listado/filtrado de ofertas (`/jobs`), cálculo de facetas o iteraciones de evaluación. Las consultas de interfaz utilizan comprobaciones ultraligeras de puntero (`get_active_cv_status()`) y el motor de scoring reutiliza la instancia de `ProfileVerifier` y el texto en memoria para todo el lote de vacantes.

---

## 13. Centralización Estricta de `__pycache__`
- **Prefijo unificado**: Todo el bytecode de Python se centraliza obligatoriamente en `.cache/pycache/` a través de la variable de entorno `PYTHONPYCACHEPREFIX` (definida en `start.bat`, `docker-compose.yml`, `Dockerfile` y reforzada en `sitecustomize.py`).
- **Cero subcarpetas en el árbol**: Queda terminantemente prohibido generar o commitear subdirectorios `__pycache__` dispersos en `src/`, `tests/` o cualquier otra carpeta del repositorio.

---

## 14. Unidades Relativas y Alias Exclusivos en la Interfaz (Frontend)
- **Cero píxeles arbitrarios**: En CSS y Tailwind queda prohibido el uso de valores `px` fijos en tipografía y dimensiones principales (ej. `text-[10px]`, `text-[11px]`). Deben emplearse clases relativas tipadas (`text-2xs`, `text-3xs`, `rem`, `em`, `dvh`, `vw`, `clamp()`).
- **Alias absolutos `@/...`**: Todas las importaciones dentro del frontend (`web/src`) deben realizarse mediante el alias `@/...`. Quedan terminantemente prohibidas las rutas relativas (`./` o `../`).

---

## 15. Prohibición de Archivos Puente, Pasarela o Redundantes
- **Cero proxies vacíos**: No se deben crear archivos o directorios cuya única finalidad sea re-exportar símbolos, hacer de puente de transición o redirigir rutas mediante llamadas estáticas (como `redirect("/")`).
- **Consolidación modular**: Los tipos, utilidades y componentes deben residir directamente en sus módulos funcionales (`web/src/types/index.ts`, `web/src/lib/`, `web/src/components/features/`).

---

## 16. CSS Moderno y Centralizado
- **Aprovechamiento de estándares web modernos**: La hoja de estilos principal (`globals.css`) se estructura mediante variables CSS fluidas, funciones nativas (`clamp()`), mezcla de color en tiempo de ejecución (`color-mix(in srgb, ...)`), consultas de soporte condicional (`@supports (backdrop-filter: blur(...))`) y respeto por accesibilidad (`@media (prefers-reduced-motion: reduce)`).

---

## 17. Cero Mocks, Datos Simulados o Fallbacks Silenciosos
- **Transparencia total**: Toda la información y estados presentados en la interfaz de usuario proceden exclusivamente de la base de datos local SQLite y de los endpoints de FastAPI en tiempo real.
- **Prohibido enmascarar errores**: Si el backend, Docker o la red no responden, la interfaz jamás debe mostrar datos simulados o mocks; debe mostrar explícitamente el estado de error, informar del fallo de conexión y proporcionar un mecanismo de reintento.

---

## 18. Arquitectura de Página Única y Terminal en Ventana Modal
- **Foco absoluto en Candidaturas**: La pantalla principal es una Single Page Application en la ruta raíz `/` orientada exclusivamente a la gestión y revisión de ofertas de empleo.
- **Terminal en Modal**: La monitorización de logs de Docker (app y Ollama) y del pipeline de búsqueda se gestiona mediante un diálogo modal interactivo (`TerminalLogsDialog`) accesible desde la cabecera, eliminando conmutadores de páginas principales o pestañas secundarias innecesarias.

---

## 19. Notificaciones Flotantes y Cero Popups Nativos de Navegador
- **Prohibido `window.alert` invasivo**: Queda prohibido bloquear la navegación con cuadros de diálogo modales nativos del navegador.
- **Recepción unificada abajo a la derecha**: Todos los avisos, confirmaciones y mensajes del sistema fluyen a través del componente unificado `Toaster` (`web/src/components/ui/toast.tsx`), renderizándose como tarjetas estilizadas flotantes en la esquina inferior derecha (`fixed bottom-4 right-4`), con auto-clasificación visual por tipo (éxito, error, advertencia, información), cierre automático y soporte para descarte manual.


