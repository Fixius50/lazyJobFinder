# Changelog

Todos los cambios relevantes de este proyecto se documentan en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el versionado sigue [SemVer](https://semver.org/lang/es/).

Tipos de cambio recomendados por versión:

- **Added**: Nuevas funcionalidades.
- **Changed**: Cambios en funcionalidad existente.
- **Deprecated**: Funcionalidades que quedarán obsoletas próximamente.
- **Removed**: Funcionalidades eliminadas.
- **Fixed**: Correcciones de errores y bugs.
- **Security**: Correcciones de vulnerabilidades y seguridad.

---

## [1.0.0] - 2026-10-28

### Added
- **Arquitectura Universal y Agnóstica**: Búsqueda, evaluación y tailoring de candidaturas para cualquier perfil y sector profesional en España.
- **Motor de Inferencia IA Local (0 €/mes)**: Integración con Ollama (`qwen2.5:3b-instruct` cuantizado en CPU Q4_K_M) con política anti-alucinación estricta y sin dependencia de servicios cloud de pago.
- **Capa de Conectores Multi-Portal**: Escaneo concurrente y aislado de JobSpy (LinkedIn, Indeed, Glassdoor, Google Jobs), API oficial de InfoJobs y Tecnoempleo RSS.
- **Persistencia SQLite Unificada y Moderna**: Modo `TRUNCATE` / `WAL` con auto-migración dinámica mediante `sqlite-utils` (`alter=True`), motor de búsqueda instantáneo `FTS5`, PRAGMAs de rendimiento en memoria y modelos canónicos Pydantic V2 (`src/models.py`).
- **Motor Documental ATS Tipográfico**: Renderizado de currículums y cartas de presentación adaptadas a cada vacante en formatos PDF (ReportLab) y Markdown editable.
- **Panel Web SPA Unificado**: Interfaz moderna desarrollada con Next.js 14, Tailwind CSS, mapa geográfico con Leaflet, filtros multicriterio dinámicos y visor de terminal en modal.
- **Deduplicación Inteligente Multi-Nivel**: Detección de ofertas repetidas mediante `url_hash`, huella semántica `content_fingerprint` y similitud difusa con RapidFuzz.
- **Canal de Alertas Opcional de Telegram**: Notificaciones matutinas y envío automático de PDFs directamente a chat privado.
- **Infraestructura de Empaquetado Multiplataforma**: Generador de releases portables e instaladores para Windows (`.exe`, `.zip`) y GNU/Linux (`.run`, `.tar.gz`).
- **Metadatos Oficiales de Citación**: Incorporación de `CITATION.cff` para registro formal del software en GitHub.

