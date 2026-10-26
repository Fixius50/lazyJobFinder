"use client";

import React, { useEffect, useState, useRef, useMemo } from "react";
import {
  Briefcase,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  FileCheck,
  Sparkles,
  AlertTriangle,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { InfoTooltip } from "@/components/ui/info-tooltip";
import { CvManager } from "@/components/features/cv/cv-manager";
import { JobCard } from "@/components/features/jobs/job-card";
import { JobFilters, EXPERIENCE_STEPS, SALARY_STEPS } from "@/components/features/jobs/job-filters";
import { JobDetailDialog } from "@/components/features/jobs/job-detail-dialog";
import { PurgeHistoryButton } from "@/components/features/maintenance/purge-history-card";
import { JobListItem, JobDetail, PaginatedJobsResponse, FilterFacetsResponse, api, hasValidCv } from "@/lib/api";

interface FilterState {
  searchTerm: string;
  exclusionTerm: string;
  selectedSource: string;
  selectedStatus: string;
  minScore: number;
  timeRange: string;
  locationName: string;
  isAllLocations: boolean;
  selectedModalities: string[];
  selectedCategories: string[];
  selectedEducations: string[];
  minExperienceStep: number;
  minSalaryStep: number;
  selectedSchedules: string[];
  selectedContractTypes: string[];
}

const INITIAL_FILTERS: FilterState = {
  searchTerm: "",
  exclusionTerm: "",
  selectedSource: "",
  selectedStatus: "",
  minScore: 0,
  timeRange: "all",
  locationName: "",
  isAllLocations: true,
  selectedModalities: [],
  selectedCategories: [],
  selectedEducations: [],
  minExperienceStep: 0,
  minSalaryStep: 0,
  selectedSchedules: [],
  selectedContractTypes: [],
};

/**
 * Filtra una vacante de empleo en memoria del navegador de forma instantánea
 * sin realizar llamadas redundantes a la API de FastAPI.
 */
function filterJobLocally(job: JobListItem, filters: FilterState): boolean {
  // 1. Puntuación mínima de afinidad IA
  if (filters.minScore > 0 && (job.score ?? 0) < filters.minScore) {
    return false;
  }

  // 2. Estado de postulación
  if (filters.selectedStatus && filters.selectedStatus.trim()) {
    if (job.status !== filters.selectedStatus) return false;
  }

  // 3. Portal / Fuente
  if (filters.selectedSource && filters.selectedSource.trim()) {
    const src = filters.selectedSource.toLowerCase().trim();
    const jobSrc = (job.source || "").toLowerCase().trim();
    if (src === "jobspy") {
      if (!["indeed", "linkedin", "glassdoor", "google", "jobspy"].includes(jobSrc)) return false;
    } else if (src === "infojobs" || src === "infojobs_api") {
      if (!jobSrc.includes("infojobs")) return false;
    } else if (src === "tecnoempleo" || src === "tecnoempleo_rss") {
      if (!jobSrc.includes("tecnoempleo")) return false;
    } else {
      if (jobSrc !== src) return false;
    }
  }

  const title = (job.title || "").toLowerCase();
  const company = (job.company || "").toLowerCase();
  const location = (job.location || "").toLowerCase();
  const description = (job.description || "").toLowerCase();
  const fullSearchText = `${title} ${company} ${location} ${description}`;

  // 4. Términos de búsqueda (comas = coincidencia con al menos una frase)
  if (filters.searchTerm && filters.searchTerm.trim()) {
    const rawTerms = filters.searchTerm
      .split(",")
      .map((t) => t.trim().toLowerCase())
      .filter(Boolean);
    if (rawTerms.length > 0) {
      const matchesAny = rawTerms.some((term) => {
        const words = term.split(/\s+/).filter(Boolean);
        return words.every((w) => fullSearchText.includes(w));
      });
      if (!matchesAny) return false;
    }
  }

  // 5. Términos de exclusión (comas = descarta si contiene cualquiera de las palabras)
  if (filters.exclusionTerm && filters.exclusionTerm.trim()) {
    const exclusions = filters.exclusionTerm
      .split(",")
      .map((e) => e.trim().toLowerCase())
      .filter(Boolean);
    const excludeScope = `${title} ${description}`;
    for (const exc of exclusions) {
      if (excludeScope.includes(exc)) {
        return false;
      }
    }
  }

  // 6. Ubicación y teletrabajo
  if (!filters.isAllLocations && filters.locationName && filters.locationName.trim()) {
    const loc = filters.locationName.trim().toLowerCase();
    if (loc !== "all" && loc !== "todas" && loc !== "cualquiera" && loc !== "mi ubicación") {
      const isRemote = job.is_remote === 1 || location.includes("remot") || location.includes("teletrabaj");
      if (!isRemote && !location.includes(loc)) {
        return false;
      }
    }
  }

  // 7. Modalidades (Checkboxes)
  if (filters.selectedModalities && filters.selectedModalities.length > 0) {
    const isRemote = job.is_remote === 1 || location.includes("remot") || location.includes("teletrabaj") || title.includes("remot") || title.includes("teletrabaj");
    const isHybrid = /h[ií]brid/i.test(`${location} ${title} ${description}`);
    const isPresencial = !isRemote && !isHybrid;

    const matchesMod = filters.selectedModalities.some((mod) => {
      const m = mod.toLowerCase();
      if (m === "teletrabajo" || m === "remoto") return isRemote;
      if (m === "hibrido") return isHybrid;
      if (m === "presencial") return isPresencial;
      return false;
    });
    if (!matchesMod) return false;
  }

  // 8. Categorías / Competencias
  if (filters.selectedCategories && filters.selectedCategories.length > 0) {
    const skillsText = Array.isArray(job.matched_skills)
      ? job.matched_skills.join(" ").toLowerCase()
      : typeof job.matched_skills === "string"
      ? job.matched_skills.toLowerCase()
      : "";
    const catScope = `${title} ${description} ${skillsText}`;
    const matchesCat = filters.selectedCategories.some((cat) => {
      const c = cat.toLowerCase().trim();
      return c && catScope.includes(c);
    });
    if (!matchesCat) return false;
  }

  // 9. Formación mínima
  if (filters.selectedEducations && filters.selectedEducations.length > 0) {
    const eduScope = `${job.education_level || ""} ${description}`.toLowerCase();
    const matchesEdu = filters.selectedEducations.some((edu) => {
      const e = edu.toLowerCase().trim();
      return e && eduScope.includes(e);
    });
    if (!matchesEdu) return false;
  }

  // 10. Experiencia
  if (filters.minExperienceStep > 0) {
    const step = filters.minExperienceStep;
    const expScope = `${title} ${description}`;
    if (step === 1) {
      if (!/junior|jr|pr[áa]cticas|beca|sin experiencia|reci[eé]n titulado|0-1 a[ñn]o/i.test(expScope)) return false;
    } else if (step === 2) {
      if (!/1\+?\s*a[ñn]o|al menos 1 a[ñn]o|m[íi]nimo 1 a[ñn]o/i.test(expScope)) return false;
    } else if (step === 3) {
      if (!/2\+?\s*a[ñn]o|al menos 2 a[ñn]o|m[íi]nimo 2 a[ñn]o/i.test(expScope)) return false;
    } else if (step === 4) {
      if (!/3\+?\s*a[ñn]o|al menos 3 a[ñn]o|m[íi]nimo 3 a[ñn]o/i.test(expScope)) return false;
    } else if (step >= 5) {
      if (!/5\+?\s*a[ñn]o|al menos 5 a[ñn]o|senior|lead/i.test(expScope)) return false;
    }
  }

  // 11. Salario mínimo
  if (filters.minSalaryStep > 0) {
    const minVal = SALARY_STEPS[filters.minSalaryStep]?.value || 0;
    if (minVal > 0) {
      const maxSal = job.salary_max ?? 0;
      const minSal = job.salary_min ?? 0;
      if (maxSal < minVal && minSal < minVal) {
        return false;
      }
    }
  }

  // 12. Jornada laboral
  if (filters.selectedSchedules && filters.selectedSchedules.length > 0) {
    const schedScope = `${job.schedule || ""} ${description}`.toLowerCase();
    const matchesSched = filters.selectedSchedules.some((sc) => {
      const s = sc.toLowerCase().trim();
      return s && schedScope.includes(s);
    });
    if (!matchesSched) return false;
  }

  // 13. Tipo de contrato
  if (filters.selectedContractTypes && filters.selectedContractTypes.length > 0) {
    const contractScope = `${job.contract_type || ""} ${description}`.toLowerCase();
    const matchesContract = filters.selectedContractTypes.some((ct) => {
      const c = ct.toLowerCase().trim();
      return c && contractScope.includes(c);
    });
    if (!matchesContract) return false;
  }

  // 14. Antigüedad
  if (filters.timeRange && filters.timeRange !== "all") {
    const dateStr = job.date_posted || job.created_at;
    if (dateStr) {
      const postedTime = new Date(dateStr).getTime();
      const now = Date.now();
      if (!isNaN(postedTime)) {
        const diffHours = (now - postedTime) / (1000 * 60 * 60);
        if (filters.timeRange === "24h" && diffHours > 24) return false;
        if (filters.timeRange === "7d" && diffHours > 24 * 7) return false;
        if (filters.timeRange === "30d" && diffHours > 24 * 30) return false;
      }
    }
  }

  return true;
}

export function ApplicationsView() {
  const [rawJobs, setRawJobs] = useState<JobListItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [apiError, setApiError] = useState<string | null>(null);
  const [showCvPanel, setShowCvPanel] = useState<boolean>(true);
  const [facets, setFacets] = useState<FilterFacetsResponse | null>(null);

  // Filtros unificados en un único estado atómico
  const [filters, setFilters] = useState<FilterState>(INITIAL_FILTERS);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const currentPageRef = useRef<number>(currentPage);

  useEffect(() => {
    currentPageRef.current = currentPage;
  }, [currentPage]);

  const updateFilter = <K extends keyof FilterState>(key: K, value: FilterState[K]) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setCurrentPage(1);
  };

  // Filtrado 100% reactivo en cliente sobre las ofertas traídas sin llamadas de red redundantes
  const filteredJobs = useMemo(() => {
    return rawJobs.filter((job) => filterJobLocally(job, filters));
  }, [rawJobs, filters]);

  const PAGE_SIZE = 20;
  const totalPages = Math.max(1, Math.ceil(filteredJobs.length / PAGE_SIZE));
  const safeCurrentPage = Math.min(currentPage, totalPages);

  const paginatedItems = useMemo(() => {
    const startIndex = (safeCurrentPage - 1) * PAGE_SIZE;
    return filteredJobs.slice(startIndex, startIndex + PAGE_SIZE);
  }, [filteredJobs, safeCurrentPage]);

  // Modal de Detalle
  const [detailModalOpen, setDetailModalOpen] = useState<boolean>(false);
  const [selectedJobDetail, setSelectedJobDetail] = useState<JobDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState<boolean>(false);

  const [hasActiveCv, setHasActiveCv] = useState<boolean>(false);
  const [searching, setSearching] = useState<boolean>(false);

  const loadFacets = async () => {
    try {
      const data = await api.getFilterFacets();
      setFacets(data);
    } catch (e) {
      console.warn("Fallo cargando facetas dinámicas:", e);
    }
  };

  const pollSearchStatus = async () => {
    try {
      const status = await api.getSearchStatus();
      if (status && status.is_running !== undefined) {
        const running = Boolean(status.is_running);
        setSearching(running);
        return running;
      }
    } catch {
      // Ignorar fallos puntuales
    }
    return false;
  };

  const handleTriggerSearch = async () => {
    try {
      setSearching(true);
      const res = await api.triggerSearch();
      alert(res.message || "Búsqueda de empleo iniciada en los portales con los términos del CV activo.");
      setTimeout(() => pollSearchStatus(), 800);
    } catch (e: any) {
      alert(`Error al iniciar búsqueda: ${e.message}`);
      setSearching(false);
    }
  };

  const fetchJobs = async (silent: boolean = false) => {
    if (!silent) {
      setLoading(true);
    }
    try {
      const res = await api.listJobs({
        page: 1,
        page_size: 500,
        sort_by: "created_at",
        sort_order: "desc",
      });
      setRawJobs(res.items || []);
      setApiError(null);
      if (res.has_cv !== undefined) {
        setHasActiveCv(res.has_cv);
      }
    } catch (err: any) {
      console.error("[ApplicationsView] Error obteniendo ofertas:", err);
      setApiError(err.message || "Error al conectar con la API local de lazyJobFinder.");
    } finally {
      if (!silent) {
        setLoading(false);
      }
    }
  };

  const handlePageChange = (newPage: number) => {
    setCurrentPage(newPage);
  };

  // Carga inicial y sincronización desacoplada
  useEffect(() => {
    loadFacets();
    fetchJobs();
    api.getActiveCV()
      .then((cv) => setHasActiveCv(hasValidCv(cv)))
      .catch(() => setHasActiveCv(false));

    pollSearchStatus();
    let wasSearching = false;
    let pollCount = 0;

    const interval = setInterval(async () => {
      pollCount += 1;
      const isRunning = await pollSearchStatus();
      if (isRunning) {
        wasSearching = true;
        fetchJobs(true);
      } else if (wasSearching) {
        wasSearching = false;
        setSearching(false);
        fetchJobs(false);
        loadFacets();
      } else if (pollCount % 4 === 0) {
        fetchJobs(true);
      }
    }, 2500);
    return () => clearInterval(interval);
  }, []);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setCurrentPage(1);
    // Filtrado en memoria sin llamar al backend
  };

  const handleResetFilters = () => {
    setFilters(INITIAL_FILTERS);
    setCurrentPage(1);
  };

  const handleSaveCriteria = async () => {
    try {
      const terminos = filters.searchTerm.split(",").map((t) => t.trim()).filter(Boolean);
      const exclusiones = filters.exclusionTerm.split(",").map((e) => e.trim()).filter(Boolean);

      await api.updateSearchConfig({
        terminos: terminos,
        ubicaciones: !filters.isAllLocations ? [filters.locationName] : ["Spain", "Remoto"],
        filtros_exclusion: exclusiones,
        antiguedad_horas: 48,
        limite_por_fuente: 15,
      });
      alert("Criterios de búsqueda y exclusiones guardados en la configuración de los conectores.");
    } catch (e: any) {
      alert(`Error al guardar criterios: ${e.message}`);
    }
  };

  const handleOpenDetail = async (jobId: number) => {
    setDetailLoading(true);
    setDetailModalOpen(true);
    try {
      const detail = await api.getJobDetail(jobId);
      setSelectedJobDetail(detail);
    } catch (err: any) {
      alert(`Error al cargar detalle: ${err.message}`);
      setDetailModalOpen(false);
    } finally {
      setDetailLoading(false);
    }
  };

  const handleUpdateStatus = async (jobId: number, newStatus: string) => {
    try {
      await api.updateJobStatus(jobId, newStatus);
      if (selectedJobDetail && selectedJobDetail.id === jobId) {
        setSelectedJobDetail({ ...selectedJobDetail, status: newStatus });
      }
      setRawJobs((prev) =>
        prev.map((j) => (j.id === jobId ? { ...j, status: newStatus } : j))
      );
    } catch (err: any) {
      alert(`Error al actualizar estado: ${err.message}`);
    }
  };

  const handleRefresh = async () => {
    try {
      setLoading(true);
      const cv = await api.getActiveCV().catch(() => null);
      setHasActiveCv(hasValidCv(cv));
      await pollSearchStatus();
      await loadFacets();
      await fetchJobs(false);
    } catch (e) {
      console.error("Error al actualizar candidaturas:", e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4 sm:space-y-6 w-full">
      {/* Encabezado fluido con Título + CV | Indicador IA minimalista en el centro | Acciones globales */}
      <div className="flex flex-col xl:flex-row xl:items-center justify-between gap-3 pb-3 border-b border-border/50">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1.5 shrink-0">
            <h2 className="text-lg sm:text-xl font-bold tracking-tight">Candidaturas y Ofertas</h2>
            <InfoTooltip content="Registro consolidado en SQLite con puntuaciones de afinidad IA y documentos ATS generados." />
          </div>

          <div className="h-5 w-px bg-border/60 mx-1 hidden sm:block" />

          {/* Bloque en una sola línea del CV Activo: Currículum Activo, ?, Desplegable, Ojo, Subir, Borrar */}
          <CvManager
            onCvChanged={(activeInfo) => {
              setHasActiveCv(hasValidCv(activeInfo));
              loadFacets();
              fetchJobs();
            }}
          />
        </div>

        {/* Indicador minimalista en el hueco superior: entre el CV y las acciones (Actualizar, etc.) */}
        {searching && (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full border border-primary/30 bg-primary/10 text-primary text-xs shadow-xs animate-in fade-in duration-200">
            <Sparkles className="h-3.5 w-3.5 animate-spin text-primary shrink-0" />
            <span className="font-medium whitespace-nowrap">
              Buscando ofertas con IA...
            </span>
            <span className="h-3 w-px bg-primary/30 hidden sm:inline-block" />
            <span className="text-2xs text-muted-foreground whitespace-nowrap hidden sm:inline-block">
              {rawJobs.length > 0
                ? `${rawJobs.length} encontradas hasta el momento`
                : "Rastreando Indeed, LinkedIn y Glassdoor..."}
            </span>
          </div>
        )}

        <div className="flex flex-wrap items-center gap-2">
          {/* Botón Buscar Ofertas Ahora (visible solo si hay CV activo y NO se está buscando ofertas) */}
          {hasActiveCv && !searching && (
            <Button
              size="sm"
              onClick={handleTriggerSearch}
              className="flex items-center gap-1.5 h-8 text-xs bg-primary text-primary-foreground hover:bg-primary/90 font-medium shadow-sm transition-all"
              title="Buscar nuevas ofertas en portales globales con los términos de tu CV activo"
            >
              <Sparkles className="h-3.5 w-3.5 text-primary-foreground" />
              <span>Buscar Ofertas Ahora</span>
            </Button>
          )}

          {/* Botón Actualizar */}
          <Button
            size="sm"
            variant="outline"
            onClick={handleRefresh}
            disabled={loading}
            className="flex items-center gap-1.5 h-8 text-xs"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
            Actualizar
          </Button>

          {/* Botón de Purga / Vaciar Historial sin la tarjeta */}
          <PurgeHistoryButton
            onHistoryCleared={() => {
              fetchJobs();
              loadFacets();
            }}
          />

          {/* Botón Ocultar / Mostrar Filtros (solo visible cuando hay un CV activo) */}
          {hasActiveCv && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => setShowCvPanel(!showCvPanel)}
              className="flex items-center gap-1.5 h-8 text-xs"
            >
              <FileCheck className="h-3.5 w-3.5 text-primary" />
              {showCvPanel ? "Ocultar Filtros" : "Mostrar Filtros"}
            </Button>
          )}
        </div>
      </div>

      {/* Estructura: Filtros laterales (solo si hay CV activo y no están ocultos) | Listado a la Derecha */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 sm:gap-6 items-start">
        {hasActiveCv && showCvPanel && (
          <aside className="lg:col-span-4 xl:col-span-3 space-y-4">
            <JobFilters
              facets={facets}
              filters={filters}
              onFilterChange={updateFilter}
              onSubmitSearch={handleSearchSubmit}
              onResetFilters={handleResetFilters}
              onSaveCriteria={handleSaveCriteria}
            />
          </aside>
        )}

        <section className={`${hasActiveCv && showCvPanel ? "lg:col-span-8 xl:col-span-9" : "lg:col-span-12"} space-y-4`}>
          {/* Listado de Ofertas en cuadrícula */}
          <div className="space-y-3">

            {/* Banner de error explícito de comunicación sin fallbacks engañosos */}
            {apiError && (
              <div className="p-3 rounded-lg border border-destructive/30 bg-destructive/10 text-destructive text-xs flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 shrink-0" />
                  <span>Error de comunicación directa con el backend: {apiError}</span>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => fetchJobs()}
                  className="h-7 text-xs border-destructive/30 hover:bg-destructive/15 text-destructive"
                >
                  Reintentar
                </Button>
              </div>
            )}

            {/* Cuadrícula de Ofertas: Si hay ofertas encontradas, mostrar siempre una tarjeta por cada oferta encontrada */}
            {paginatedItems.length > 0 ? (
              <div
                className={`grid grid-cols-1 sm:grid-cols-2 ${
                  showCvPanel
                    ? "lg:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-4"
                    : "lg:grid-cols-3 xl:grid-cols-5 2xl:grid-cols-5"
                } gap-3 sm:gap-3.5`}
              >
                {paginatedItems.map((job: JobListItem) => (
                  <JobCard
                    key={job.id}
                    job={job}
                    onOpenDetail={handleOpenDetail}
                  />
                ))}
              </div>
            ) : searching || loading ? (
              /* Si aún no hay ofertas en base de datos y está cargando/buscando, mostrar tarjetas individuales en carga */
              <div
                className={`grid grid-cols-1 sm:grid-cols-2 ${
                  showCvPanel
                    ? "lg:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-4"
                    : "lg:grid-cols-3 xl:grid-cols-5 2xl:grid-cols-5"
                } gap-3 sm:gap-3.5`}
              >
                {[...Array(8)].map((_, i) => (
                  <Card
                    key={i}
                    className="border border-border/60 bg-card/60 backdrop-blur-xs p-3.5 space-y-3 animate-pulse overflow-hidden relative shadow-xs"
                  >
                    <div className="flex items-center justify-between">
                      <div className="h-4 w-16 bg-primary/20 rounded-full" />
                      <div className="h-3.5 w-12 bg-muted rounded" />
                    </div>
                    <div className="space-y-1.5 pt-1">
                      <div className="h-4 bg-muted/80 rounded w-4/5" />
                      <div className="h-3 bg-muted/50 rounded w-3/5" />
                    </div>
                    <div className="pt-2 border-t border-border/30 space-y-2">
                      <div className="flex items-center justify-between">
                        <div className="h-3 bg-muted/40 rounded w-1/3" />
                        <div className="h-3 bg-muted/40 rounded w-1/4" />
                      </div>
                      <div className="h-1.5 bg-primary/20 rounded-full w-full" />
                    </div>
                    <div className="flex items-center justify-center pt-2 text-2xs text-muted-foreground/80 gap-1.5">
                      <RefreshCw className="h-3 w-3 animate-spin text-primary" />
                      <span>Cargando oferta {i + 1}...</span>
                    </div>
                  </Card>
                ))}
              </div>
            ) : (
              /* Sin ofertas */
              <Card className="border-dashed bg-card/40">
                <CardContent className="flex flex-col items-center justify-center py-16 text-center text-muted-foreground space-y-3">
                  <Briefcase className="h-10 w-10 text-muted-foreground/50" />
                  <p className="text-sm font-semibold text-foreground">
                    {!hasActiveCv
                      ? "Sin currículum activo seleccionado"
                      : "No se encontraron candidaturas"}
                  </p>
                  <p className="text-xs max-w-md text-muted-foreground">
                    {!hasActiveCv
                      ? "Sube o selecciona un currículum en la barra superior para activar los filtros y la búsqueda personalizada de ofertas."
                      : "No hay ofertas que coincidan con los filtros aplicados o aún no has lanzado una búsqueda."}
                  </p>
                </CardContent>
              </Card>
            )}

            {/* Paginación fluida en cliente */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between pt-4 border-t text-xs text-muted-foreground">
                <div>
                  Mostrando {paginatedItems.length} de {filteredJobs.length} ofertas
                  {filteredJobs.length !== rawJobs.length && (
                    <span className="text-muted-foreground/75">
                      {" "}(filtradas de {rawJobs.length} cargadas)
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-1">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handlePageChange(Math.max(1, safeCurrentPage - 1))}
                    disabled={safeCurrentPage <= 1 || loading}
                    className="h-8 px-2"
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                  <span className="px-2 font-medium text-foreground">
                    Página {safeCurrentPage} de {totalPages}
                  </span>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handlePageChange(Math.min(totalPages, safeCurrentPage + 1))}
                    disabled={safeCurrentPage >= totalPages || loading}
                    className="h-8 px-2"
                  >
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            )}
          </div>
        </section>
      </div>

      {/* Modal de Detalle de Oferta Modular */}
      <JobDetailDialog
        open={detailModalOpen}
        onOpenChange={setDetailModalOpen}
        jobDetail={selectedJobDetail}
        loading={detailLoading}
        onUpdateStatus={handleUpdateStatus}
      />
    </div>
  );
}
