/**
 * Cliente de API tipado para el panel de administración lazyJobFinder.
 * Comunica de forma transparente con el backend FastAPI local vía proxy /api.
 */

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

export interface ActiveCVInfo {
  type: "canonical" | "custom" | "none";
  filename: string;
  path: string;
  size_bytes: number;
  modified_at: string;
  is_default: boolean;
  description: string;
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

export interface SystemLogItem {
  id: number;
  timestamp: string;
  level: "INFO" | "WARNING" | "ERROR" | "CRITICAL";
  source: string;
  message: string;
  details?: string;
}

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
    };
  };
  horario: {
    hora: number;
    minuto: number;
  };
  secrets_status: {
    telegram_configured: boolean;
    infojobs_configured: boolean;
  };
  privacy_notice: {
    telegram_transmission_note: string;
  };
}

const API_BASE = "/api";

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const headers = {
    "Content-Type": "application/json",
    ...options.headers,
  };

  const response = await fetch(url, { ...options, headers });
  if (!response.ok) {
    let errorDetail = `Error ${response.status}: ${response.statusText}`;
    try {
      const errorJson = await response.json();
      if (errorJson.detail) {
        errorDetail = typeof errorJson.detail === "string" ? errorJson.detail : JSON.stringify(errorJson.detail);
      }
    } catch {
      // Usar statusText predeterminado si no hay cuerpo JSON
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

export const api = {
  // 1. Control de Docker y Sistema
  getServicesStatus: () => request<ServicesStatusResponse>("/system/status"),
  sendServiceAction: (service: string, action: "start" | "stop" | "restart") =>
    request<{ success: boolean; message: string }>("/system/action", {
      method: "POST",
      body: JSON.stringify({ service, action }),
    }),
  getSystemLogs: (limit = 100, level?: string, source?: string) => {
    const params = new URLSearchParams({ limit: limit.toString() });
    if (level) params.append("level", level);
    if (source) params.append("source", source);
    return request<SystemLogItem[]>(`/system/logs?${params.toString()}`);
  },
  getContainerLogs: (service: string = "all", tail = 80) =>
    request<{ service: string; logs: string }>(`/system/logs/container?service=${service}&tail=${tail}`),

  // 2. CV y Búsqueda
  getActiveCV: () => request<ActiveCVInfo>("/cv/active"),
  listUploadedCVs: () => request<any[]>("/cv/list"),
  uploadCV: async (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    const response = await fetch(`${API_BASE}/cv/upload`, {
      method: "POST",
      body: formData,
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || "Error subiendo el archivo CV.");
    }
    return response.json();
  },
  selectActiveCV: (filename: string) =>
    request<{ success: boolean; selected: string; active_info: ActiveCVInfo }>("/cv/select", {
      method: "POST",
      body: JSON.stringify({ filename }),
    }),
  previewActiveCV: () =>
    request<{
      filename: string;
      type: string;
      extension: string;
      char_count: number;
      word_count: number;
      text_preview: string;
      full_text_length: number;
      is_default: boolean;
      error?: string;
    }>("/cv/preview"),
  getPreflight: () => request<PreflightResponse>("/search/preflight"),
  triggerSearch: () => request<{ success: boolean; message: string }>("/search/run", { method: "POST" }),
  getSearchStatus: () => request<any>("/search/status"),

  // 3. Candidaturas
  listJobs: (params: {
    search?: string;
    source?: string;
    status?: string;
    min_score?: number;
    is_remote?: boolean;
    only_ui_saved?: boolean;
    page?: number;
    page_size?: number;
    sort_by?: string;
    sort_order?: string;
  }) => {
    const searchParams = new URLSearchParams();
    if (params.search) searchParams.append("search", params.search);
    if (params.source) searchParams.append("source", params.source);
    if (params.status) searchParams.append("status", params.status);
    if (params.min_score !== undefined && params.min_score !== null)
      searchParams.append("min_score", params.min_score.toString());
    if (params.is_remote !== undefined) searchParams.append("is_remote", params.is_remote ? "true" : "false");
    if (params.only_ui_saved !== undefined)
      searchParams.append("only_ui_saved", params.only_ui_saved ? "true" : "false");
    if (params.page) searchParams.append("page", params.page.toString());
    if (params.page_size) searchParams.append("page_size", params.page_size.toString());
    if (params.sort_by) searchParams.append("sort_by", params.sort_by);
    if (params.sort_order) searchParams.append("sort_order", params.sort_order);

    return request<PaginatedJobsResponse>(`/jobs?${searchParams.toString()}`);
  },
  getJobDetail: (jobId: number) => request<JobDetail>(`/jobs/${jobId}`),
  updateJobStatus: (jobId: number, status: string) =>
    request<{ success: boolean; status: string }>(`/jobs/${jobId}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),
  updateJobChannel: (jobId: number, payload: { telegram_notified?: number; ui_saved?: number }) =>
    request<{ success: boolean }>(`/jobs/${jobId}/channel`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  getDocumentUrl: (jobId: number, docType: "cv_pdf" | "cv_md" | "letter_pdf" | "letter_md") =>
    `${API_BASE}/jobs/${jobId}/document/${docType}`,

  // 4. Configuración
  getSettings: () => request<SettingsResponse>("/settings"),
  updateChannels: (payload: {
    guardar_en_interfaz: boolean;
    enviar_telegram: boolean;
    telegram_adjuntar_docs?: boolean;
    umbral_minimo_puntuacion?: number;
  }) =>
    request<{ success: boolean; message: string }>("/settings/channels", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  updateSearchConfig: (payload: {
    terminos: string[];
    ubicaciones: string[];
    filtros_exclusion: string[];
    antiguedad_horas: number;
    limite_por_fuente: number;
  }) =>
    request<{ success: boolean; message: string }>("/settings/search", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),

  // 5. Mantenimiento
  maintenanceStop: () => request<{ success: boolean; message: string }>("/maintenance/stop", { method: "POST" }),
  maintenanceDown: (removeVolumes: boolean, confirmationPhrase: string) =>
    request<{ success: boolean; message: string }>("/maintenance/down-containers", {
      method: "POST",
      body: JSON.stringify({
        remove_volumes: removeVolumes,
        confirmation_phrase: confirmationPhrase,
      }),
    }),
  maintenanceCleanDocs: (jobIds: number[], confirmation: boolean) =>
    request<{ success: boolean; deleted_count: number; message: string }>("/maintenance/clean-docs", {
      method: "POST",
      body: JSON.stringify({ job_ids: jobIds, confirmation }),
    }),
  maintenanceClearHistory: (confirmationPhrase: string) =>
    request<{ success: boolean; message: string; details: any }>("/maintenance/clear-history", {
      method: "POST",
      body: JSON.stringify({ confirmation_phrase: confirmationPhrase }),
    }),
};
