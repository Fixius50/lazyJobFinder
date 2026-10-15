# Guía de Contexto Técnico para Agentes de IA

Si eres un modelo de Inteligencia Artificial que trabaja en este repositorio, **lee primero el documento maestro de arquitectura y limitaciones técnicas**:

👉 **[docs/AI_SYSTEM_OVERVIEW.md](docs/AI_SYSTEM_OVERVIEW.md)**

---

## Resumen Rápido de Directrices Fundamentales

1. **Coste 0 €/mes**: No introduzcas dependencias ni APIs de pago de IA (cero OpenAI, Anthropic, Claude o servicios cloud).
2. **Ollama en Docker**: La inferencia se realiza 100% en local dentro del contenedor `lazyjob_ollama` mediante **CPU cuantizada (Q4_K_M)** con el modelo `qwen2.5:3b-instruct`. No presupongas aceleración ROCm en Docker Desktop para la AMD RX 6600 en Windows.
3. **Privacidad y Telegram**: La inferencia de IA y el análisis son 100% locales (ningún dato viaja a nubes de IA). No obstante, el envío de los PDFs por Telegram implica transmitirlos a través de la infraestructura externa de Telegram (HTTPS hacia servidores de la Telegram Bot API).
4. **Veracidad Factual por Código**: Todo contenido generado debe verificarse algorítmicamente mediante `ProfileVerifier` ([`src/tailoring/verifier.py`](src/tailoring/verifier.py)) contra [`config/profile.yaml`](config/profile.yaml). Se prohíbe alucinar experiencia laboral comercial o tecnologías ausentes en dicho perfil.
5. **Deduplicación entre Portales**: El esquema SQLite almacena `url_hash` y `content_fingerprint` ([`src/database.py`](src/database.py)) para evitar notificaciones duplicadas cuando una misma vacante se publica simultáneamente en Indeed y LinkedIn.
6. **Documentos Controlados**: Los PDFs se generan mediante plantillas fijas en ReportLab ([`src/tailoring/pdf_renderer.py`](src/tailoring/pdf_renderer.py)). El LLM jamás controla el layout ni el diseño. El CV original ([`config/cv_base.md`](config/cv_base.md)) es estrictamente de solo lectura.
7. **Aislamiento de Conectores**: Cada portal de búsqueda (Tecnoempleo RSS, InfoJobs API, Indeed, LinkedIn, Glassdoor, Google Jobs) opera de forma independiente para que el fallo o rate-limit de uno no cancele los demás.
8. **Planificación y Reinicios**: APScheduler registra cada ejecución en la tabla `pipeline_runs`. En el arranque del contenedor, comprueba `check_missed_run_on_startup()` para recuperar ejecuciones perdidas si el equipo estuvo apagado.
9. **Telegram como Interfaz Única**: No añadas frontends web ni paneles visuales. Toda la interacción del usuario se gestiona a través del bot privado en [`src/telegram_bot/bot.py`](src/telegram_bot/bot.py) con verificación estricta de `TELEGRAM_ALLOWED_USER_ID > 0`.
