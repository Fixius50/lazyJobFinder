/**
 * Cliente de API tipado para el panel de administración lazyJobFinder.
 * Comunica de forma transparente con el backend FastAPI local vía proxy /api.
 */

export * from "@/types";
import type {
  ServiceInfo,
  ServicesStatusResponse,
  PreflightResponse,
  JobListItem,
  JobDetail,
  PaginatedJobsResponse,
  ActiveCVInfo,
  SystemLogItem,
  SettingsResponse,
  FilterFacetsResponse,
} from "@/types";

export function getApiBaseUrl(): string {
  if (typeof window !== "undefined") {
    // Si se accede desde Next.js dev server en puerto 3000,
    // se conecta directamente a FastAPI (puerto 8000) usando el mismo hostname (localhost o 127.0.0.1)
    if (window.location.port === "3000") {
      const host = window.location.hostname || "localhost";
      return `http://${host}:8000/api`;
    }
  }
  return "/api";
}

export interface RequestOptions extends RequestInit {
  timeoutMs?: number;
}

async function request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const baseUrl = getApiBaseUrl();
  const url = `${baseUrl}${endpoint}`;
  const timeoutMs = options.timeoutMs ?? 20000; // 20 segundos de timeout por defecto

  const headers: Record<string, string> = {
    ...((options.headers as Record<string, string>) || {}),
  };
  if (options.body) {
    headers["Content-Type"] = "application/json";
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => {
    controller.abort();
  }, timeoutMs);

  const fetchOptions: RequestInit = {
    ...options,
    headers,
    cache: "no-store",
    signal: options.signal || controller.signal,
  };

  const method = options.method || "GET";
  try {
    const response = await fetch(url, fetchOptions);
    clearTimeout(timeoutId);

    if (!response.ok) {
      let errorDetail = `HTTP ${response.status}: ${response.statusText}`;
      try {
        const errorJson = await response.json();
        if (errorJson.detail) {
          errorDetail = typeof errorJson.detail === "string" ? errorJson.detail : JSON.stringify(errorJson.detail);
        }
      } catch {
        // Fallback a texto o status
      }
      const err = new Error(errorDetail);
      console.error(`[API ERROR] ${method} ${url} ->`, errorDetail);
      throw err;
    }

    return await response.json();
  } catch (err: any) {
    clearTimeout(timeoutId);
    if (err.name === "AbortError") {
      const timeoutError = new Error(`Tiempo de espera agotado (${timeoutMs / 1000}s) comunicando con ${url}`);
      console.error(`[API TIMEOUT] ${method} ${url}:`, timeoutError);
      throw timeoutError;
    }
    console.error(`[API NETWORK/SOCKET ERROR] ${method} ${url}:`, err);
    throw err;
  }
}

export const api = {
  getBaseUrl: () => getApiBaseUrl(),

  // 1. Control de Docker y Sistema
  getServicesStatus: () => request<ServicesStatusResponse>("/system/status", { timeoutMs: 10000 }),
  sendServiceAction: async (service: string, action: "start" | "stop" | "restart") => {
    const res = await request<{ success: boolean; message?: string; error?: string }>("/system/action", {
      method: "POST",
      body: JSON.stringify({ service, action }),
      timeoutMs: 35000,
    });
    if (!res.success) {
      throw new Error(res.error || res.message || "Error al ejecutar acción sobre el servicio.");
    }
    return res;
  },
  getSystemLogs: (limit = 100, level?: string, source?: string) => {
    const params = new URLSearchParams({ limit: limit.toString() });
    if (level) params.append("level", level);
    if (source) params.append("source", source);
    return request<SystemLogItem[]>(`/system/logs?${params.toString()}`, { timeoutMs: 15000 });
  },
  clearSystemLogs: () =>
    request<{ success: boolean; deleted_count: number; message: string }>("/system/logs", {
      method: "DELETE",
      timeoutMs: 10000,
    }),
  getContainerLogs: (service: string = "all", tail = 80) =>
    request<{ service: string; logs: string }>(`/system/logs/container?service=${service}&tail=${tail}`, { timeoutMs: 15000 }),

  // 2. CV y Búsqueda
  getActiveCV: () => request<ActiveCVInfo>("/cv/active", { timeoutMs: 10000 }),
  listUploadedCVs: () => request<any[]>("/cv/list", { timeoutMs: 10000 }),
  uploadCV: async (file: File) => {
    const baseUrl = getApiBaseUrl();
    const url = `${baseUrl}/cv/upload`;
    const formData = new FormData();
    formData.append("file", file);

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000);

    try {
      const response = await fetch(url, {
        method: "POST",
        body: formData,
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        const detail = err.detail || `Error al subir CV (HTTP ${response.status})`;
        console.error(`[API ERROR] POST ${url}:`, detail);
        throw new Error(detail);
      }
      return await response.json();
    } catch (err: any) {
      clearTimeout(timeoutId);
      console.error(`[API ERROR] POST ${url}:`, err);
      if (err.name === "AbortError") {
        throw new Error("Tiempo de espera agotado al subir el CV.");
      }
      throw err;
    }
  },
  selectActiveCV: (filename: string) =>
    request<{
      success: boolean;
      selected: string;
      active_info: ActiveCVInfo;
      re_evaluated_jobs?: number;
      message?: string;
    }>("/cv/select", {
      method: "POST",
      body: JSON.stringify({ filename }),
    }),
  deleteCV: (filename: string) =>
    request<{ success: boolean; message: string; active_info: ActiveCVInfo }>(
      `/cv/${encodeURIComponent(filename)}`,
      { method: "DELETE" }
    ),
  previewActiveCV: (filename?: string) =>
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
    }>(`/cv/preview${filename ? `?filename=${encodeURIComponent(filename)}` : ""}`),
  reevaluateCV: () =>
    request<{
      success: boolean;
      re_evaluated_jobs: number;
      active_info: ActiveCVInfo;
      message: string;
    }>("/cv/reevaluate", { method: "POST" }),
  getPreflight: () => request<PreflightResponse>("/search/preflight"),
  triggerSearch: () => request<{ success: boolean; message: string }>("/search/run", { method: "POST" }),
  getSearchStatus: () => request<any>("/search/status"),

  // 3. Candidaturas
  listJobs: (params: {
    search?: string;
    exclude?: string;
    location?: string;
    source?: string;
    status?: string;
    min_score?: number;
    is_remote?: boolean;
    modality?: string;
    modalities?: string[];
    categories?: string[];
    educations?: string[];
    min_experience_years?: number;
    min_salary?: number;
    schedules?: string[];
    contract_types?: string[];
    geo_lat?: number;
    geo_lon?: number;
    geo_radius_km?: number;
    only_ui_saved?: boolean;
    page?: number;
    page_size?: number;
    sort_by?: string;
    sort_order?: string;
  }) => {
    const searchParams = new URLSearchParams();
    if (params.search) searchParams.append("search", params.search);
    if (params.exclude) searchParams.append("exclude", params.exclude);
    if (params.location) searchParams.append("location", params.location);
    if (params.source) searchParams.append("source", params.source);
    if (params.status) searchParams.append("status", params.status);
    if (params.min_score !== undefined && params.min_score !== null)
      searchParams.append("min_score", params.min_score.toString());
    if (params.is_remote !== undefined) searchParams.append("is_remote", params.is_remote ? "true" : "false");
    if (params.modality) searchParams.append("modality", params.modality);
    if (params.modalities && params.modalities.length > 0) {
      params.modalities.forEach((m) => searchParams.append("modalities", m));
    }
    if (params.categories && params.categories.length > 0) {
      params.categories.forEach((c) => searchParams.append("categories", c));
    }
    if (params.educations && params.educations.length > 0) {
      params.educations.forEach((e) => searchParams.append("educations", e));
    }
    if (params.min_experience_years !== undefined && params.min_experience_years > 0) {
      searchParams.append("min_experience_years", params.min_experience_years.toString());
    }
    if (params.min_salary !== undefined && params.min_salary > 0) {
      searchParams.append("min_salary", params.min_salary.toString());
    }
    if (params.schedules && params.schedules.length > 0) {
      params.schedules.forEach((s) => searchParams.append("schedules", s));
    }
    if (params.contract_types && params.contract_types.length > 0) {
      params.contract_types.forEach((ct) => searchParams.append("contract_types", ct));
    }
    if (
      params.geo_radius_km !== undefined &&
      params.geo_radius_km > 0 &&
      params.geo_lat !== undefined &&
      params.geo_lon !== undefined
    ) {
      searchParams.append("geo_lat", params.geo_lat.toString());
      searchParams.append("geo_lon", params.geo_lon.toString());
      searchParams.append("geo_radius_km", params.geo_radius_km.toString());
    }
    if (params.only_ui_saved !== undefined)
      searchParams.append("only_ui_saved", params.only_ui_saved ? "true" : "false");
    if (params.page) searchParams.append("page", params.page.toString());
    if (params.page_size) searchParams.append("page_size", params.page_size.toString());
    if (params.sort_by) searchParams.append("sort_by", params.sort_by);
    if (params.sort_order) searchParams.append("sort_order", params.sort_order);

    return request<PaginatedJobsResponse>(`/jobs?${searchParams.toString()}`);
  },
  getFilterFacets: () => request<FilterFacetsResponse>("/jobs/facets"),
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
    `${getApiBaseUrl()}/jobs/${jobId}/document/${docType}`,

  // 4. Configuración
  getSettings: () => request<SettingsResponse>("/settings"),
  updateChannels: (payload: {
    guardar_en_interfaz?: boolean;
    enviar_telegram: boolean;
    telegram_user_id?: string;
    telegram_adjuntar_docs?: boolean;
    umbral_minimo_puntuacion?: number;
    infojobs_client_id?: string;
    infojobs_client_secret?: string;
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
