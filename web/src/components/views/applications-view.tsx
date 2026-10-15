"use client";

import React, { useEffect, useState } from "react";
import {
  Briefcase,
  Search,
  Download,
  ExternalLink,
  Eye,
  CheckCircle2,
  RefreshCw,
  Building,
  MapPin,
  Calendar,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Dialog } from "@/components/ui/dialog";
import { JobListItem, JobDetail, PaginatedJobsResponse, api } from "@/lib/api";
import { formatDateTime } from "@/lib/utils";
import { APPLICATION_STATUSES, PORTAL_SOURCES, ApplicationStatusKey } from "@/lib/constants";

export function ApplicationsView() {
  const [jobsData, setJobsData] = useState<PaginatedJobsResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  // Filtros y Paginación
  const [searchTerm, setSearchTerm] = useState<string>("");
  const [selectedSource, setSelectedSource] = useState<string>("");
  const [selectedStatus, setSelectedStatus] = useState<string>("");
  const [minScore, setMinScore] = useState<string>("");
  const [isRemoteOnly, setIsRemoteOnly] = useState<boolean>(false);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [sortBy, setSortBy] = useState<string>("created_at");
  const [sortOrder, setSortOrder] = useState<string>("desc");

  // Modal de Detalle
  const [detailModalOpen, setDetailModalOpen] = useState<boolean>(false);
  const [selectedJobDetail, setSelectedJobDetail] = useState<JobDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState<boolean>(false);

  const fetchJobs = async () => {
    setLoading(true);
    try {
      const res = await api.listJobs({
        search: searchTerm || undefined,
        source: selectedSource || undefined,
        status: selectedStatus || undefined,
        min_score: minScore ? parseInt(minScore, 10) : undefined,
        is_remote: isRemoteOnly ? true : undefined,
        page: currentPage,
        page_size: 15,
        sort_by: sortBy,
        sort_order: sortOrder,
      });
      setJobsData(res);
    } catch (err: any) {
      console.error("Error al cargar candidaturas:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs();
  }, [currentPage, sortBy, sortOrder, selectedSource, selectedStatus, isRemoteOnly]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setCurrentPage(1);
    fetchJobs();
  };

  const handleOpenDetail = async (jobId: number) => {
    setDetailLoading(true);
    setDetailModalOpen(true);
    try {
      const detail = await api.getJobDetail(jobId);
      setSelectedJobDetail(detail);
    } catch (err: any) {
      alert(`Error al abrir detalle: ${err.message}`);
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
      await fetchJobs();
    } catch (err: any) {
      alert(`Error al actualizar estado: ${err.message}`);
    }
  };

  const getScoreBadge = (score?: number | null) => {
    if (score === undefined || score === null) {
      return <Badge variant="secondary">Sin evaluar</Badge>;
    }
    if (score >= 80) {
      return <Badge variant="success">{score} / 100</Badge>;
    }
    if (score >= 65) {
      return <Badge variant="warning">{score} / 100</Badge>;
    }
    return <Badge variant="destructive">{score} / 100</Badge>;
  };

  const getStatusBadge = (status: string) => {
    const meta = APPLICATION_STATUSES[status as ApplicationStatusKey];
    if (meta) {
      return <Badge variant={meta.badge}>{meta.label}</Badge>;
    }
    return <Badge variant="secondary">{status}</Badge>;
  };

  return (
    <div className="space-y-4 sm:space-y-6 w-full">
      {/* Encabezado fluido */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b">
        <div>
          <h2 className="text-lg sm:text-xl font-bold tracking-tight">Candidaturas y Ofertas</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Registro consolidado en SQLite con puntuaciones de afinidad IA y documentos ATS generados.
          </p>
        </div>

        <Button
          size="sm"
          variant="outline"
          onClick={fetchJobs}
          disabled={loading}
          className="flex items-center gap-1.5 h-8 text-xs self-start sm:self-auto"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          Actualizar
        </Button>
      </div>

      {/* Barra de Filtros y Búsqueda con CSS Relativo */}
      <Card className="border bg-card/60 backdrop-blur-sm shadow-sm">
        <CardContent className="p-3 sm:p-4 space-y-3">
          <form onSubmit={handleSearchSubmit} className="flex flex-col sm:flex-row items-center gap-2">
            <div className="relative flex-1 w-full">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                type="text"
                placeholder="Buscar por puesto, empresa o tecnología..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-9 text-xs w-full"
              />
            </div>

            <Button type="submit" size="sm" className="h-9 px-4 text-xs w-full sm:w-auto shrink-0">
              Buscar
            </Button>
          </form>

          {/* Filtros secundarios relativos */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t text-xs">
            <div>
              <Select
                value={selectedSource}
                onChange={(e) => {
                  setSelectedSource(e.target.value);
                  setCurrentPage(1);
                }}
                className="text-xs h-8 w-full"
              >
                <option value="">Todos los portales</option>
                {Object.entries(PORTAL_SOURCES).map(([code, meta]) => (
                  <option key={code} value={code}>
                    {meta.label}
                  </option>
                ))}
              </Select>
            </div>

            <div>
              <Select
                value={selectedStatus}
                onChange={(e) => {
                  setSelectedStatus(e.target.value);
                  setCurrentPage(1);
                }}
                className="text-xs h-8 w-full"
              >
                <option value="">Todos los estados</option>
                {Object.entries(APPLICATION_STATUSES).map(([key, meta]) => (
                  <option key={key} value={key}>
                    {meta.label}
                  </option>
                ))}
              </Select>
            </div>

            <div>
              <Select
                value={minScore}
                onChange={(e) => {
                  setMinScore(e.target.value);
                  setCurrentPage(1);
                }}
                className="text-xs h-8 w-full"
              >
                <option value="">Cualquier nota</option>
                <option value="65">Aptas (≥ 65 pts)</option>
                <option value="80">Sobresalientes (≥ 80 pts)</option>
                <option value="90">Excelentes (≥ 90 pts)</option>
              </Select>
            </div>

            <div className="flex items-center space-x-2 pl-1">
              <input
                type="checkbox"
                id="remoteOnly"
                checked={isRemoteOnly}
                onChange={(e) => {
                  setIsRemoteOnly(e.target.checked);
                  setCurrentPage(1);
                }}
                className="h-3.5 w-3.5 rounded border-gray-300 text-primary focus:ring-primary cursor-pointer"
              />
              <label htmlFor="remoteOnly" className="text-xs text-muted-foreground select-none cursor-pointer">
                Solo remoto
              </label>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Resultados: Listado fluido con vista adaptativa */}
      <div className="space-y-3">
        {loading ? (
          <div className="flex flex-col items-center justify-center py-12 text-muted-foreground space-y-2">
            <RefreshCw className="h-6 w-6 animate-spin text-primary" />
            <p className="text-xs">Consultando candidaturas en base de datos local...</p>
          </div>
        ) : !jobsData || jobsData.items.length === 0 ? (
          <Card className="border-dashed">
            <CardContent className="flex flex-col items-center justify-center py-12 text-center text-muted-foreground space-y-2">
              <Briefcase className="h-8 w-8 text-muted-foreground/60" />
              <p className="text-sm font-medium text-foreground">No se encontraron candidaturas</p>
              <p className="text-xs max-w-sm">
                No hay ofertas que coincidan con los filtros aplicados o aún no has lanzado una búsqueda.
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-2.5">
            {jobsData.items.map((job: JobListItem) => {
              const sourceMeta = PORTAL_SOURCES[job.source as keyof typeof PORTAL_SOURCES];
              return (
                <Card
                  key={job.id}
                  className="hover:border-primary/40 transition-all duration-150 bg-card/80 backdrop-blur-sm shadow-sm"
                >
                  <CardContent className="p-3 sm:p-4 flex flex-col md:flex-row items-start md:items-center justify-between gap-3">
                    {/* Información Principal */}
                    <div className="space-y-1.5 flex-1 min-w-0 w-full">
                      <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
                        {getScoreBadge(job.score)}
                        {getStatusBadge(job.status)}
                        <span className="text-[11px] font-medium px-2 py-0.5 rounded bg-muted text-muted-foreground">
                          {sourceMeta ? sourceMeta.label : job.source}
                        </span>
                        {job.is_remote ? (
                          <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400">
                            Remoto
                          </span>
                        ) : null}
                      </div>

                      <h3 className="text-sm font-semibold text-foreground truncate hover:text-primary transition-colors">
                        <a href={job.canonical_url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1.5">
                          {job.title}
                          <ExternalLink className="h-3 w-3 shrink-0 opacity-60" />
                        </a>
                      </h3>

                      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <Building className="h-3 w-3 shrink-0" />
                          {job.company || "Empresa Confidencial"}
                        </span>
                        <span className="flex items-center gap-1">
                          <MapPin className="h-3 w-3 shrink-0" />
                          {job.location || "España"}
                        </span>
                        <span className="flex items-center gap-1">
                          <Calendar className="h-3 w-3 shrink-0" />
                          {formatDateTime(job.created_at)}
                        </span>
                      </div>
                    </div>

                    {/* Acciones y Documentos */}
                    <div className="flex items-center gap-2 w-full md:w-auto justify-end pt-2 md:pt-0 border-t md:border-t-0 shrink-0">
                      {job.has_cv && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => window.open(api.getDocumentUrl(job.id, "cv_pdf"), "_blank")}
                          title="Descargar CV adaptado en PDF"
                          className="h-8 px-2 text-xs flex items-center gap-1 text-emerald-400 hover:text-emerald-300"
                        >
                          <Download className="h-3.5 w-3.5" />
                          <span className="hidden sm:inline">CV</span>
                        </Button>
                      )}

                      {job.has_letter && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => window.open(api.getDocumentUrl(job.id, "letter_pdf"), "_blank")}
                          title="Descargar Carta en PDF"
                          className="h-8 px-2 text-xs flex items-center gap-1 text-blue-400 hover:text-blue-300"
                        >
                          <Download className="h-3.5 w-3.5" />
                          <span className="hidden sm:inline">Carta</span>
                        </Button>
                      )}

                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => handleOpenDetail(job.id)}
                        className="h-8 text-xs flex items-center gap-1"
                      >
                        <Eye className="h-3.5 w-3.5" />
                        <span>Detalles</span>
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
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

      {/* Modal de Detalle de Oferta con CSS Relativo */}
      <Dialog
        open={detailModalOpen}
        onOpenChange={setDetailModalOpen}
        title={selectedJobDetail?.title || "Detalle de la Candidatura"}
        description={`${selectedJobDetail?.company || "Empresa"} · ${selectedJobDetail?.location || "Ubicación"}`}
      >
        {detailLoading ? (
          <div className="flex items-center justify-center py-8">
            <RefreshCw className="h-5 w-5 animate-spin text-primary" />
          </div>
        ) : selectedJobDetail ? (
          <div className="space-y-4 max-h-[70dvh] overflow-y-auto pr-1 text-xs">
            {/* Cabecera de Estado y Puntuación */}
            <div className="flex flex-wrap items-center justify-between gap-2 p-3 rounded-lg bg-muted/40 border">
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground font-medium">Estado:</span>
                <Select
                  value={selectedJobDetail.status}
                  onChange={(e) => handleUpdateStatus(selectedJobDetail.id, e.target.value)}
                  className="h-7 text-xs bg-background"
                >
                  {Object.entries(APPLICATION_STATUSES).map(([key, meta]) => (
                    <option key={key} value={key}>
                      {meta.label}
                    </option>
                  ))}
                </Select>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-muted-foreground font-medium">Afinidad ATS:</span>
                {getScoreBadge(selectedJobDetail.score)}
              </div>
            </div>

            {/* Justificación de la IA si existe */}
            {selectedJobDetail.reasoning && (
              <div className="p-3 rounded-lg bg-primary/5 border border-primary/20 space-y-1">
                <h4 className="font-semibold text-primary flex items-center gap-1.5">
                  <CheckCircle2 className="h-3.5 w-3.5" /> Razonamiento del Modelo Local
                </h4>
                <p className="text-muted-foreground leading-relaxed whitespace-pre-wrap">
                  {selectedJobDetail.reasoning}
                </p>
              </div>
            )}

            {/* Competencias y Habilidades Coincidentes */}
            {selectedJobDetail.matched_skills && selectedJobDetail.matched_skills.length > 0 && (
              <div className="space-y-1.5">
                <h4 className="font-medium text-foreground">Habilidades coincidentes:</h4>
                <div className="flex flex-wrap gap-1">
                  {selectedJobDetail.matched_skills.map((skill: string, i: number) => (
                    <span key={i} className="px-2 py-0.5 rounded bg-muted text-[11px] font-mono text-primary">
                      {skill}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Descripción Completa de la Oferta */}
            {selectedJobDetail.description && (
              <div className="space-y-1.5">
                <h4 className="font-medium text-foreground">Descripción original del puesto:</h4>
                <div className="p-3 rounded-md bg-muted/30 border text-muted-foreground leading-relaxed max-h-48 overflow-y-auto whitespace-pre-wrap font-sans text-[11px]">
                  {selectedJobDetail.description}
                </div>
              </div>
            )}

            {/* Enlace y Documentos */}
            <div className="flex flex-wrap items-center justify-between gap-2 pt-3 border-t">
              <a
                href={selectedJobDetail.canonical_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline flex items-center gap-1"
              >
                Abrir oferta en portal oficial
                <ExternalLink className="h-3 w-3" />
              </a>

              <div className="flex items-center gap-2">
                {selectedJobDetail.has_cv && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => window.open(api.getDocumentUrl(selectedJobDetail.id, "cv_pdf"), "_blank")}
                    className="h-8 text-xs flex items-center gap-1"
                  >
                    <Download className="h-3.5 w-3.5" />
                    CV Adaptado
                  </Button>
                )}

                {selectedJobDetail.has_letter && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => window.open(api.getDocumentUrl(selectedJobDetail.id, "letter_pdf"), "_blank")}
                    className="h-8 text-xs flex items-center gap-1"
                  >
                    <Download className="h-3.5 w-3.5" />
                    Carta Adaptada
                  </Button>
                )}
              </div>
            </div>
          </div>
        ) : null}
      </Dialog>
    </div>
  );
}
