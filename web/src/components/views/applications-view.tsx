"use client";

import React, { useEffect, useState } from "react";
import {
  Briefcase,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  FileCheck,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { InfoTooltip } from "@/components/ui/info-tooltip";
import { CvManager } from "@/components/views/cv-manager";
import { JobCard } from "@/components/features/jobs/job-card";
import { JobFilters, EXPERIENCE_STEPS, SALARY_STEPS } from "@/components/features/jobs/job-filters";
import { JobDetailDialog } from "@/components/features/jobs/job-detail-dialog";
import { PurgeHistoryButton } from "@/components/features/maintenance/purge-history-card";
import { ServiceToolbarActions } from "@/components/features/services/service-toolbar-actions";
import { JobListItem, JobDetail, PaginatedJobsResponse, FilterFacetsResponse, api } from "@/lib/api";

export function ApplicationsView() {
  const [jobsData, setJobsData] = useState<PaginatedJobsResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [showCvPanel, setShowCvPanel] = useState<boolean>(true);
  const [facets, setFacets] = useState<FilterFacetsResponse | null>(null);

  // Filtros y Paginación
  const [searchTerm, setSearchTerm] = useState<string>("");
  const [exclusionTerm, setExclusionTerm] = useState<string>("");
  const [selectedSource, setSelectedSource] = useState<string>("");
  const [selectedStatus, setSelectedStatus] = useState<string>("");
  const [minScore, setMinScore] = useState<number>(0);
  const [currentPage, setCurrentPage] = useState<number>(1);

  // Filtros Avanzados Geográficos y por Dimensiones
  const [geoLat, setGeoLat] = useState<number>(40.4168);
  const [geoLon, setGeoLon] = useState<number>(-3.7038);
  const [geoRadiusKm, setGeoRadiusKm] = useState<number>(50);
  const [locationName, setLocationName] = useState<string>("Cualquier lugar");
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

  const loadFacets = async () => {
    try {
      const data = await api.getFilterFacets();
      setFacets(data);
    } catch (e) {
      console.warn("Fallo cargando facetas dinámicas:", e);
    }
  };

  useEffect(() => {
    loadFacets();
  }, []);

  const fetchJobs = async () => {
    setLoading(true);
    try {
      const expYears = minExperienceStep > 0 ? EXPERIENCE_STEPS[minExperienceStep]?.years : undefined;
      const minSal = minSalaryStep > 0 ? SALARY_STEPS[minSalaryStep]?.value : undefined;

      const res = await api.listJobs({
        search: searchTerm || undefined,
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
        geo_lat: !isAllLocations ? geoLat : undefined,
        geo_lon: !isAllLocations ? geoLon : undefined,
        geo_radius_km: !isAllLocations ? geoRadiusKm : undefined,
        page: currentPage,
        page_size: 20,
        sort_by: "created_at",
        sort_order: "desc",
      });
      setJobsData(res);
    } catch (err: any) {
      console.error("[ApplicationsView] Error obteniendo ofertas:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs();
  }, [
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
    geoLat,
    geoLon,
    geoRadiusKm,
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
    setGeoLat(40.4168);
    setGeoLon(-3.7038);
    setGeoRadiusKm(50);
    setLocationName("Madrid");
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
        terminos: terminos.length > 0 ? terminos : ["Desarrollador Junior", "Full Stack"],
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
      {/* Encabezado fluido con Servicios, Actualizar, Purgar y Ocultar Panel */}
      <div className="flex flex-col 2xl:flex-row 2xl:items-center justify-between gap-3 pb-3 border-b">
        <div className="flex items-center gap-1.5 shrink-0">
          <h2 className="text-lg sm:text-xl font-bold tracking-tight">Candidaturas y Ofertas</h2>
          <InfoTooltip content="Registro consolidado en SQLite con puntuaciones de afinidad IA y documentos ATS generados." />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Servicios Docker y Acciones Globales */}
          <ServiceToolbarActions />

          <div className="h-5 w-px bg-border/60 mx-1 hidden sm:block" />

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

          {/* Botón Ocultar / Mostrar Panel */}
          <Button
            size="sm"
            variant="outline"
            onClick={() => setShowCvPanel(!showCvPanel)}
            className="flex items-center gap-1.5 h-8 text-xs"
          >
            <FileCheck className="h-3.5 w-3.5 text-primary" />
            {showCvPanel ? "Ocultar Panel Lateral" : "Mostrar Panel Lateral"}
          </Button>
        </div>
      </div>

      {/* Estructura en Dos Columnas: Panel Lateral Izquierdo (CV + Filtros) | Listado a la Derecha */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 sm:gap-6 items-start">
        {showCvPanel && (
          <aside className="lg:col-span-4 xl:col-span-3 space-y-4">
            <CvManager onCvChanged={fetchJobs} />
            <JobFilters
              facets={facets}
              searchTerm={searchTerm}
              onSearchTermChange={setSearchTerm}
              exclusionTerm={exclusionTerm}
              onExclusionTermChange={setExclusionTerm}
              geoLat={geoLat}
              geoLon={geoLon}
              geoRadiusKm={geoRadiusKm}
              locationName={locationName}
              isAllLocations={isAllLocations}
              onGeoLocationChange={(lat, lon, name) => {
                setGeoLat(lat);
                setGeoLon(lon);
                setLocationName(name);
                setCurrentPage(1);
              }}
              onGeoRadiusChange={(radiusKm) => {
                setGeoRadiusKm(radiusKm);
                setCurrentPage(1);
              }}
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

        <section className={`${showCvPanel ? "lg:col-span-8 xl:col-span-9" : "lg:col-span-12"} space-y-4`}>
          {/* Listado de Ofertas en cuadrícula de 4 tarjetas por fila */}
          <div className="space-y-3">
            {loading ? (
              <div className="flex flex-col items-center justify-center py-16 text-muted-foreground space-y-2">
                <RefreshCw className="h-6 w-6 animate-spin text-primary" />
                <p className="text-xs">Consultando candidaturas en base de datos local...</p>
              </div>
            ) : !jobsData || jobsData.items.length === 0 ? (
              <Card className="border-dashed">
                <CardContent className="flex flex-col items-center justify-center py-16 text-center text-muted-foreground space-y-2">
                  <Briefcase className="h-8 w-8 text-muted-foreground/60" />
                  <p className="text-sm font-medium text-foreground">No se encontraron candidaturas</p>
                  <p className="text-xs max-w-sm">
                    No hay ofertas que coincidan con los filtros aplicados o aún no has lanzado una búsqueda.
                  </p>
                </CardContent>
              </Card>
            ) : (
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
                    onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
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
                    onClick={() => setCurrentPage((p) => Math.min(jobsData.total_pages, p + 1))}
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
