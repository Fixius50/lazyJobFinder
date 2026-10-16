# Reglas del Proyecto - lazyJobFinder

Este documento establece las normas obligatorias de desarrollo, arquitectura y comportamiento para cualquier modificación en el repositorio lazyJobFinder.

---

## 1. Inferencia Local y Coste Cero (0 €/mes)
- Prohibido introducir dependencias, librerías o llamadas a APIs comerciales o de pago (OpenAI, Anthropic, Claude, Gemini Cloud, etc.).
- Toda la inferencia de Inteligencia Artificial se ejecuta de forma local y soberana mediante Ollama dentro del contenedor `lazyjob_ollama`.
- El modelo predeterminado es `qwen2.5:3b-instruct` ejecutándose en CPU cuantizada (Q4_K_M).
- No presupongas aceleración GPU ROCm en Docker Desktop para Windows.

---

## 2. Veracidad Fáctica y Garantía Anti-Alucinación
- Cualquier dato profesional, competencia técnica, titulación o proyecto debe validarse estrictamente contra `config/profile.yaml` a través de `ProfileVerifier` (`src/tailoring/verifier.py`).
- Queda terminantemente prohibido inventar o simular experiencia laboral comercial o tecnologías que el usuario no domine.
- Si una oferta de empleo exige requisitos no presentes en el perfil del candidato, se registran en `missing_skills` y la puntuación de afinidad se penaliza; nunca se afirma que el candidato tiene dicha experiencia.
- El archivo base `config/cv_base.md` es de solo lectura y jamás debe ser sobrescrito por el pipeline ni por la subida de currículums.

---

## 3. Privacidad y Canales Desacoplados
- Toda la evaluación, scoring y almacenamiento en base de datos SQLite en modo WAL se realiza localmente en la máquina del usuario.
- El canal de notificación de Telegram es complementario y desacoplado: su activación o desactivación en la configuración no altera el funcionamiento del panel web local ni la persistencia de datos.

---

## 4. Control Rígido de Documentos PDF
- Los documentos adaptados (CV y cartas de motivación) se compilan exclusivamente mediante ReportLab (`src/tailoring/pdf_renderer.py`) con una plantilla de diseño e ingeniería tipográfica rígida controlada por código.
- El modelo LLM únicamente aporta los fragmentos de texto verificados; jamás controla el layout, márgenes, tipografías ni estructura visual del PDF.
- Todos los documentos generados se respaldan en disco tanto en formato PDF como en Markdown editable junto a un registro JSON de cambios.

---

## 5. Aislamiento Estricto de Conectores de Búsqueda
- Cada portal de empleo (Tecnoempleo RSS, InfoJobs API, Indeed, LinkedIn, Glassdoor, Google Jobs) debe ejecutarse aislado en su propio bloque `try/except`.
- Un error de conexión, cambio de DOM o rate-limit en un portal jamás debe cancelar el escaneo en los restantes conectores.

---

## 6. Deduplicación entre Portales
- Para evitar procesar o notificar ofertas duplicadas publicadas simultáneamente en múltiples sitios (ej. Indeed y LinkedIn), el sistema calcula un `url_hash` y una huella digital difusa `content_fingerprint` con RapidFuzz.
- Las ofertas duplicadas se vinculan a la oferta canónica principal sin borrar el registro ni duplicar notificaciones.

---

## 7. Arquitectura Frontend (Directrices de Interfaz)
- **Separación de responsabilidades**:
  - `web/src/types/`: Interfaces y contratos TypeScript organizados por dominio (`jobs.ts`, `services.ts`, `settings.ts`, `cv.ts`, `logs.ts`).
  - `web/src/components/ui/`: Primitivas reutilizables de diseño (botones, tarjetas, selectores, tooltips).
  - `web/src/components/features/`: Componentes modulares por dominio funcional (`jobs/`, `services/`, `cv/`).
  - `web/src/components/views/`: Vistas de ensamblado conectadas a estado global.
- **Márgenes y fluidez**:
  - CSS 100% relativo y fluido (`rem`, `%`, `flex`, `grid`, `dvh`).
  - Separación lateral global de como máximo 5vw (`px-4 sm:px-[3vw] lg:px-[5vw]`). Prohibido usar contenedores rígidos fijos tipo `max-w-7xl` que encajonen la pantalla en monitores anchos.
- **Minimización de textos y Tooltips Contextuales**:
  - Títulos limpios acompañados por el componente `InfoTooltip` (`(?)`) para albergar explicaciones y descripciones sin sobrecargar la pantalla.
- **Controles interactivos**:
  - Los botones de estado deben reflejar visualmente el color de su estado en el fondo.
  - El filtrado de afinidad en candidaturas se gestiona mediante un slider continuo sin cortes laterales.

---

## 8. Seguridad en Mantenimiento
- Las operaciones destructivas en base de datos (como el borrado del historial de ofertas) exigen validación mediante frases de confirmación exactas definidas en `CONFIRMATION_PHRASES`.

---

## 9. Estilo de Documentación
- La documentación del repositorio debe ser práctica, concisa, técnica y libre de emojis.
