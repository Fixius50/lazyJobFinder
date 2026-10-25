# Análisis y Verificación de Fuentes de Empleo en España

Este documento detalla la verificación individual de las bolsas de empleo en España para **cualquier disciplina o perfil profesional**, junto con las condiciones de acceso, limitaciones reales y la estrategia de aislamiento de fallos.

---

## 1. Verificación Individual de Fuentes

### A. Tecnoempleo (Canales RSS Sindicados - Opcional / Especializado)
- **Mecanismo de acceso**: Peticiones HTTP a `https://www.tecnoempleo.com/busqueda-empleo.php?te={termino}&en=rss`.
- **Viabilidad real**: **Alta**. Es un portal vertical especializado en tecnología en España. Permanece desactivado por defecto para no contaminar búsquedas generales de otras profesiones (logística, administración, sanidad, hostelería, etc.), pero puede activarse si el usuario lo requiere.
- **Riesgos y mitigación**:
  - Si Tecnoempleo devuelve un error temporal (HTTP 500/503), el conector captura la excepción, registra un aviso en la base de datos `system_logs` y permite que los demás conectores prosigan.
- **Coste**: 0 €/mes. Cero credenciales requeridas.

### B. InfoJobs (API REST Oficial de Desarrolladores)
- **Mecanismo de acceso**: Endpoint `/api/9/offer` mediante HTTP Basic Authentication.
- **Viabilidad real**: **Muy Alta** siempre que el usuario registre una aplicación gratuita en `developer.infojobs.net`.
- **Riesgos y mitigación**:
  - Si el usuario no introduce `INFOJOBS_CLIENT_ID` o `INFOJOBS_CLIENT_SECRET`, el conector detecta la ausencia de credenciales de forma preventiva y se desactiva limpiamente sin emitir errores catastróficos.
  - Si las credenciales caducan o son inválidas (HTTP 401/403), se emite una advertencia en el log y el sistema continúa con el resto de fuentes.
- **Coste**: 0 €/mes en la cuota gratuita para desarrolladores.

### C. Indeed España (JobSpy)
- **Mecanismo de acceso**: Extracción normalizada con parámetro `country_indeed='spain'`.
- **Viabilidad real**: **Alta**. Indeed tiene una enorme masa de puestos en Madrid, Barcelona, Valencia, Sevilla y remoto.
- **Riesgos y mitigación**:
  - Indeed implementa detección de bots si se satura de peticiones.
  - **Mitigación implementada**: Se aísla en su propio bloque `try-except`, se introducen pausas de 1.5s entre consultas y se limita el volumen a 15 ofertas por ejecución.

### D. LinkedIn España (JobSpy)
- **Mecanismo de acceso**: Scraping de la interfaz pública de empleo de LinkedIn.
- **Viabilidad real**: **Media / Variable**. LinkedIn es la plataforma con las medidas anti-bot más agresivas.
- **Riesgos y mitigación**:
  - Frecuentemente puede responder con HTTP 429 (Too Many Requests) o pantallas de verificación si detecta peticiones automatizadas repetidas desde la misma IP.
  - **Mitigación crítica**: **Aislamiento estricto por portal**. Si LinkedIn bloquea una petición, JobSpyConnector registra `linkedin: error/rate-limited`, pero **Indeed, Glassdoor y Google Jobs continúan extrayendo ofertas sin cancelarse**.

### E. Glassdoor & Google Jobs (JobSpy)
- **Mecanismo de acceso**: Extracción web normalizada.
- **Viabilidad real**: **Media**. Google Jobs es particularmente útil para indexar puestos procedentes de portales ATS de empresas (Greenhouse, Lever, Workday) sin tener que configurar cientos de conectores individuales.
- **Mitigación**: Ejecutados como sub-fuentes independientes en el bucle de JobSpy.

---

## 2. Resumen de Tolerancia a Fallos

El sistema no da por garantizada la disponibilidad de ningún conector ni portal:

1. **Aislamiento en dos niveles**:
   - Nivel 1 (Conectores mayores): Tecnoempleo, InfoJobs y JobSpy corren secuencialmente en bloques independientes.
   - Nivel 2 (Sub-portales de JobSpy): Cada portal (`indeed`, `linkedin`, `glassdoor`, `google`) se ejecuta en su propio sub-bloque con control de excepciones individual.
2. **Registro de estado visible para el usuario**:
   - Cada escaneo registra en la base de datos y reporta a Telegram el estado de cada conector y portal (`ok`, `error`, `not_configured`).
   - El usuario sabrá de inmediato si una fuente particular no ha devuelto resultados o ha sufrido una restricción temporal de red.
