/**
 * Constantes y definiciones compartidas sincronizadas con config/shared_constants.json.
 */

export const APPLICATION_STATUSES = {
  discovered: { label: "Descubierta", badge: "secondary" as const },
  evaluating: { label: "Evaluando...", badge: "warning" as const },
  generating_docs: { label: "Generando documentos...", badge: "warning" as const },
  evaluated: { label: "Evaluada", badge: "outline" as const },
  notified: { label: "Notificada", badge: "warning" as const },
  applied: { label: "Postulada", badge: "default" as const },
  interview: { label: "Entrevista", badge: "success" as const },
  discarded: { label: "Descartada", badge: "destructive" as const },
  rejected: { label: "Rechazada", badge: "destructive" as const },
  archived: { label: "Archivada", badge: "secondary" as const },
};

export type ApplicationStatusKey = keyof typeof APPLICATION_STATUSES;

export const PORTAL_SOURCES: Record<string, { label: string; type: string }> = {
  tecnoempleo: { label: "Tecnoempleo", type: "rss" },
  tecnoempleo_rss: { label: "Tecnoempleo RSS", type: "rss" },
  infojobs: { label: "InfoJobs", type: "api" },
  infojobs_api: { label: "InfoJobs API", type: "api" },
  linkedin: { label: "LinkedIn", type: "scraper" },
  indeed: { label: "Indeed", type: "scraper" },
  glassdoor: { label: "Glassdoor", type: "scraper" },
  google: { label: "Google Jobs", type: "scraper" },
  jobspy: { label: "JobSpy Multi-portal", type: "scraper" },
};

export const SERVICES = ["ollama", "lazyjobfinder"] as const;
export const SERVICE_ACTIONS = ["start", "stop", "restart"] as const;

export const CONFIRMATION_PHRASES = {
  clear_history: "BORRAR_HISTORIAL",
  down_containers: "ELIMINAR_CONTENEDORES",
  destroy_volumes: "DESTRUIR_VOLUMENES_PERMANENTE",
} as const;

export const CV_UPLOAD_LIMITS = {
  max_size_bytes: 5242880,
  max_size_mb: 5,
  allowed_extensions: [".pdf", ".md", ".txt"],
};

export const SCORING = {
  default_threshold: 65,
  high_fit_threshold: 80,
  moderate_fit_threshold: 65,
};
