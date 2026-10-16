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
