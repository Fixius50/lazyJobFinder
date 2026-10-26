/**
 * Definiciones de tipos unificadas para el panel de administración lazyJobFinder.
 * Centraliza los modelos de datos del sistema, ofertas, CV, ajustes y registros.
 */

// =============================================================================
// 1. SISTEMA Y SERVICIOS DOCKER
// =============================================================================

export interface ServiceInfo {
  status: "saludable" | "arrancando" | "detenido" | "error" | string;
  health: string;
  container_name: string;
  id?: string;
  raw_state?: string;
}

export interface ServicesStatusResponse {
  services: {
    ollama: ServiceInfo;
    lazyjobfinder: ServiceInfo;
    [key: string]: ServiceInfo;
  };
  pipeline: {
    is_running: boolean;
    has_run_today: boolean;
    last_run?: {
      id: number;
      started_at: string;
      finished_at: string;
      status: string;
      total_found: number;
      new_jobs: number;
      relevant_jobs: number;
    } | null;
  };
}

export interface PreflightResponse {
  can_execute: boolean;
  ollama: {
    healthy: boolean;
    url: string;
    models: string[];
    error?: string | null;
  };
  pipeline: {
    is_running: boolean;
    locked: boolean;
  };
  database: {
    healthy: boolean;
    error?: string | null;
  };
}

// =============================================================================
// 2. OFERTAS Y CANDIDATURAS
// =============================================================================

export interface JobListItem {
  id: number;
  title: string;
  company: string;
  location: string;
  is_remote: number;
  source: string;
  canonical_url: string;
  salary_min?: number | null;
  salary_max?: number | null;
  salary_currency?: string;
  date_posted?: string;
  created_at: string;
  updated_at: string;
  status: string;
  duplicate_of_id?: number | null;
  similarity_score?: number | null;
  alternate_sources?: string;
  telegram_notified: number;
  ui_saved: number;
  score?: number | null;
  fit_level?: string | null;
  should_apply?: number | null;
  has_cv: boolean;
  has_letter: boolean;
}

export interface PaginatedJobsResponse {
  items: JobListItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  has_cv?: boolean;
}

export interface JobDetail extends JobListItem {
  description?: string;
  matched_skills: string[];
  missing_skills: string[];
  strengths: string[];
  gaps: string[];
  reasoning?: string;
  diff_summary?: string;
  cv_pdf_path?: string;
  cv_md_path?: string;
  letter_pdf_path?: string;
  letter_md_path?: string;
  evaluated_at?: string;
  documents_generated_at?: string;
}

export interface JobFilterParams {
  search?: string;
  source?: string;
  status?: string;
  min_score?: number;
  is_remote?: boolean;
  modality?: "all" | "presencial" | "teletrabajo" | "hibrido" | string;
  time_range?: "all" | "24h" | "7d" | "30d" | string;
  only_ui_saved?: boolean;
  page?: number;
  page_size?: number;
  sort_by?: string;
  sort_order?: string;
}

export interface FacetItem {
  id: string;
  label: string;
  count: number;
}

export interface FilterFacetsResponse {
  sources: FacetItem[];
  modalities: FacetItem[];
  categories: FacetItem[];
  educations: FacetItem[];
  schedules: FacetItem[];
  contract_types: FacetItem[];
  salary_stats: {
    min: number;
    max: number;
    currency: string;
  };
  top_locations: { name: string; count: number }[];
  total_jobs: number;
}

// =============================================================================
// 3. CURRÍCULUM VITAE (CV)
// =============================================================================

export interface ActiveCVInfo {
  type: "canonical" | "custom" | "none";
  filename: string;
  path: string;
  size_bytes: number;
  modified_at: string;
  is_default: boolean;
  description: string;
  search_terms?: string[];
  primary_role?: string;
}

// =============================================================================
// 4. CONFIGURACIÓN Y CANALES
// =============================================================================

export interface SettingsResponse {
  busqueda: {
    terminos: string[];
    ubicaciones: string[];
    filtros_exclusion: string[];
    antiguedad_horas: number;
    limite_por_fuente: number;
  };
  fuentes: Record<string, any>;
  evaluacion: {
    umbral_minimo_puntuacion: number;
    generar_documentos: boolean;
    idioma_documentos: string;
  };
  notificaciones: {
    guardar_en_interfaz: boolean;
    enviar_telegram: boolean;
    telegram?: {
      habilitado: boolean;
      adjuntar_documentos: boolean;
      notificar_solo_superan_umbral: boolean;
      notificar_resumen_vacio: boolean;
      allowed_user_id?: string;
    };
  };
  horario: {
    hora: number;
    minuto: number;
  };
  secrets_status: {
    telegram_configured: boolean;
    telegram_token_present?: boolean;
    telegram_user_id?: string;
    telegram_bot_username?: string;
    infojobs_configured: boolean;
    infojobs_client_id?: string;
    infojobs_secret_present?: boolean;
  };
  privacy_notice: {
    telegram_transmission_note: string;
  };
}

// =============================================================================
// 5. REGISTROS Y AUDITORÍA
// =============================================================================

export interface SystemLogItem {
  id: number;
  timestamp: string;
  level: "INFO" | "WARNING" | "ERROR" | "CRITICAL";
  source: string;
  message: string;
  details?: string;
}
