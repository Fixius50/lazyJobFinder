"use client";

import React, { useEffect, useState, useRef } from "react";
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
import { ServiceToolbarActions } from "@/components/features/services/service-toolbar-actions";
import { JobListItem, JobDetail, PaginatedJobsResponse, FilterFacetsResponse, api } from "@/lib/api";

export function ApplicationsView() {
  const [jobsData, setJobsData] = useState<PaginatedJobsResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [apiError, setApiError] = useState<string | null>(null);
  const [showCvPanel, setShowCvPanel] = useState<boolean>(true);
  const [facets, setFacets] = useState<FilterFacetsResponse | null>(null);

  // Filtros y Paginación
  const [searchTerm, setSearchTerm] = useState<string>("");
  const [exclusionTerm, setExclusionTerm] = useState<string>("");
  const [selectedSource, setSelectedSource] = useState<string>("");
  const [selectedStatus, setSelectedStatus] = useState<string>("");
  const [minScore, setMinScore] = useState<number>(0);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const currentPageRef = useRef<number>(currentPage);

  useEffect(() => {
    currentPageRef.current = currentPage;
  }, [currentPage]);

  // Filtros Avanzados y por Dimensiones
  const [locationName, setLocationName] = useState<string>("");
  const [isAllLocations, setIsAllLocations] = useState<boolean>(true);

  const [selectedModalities, setSelectedModalities] = useState<string[]>([]);
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [selectedEducations, setSelectedEducations] = useState<string[]>([]);
  const [minExperienceStep, setMinExperienceStep] = useState<number>(0);
  const [minSalaryStep, setMinSalaryStep] = useState<number>(0);
  const [selectedSchedules, setSelectedSchedules] = useState<string[]>([]);
  const [selectedContractTypes, setSelectedContractTypes] = useState<string[]>([]);

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
      // Consulta inmediata tras iniciar
      setTimeout(() => pollSearchStatus(), 800);
    } catch (e: any) {
      alert(`Error al iniciar búsqueda: ${e.message}`);
      setSearching(false);
    }
  };

  useEffect(() => {
    loadFacets();
    api.getActiveCV().then((cv) => {
      setHasActiveCv(Boolean(cv && cv.type !== "none" && cv.filename && cv.filename !== "Ninguno" && cv.filename !== "none"));
    }).catch(() => setHasActiveCv(false));

    // Comprobación inicial y monitorización del estado de búsqueda
    pollSearchStatus();
    const interval = setInterval(async () => {
      const isRunning = await pollSearchStatus();
      if (isRunning) {
        // Refrescar silenciosamente conservando exactamente la página activa en tiempo real
        fetchJobs(true, currentPageRef.current);
      }
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  const fetchJobs = async (silent: boolean = false, pageOverride?: number) => {
    if (!silent) {
      setLoading(true);
    }
    const targetPage = pageOverride ?? currentPageRef.current;
    try {
      const expYears = minExperienceStep > 0 ? EXPERIENCE_STEPS[minExperienceStep]?.years : undefined;
      const minSal = minSalaryStep > 0 ? SALARY_STEPS[minSalaryStep]?.value : undefined;

      const res = await api.listJobs({
        search: searchTerm.trim() || undefined,
        exclude: exclusionTerm.trim() || undefined,
        location: !isAllLocations && locationName ? locationName : undefined,
        source: selectedSource || undefined,
        status: selectedStatus || undefined,
        min_score: minScore > 0 ? minScore : undefined,
        modalities: selectedModalities.length > 0 ? selectedModalities : undefined,
        categories: selectedCategories.length > 0 ? selectedCategories : undefined,
        educations: selectedEducations.length > 0 ? selectedEducations : undefined,
        min_experience_years: expYears,
        min_salary: minSal,
        schedules: selectedSchedules.length > 0 ? selectedSchedules : undefined,
        contract_types: selectedContractTypes.length > 0 ? selectedContractTypes : undefined,
        page: targetPage,
        page_size: 20,
        sort_by: "created_at",
        sort_order: "desc",
      });
      setJobsData(res);
      setApiError(null);
      if (res.has_cv !== undefined) {
        setHasActiveCv(res.has_cv);
      }
      // Sincronizar facetas con el total de ofertas devuelto
      loadFacets();
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
    currentPageRef.current = newPage;
    setCurrentPage(newPage);
    fetchJobs(false, newPage);
  };

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchJobs();
    }, 300);
    return () => clearTimeout(timer);
  }, [
    searchTerm,
    exclusionTerm,
    selectedSource,
    selectedStatus,
    minScore,
    selectedModalities,
    selectedCategories,
    selectedEducations,
    minExperienceStep,
    minSalaryStep,
    selectedSchedules,
    selectedContractTypes,
    isAllLocations,
    locationName,
    currentPage,
  ]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setCurrentPage(1);
    fetchJobs();
  };

  const handleResetFilters = () => {
    setSearchTerm("");
    setExclusionTerm("");
    setSelectedSource("");
    setSelectedStatus("");
    setMinScore(0);
    setIsAllLocations(true);
    setLocationName("");
    setSelectedModalities([]);
    setSelectedCategories([]);
    setSelectedEducations([]);
    setMinExperienceStep(0);
    setMinSalaryStep(0);
    setSelectedSchedules([]);
    setSelectedContractTypes([]);
    setCurrentPage(1);
  };

  const handleSaveCriteria = async () => {
    try {
      const terminos = searchTerm.split(",").map((t) => t.trim()).filter(Boolean);
      const exclusiones = exclusionTerm.split(",").map((e) => e.trim()).filter(Boolean);

      await api.updateSearchConfig({
        terminos: terminos,
        ubicaciones: !isAllLocations ? [locationName] : ["Spain", "Remoto"],
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
      fetchJobs();
    } catch (err: any) {
      alert(`Error al actualizar estado: ${err.message}`);
    }
  };

  return (
    <div className="space-y-4 sm:space-y-6 w-full">
      {/* Encabezado fluido con Título + CV en una sola línea | Acciones globales */}
      <div className="flex flex-col 2xl:flex-row 2xl:items-center justify-between gap-3 pb-3 border-b border-border/50">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1.5 shrink-0">
            <h2 className="text-lg sm:text-xl font-bold tracking-tight">Candidaturas y Ofertas</h2>
            <InfoTooltip content="Registro consolidado en SQLite con puntuaciones de afinidad IA y documentos ATS generados." />
          </div>

          <div className="h-5 w-px bg-border/60 mx-1 hidden sm:block" />

          {/* Bloque en una sola línea del CV Activo: Currículum Activo, ?, Desplegable, Ojo, Subir, Borrar */}
          <CvManager
            onCvChanged={(activeInfo) => {
              const hasCv = Boolean(
                activeInfo &&
                activeInfo.type !== "none" &&
                activeInfo.filename &&
                activeInfo.filename !== "Ninguno" &&
                activeInfo.filename !== "none"
              );
              setHasActiveCv(hasCv);
              loadFacets();
              fetchJobs();
            }}
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Servicios Docker y Acciones Globales */}
          <ServiceToolbarActions />

          <div className="h-5 w-px bg-border/60 mx-1 hidden sm:block" />

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
            onClick={() => {
              fetchJobs();
              loadFacets();
            }}
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
              searchTerm={searchTerm}
              onSearchTermChange={setSearchTerm}
              exclusionTerm={exclusionTerm}
              onExclusionTermChange={setExclusionTerm}
              locationName={locationName}
              onLocationChange={(loc) => {
                setLocationName(loc);
                setCurrentPage(1);
              }}
              isAllLocations={isAllLocations}
              onToggleAllLocations={(all) => {
                setIsAllLocations(all);
                setCurrentPage(1);
              }}
              selectedModalities={selectedModalities}
              onModalitiesChange={(mods) => {
                setSelectedModalities(mods);
                setCurrentPage(1);
              }}
              selectedCategories={selectedCategories}
              onCategoriesChange={(cats) => {
                setSelectedCategories(cats);
                setCurrentPage(1);
              }}
              selectedEducations={selectedEducations}
              onEducationsChange={(edus) => {
                setSelectedEducations(edus);
                setCurrentPage(1);
              }}
              minExperienceStep={minExperienceStep}
              onMinExperienceStepChange={(step) => {
                setMinExperienceStep(step);
                setCurrentPage(1);
              }}
              minSalaryStep={minSalaryStep}
              onMinSalaryStepChange={(step) => {
                setMinSalaryStep(step);
                setCurrentPage(1);
              }}
              selectedSchedules={selectedSchedules}
              onSchedulesChange={(scheds) => {
                setSelectedSchedules(scheds);
                setCurrentPage(1);
              }}
              selectedContractTypes={selectedContractTypes}
              onContractTypesChange={(cts) => {
                setSelectedContractTypes(cts);
                setCurrentPage(1);
              }}
              selectedSource={selectedSource}
              onSourceChange={(source) => {
                setSelectedSource(source);
                setCurrentPage(1);
              }}
              selectedStatus={selectedStatus}
              onStatusChange={(status) => {
                setSelectedStatus(status);
                setCurrentPage(1);
              }}
              minScore={minScore}
              onMinScoreChange={(score) => {
                setMinScore(score);
                setCurrentPage(1);
              }}
              onSubmitSearch={handleSearchSubmit}
              onResetFilters={handleResetFilters}
              onSaveCriteria={handleSaveCriteria}
            />
          </aside>
        )}

        <section className={`${hasActiveCv && showCvPanel ? "lg:col-span-8 xl:col-span-9" : "lg:col-span-12"} space-y-4`}>
          {/* Listado de Ofertas en cuadrícula */}
          <div className="space-y-3">
            {/* Banner de progreso mientras busca o evalúa en segundo plano */}
            {searching && (
              <div className="flex flex-wrap items-center justify-between gap-2 p-2.5 rounded-lg border border-primary/30 bg-primary/5">
                <div className="flex items-center gap-2 text-xs font-semibold text-primary">
                  <Sparkles className="h-4 w-4 animate-spin text-primary" />
                  <span>Buscando ofertas compatibles en portales de empleo y evaluando con IA...</span>
                </div>
                <span className="text-2xs text-muted-foreground animate-pulse">
                  {jobsData && jobsData.total > 0
                    ? `${jobsData.total} ofertas encontradas hasta el momento`
                    : "Rastreando Indeed, LinkedIn y Glassdoor..."}
                </span>
              </div>
            )}

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
            {jobsData && jobsData.items.length > 0 ? (
              <div
                className={`grid grid-cols-1 sm:grid-cols-2 ${
                  showCvPanel
                    ? "lg:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-4"
                    : "lg:grid-cols-3 xl:grid-cols-5 2xl:grid-cols-5"
                } gap-3 sm:gap-3.5`}
              >
                {jobsData.items.map((job: JobListItem) => (
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

            {/* Paginación fluida */}
            {jobsData && jobsData.total_pages > 1 && (
              <div className="flex items-center justify-between pt-4 border-t text-xs text-muted-foreground">
                <div>
                  Mostrando {jobsData.items.length} de {jobsData.total} ofertas
                </div>
                <div className="flex items-center gap-1">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handlePageChange(Math.max(1, currentPage - 1))}
                    disabled={currentPage <= 1 || loading}
                    className="h-8 px-2"
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                  <span className="px-2 font-medium text-foreground">
                    Página {currentPage} de {jobsData.total_pages}
                  </span>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handlePageChange(Math.min(jobsData.total_pages, currentPage + 1))}
                    disabled={currentPage >= jobsData.total_pages || loading}
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
