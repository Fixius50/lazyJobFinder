"use client";

import React, { useEffect, useState } from "react";
import {
  Briefcase,
  Search,
  Filter,
  Download,
  ExternalLink,
  Eye,
  CheckCircle2,
  XCircle,
  FileText,
  Send,
  Globe,
  RefreshCw,
  Building,
  MapPin,
  Calendar,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Dialog } from "@/components/ui/dialog";
import { JobListItem, JobDetail, PaginatedJobsResponse, api } from "@/lib/api";
import { formatDateTime } from "@/lib/utils";
import { APPLICATION_STATUSES, PORTAL_SOURCES, ApplicationStatusKey } from "@/lib/constants";

export default function ApplicationsPage() {
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
    <div className="space-y-6">
      {/* Encabezado */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b">
        <div>
          <h2 className="text-xl font-bold tracking-tight">Candidaturas y Ofertas</h2>
          <p className="text-xs text-muted-foreground mt-1">
            Registro consolidado en SQLite con puntuaciones de afinidad IA y documentos ATS generados.
          </p>
        </div>

        <Button
          size="sm"
          variant="outline"
          onClick={fetchJobs}
          disabled={loading}
          className="flex items-center gap-1.5 h-8 text-xs"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          Actualizar Tabla
        </Button>
      </div>

      {/* Barra de Filtros y Búsqueda */}
      <Card>
        <CardContent className="p-4 space-y-3">
          <form onSubmit={handleSearchSubmit} className="flex flex-col md:flex-row items-center gap-2">
            <div className="relative flex-1 w-full">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                type="text"
                placeholder="Buscar por puesto, empresa o tecnología..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-9 text-xs"
              />
            </div>

            <Button type="submit" size="sm" className="h-9 px-4 text-xs w-full md:w-auto shrink-0">
              Buscar
            </Button>
          </form>

          {/* Filtros secundarios */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 border-t text-xs">
            <div>
              <Select
                value={selectedSource}
                onChange={(e) => {
                  setSelectedSource(e.target.value);
                  setCurrentPage(1);
                }}
                className="text-xs h-8"
              >
                <option value="">Todas las fuentes</option>
                <option value="tecnoempleo_rss">Tecnoempleo</option>
                <option value="infojobs_api">InfoJobs</option>
                <option value="jobspy">JobSpy (LinkedIn/Indeed/Google)</option>
              </Select>
            </div>

            <div>
              <Select
                value={selectedStatus}
                onChange={(e) => {
                  setSelectedStatus(e.target.value);
                  setCurrentPage(1);
                }}
                className="text-xs h-8"
              >
                <option value="">Todos los estados</option>
                <option value="notified">Notificada</option>
                <option value="evaluated">Evaluada</option>
                <option value="applied">Postulada</option>
                <option value="interview">Entrevista</option>
                <option value="rejected">Descartada</option>
                <option value="archived">Archivada</option>
              </Select>
            </div>

            <div>
              <Select
                value={minScore}
                onChange={(e) => {
                  setMinScore(e.target.value);
                  setCurrentPage(1);
                }}
                className="text-xs h-8"
              >
                <option value="">Cualquier afinidad</option>
                <option value="80">Alta (≥ 80)</option>
                <option value="65">Relevante (≥ 65)</option>
                <option value="50">Moderada (≥ 50)</option>
              </Select>
            </div>

            <div>
              <Select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="text-xs h-8"
              >
                <option value="created_at">Ordenar por Fecha</option>
                <option value="score">Ordenar por Puntuación</option>
                <option value="company">Ordenar por Empresa</option>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Tabla Compacta de Ofertas */}
      <div className="rounded-xl border bg-card overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-muted/50 border-b text-muted-foreground font-semibold">
              <tr>
                <th className="py-2.5 px-3">Empresa</th>
                <th className="py-2.5 px-3">Puesto / Vacante</th>
                <th className="py-2.5 px-3">Modalidad / Ubicación</th>
                <th className="py-2.5 px-3 text-center">Score</th>
                <th className="py-2.5 px-3">Detección</th>
                <th className="py-2.5 px-3">Fuente</th>
                <th className="py-2.5 px-3 text-center">Estado</th>
                <th className="py-2.5 px-3 text-center">Docs</th>
                <th className="py-2.5 px-3 text-center">Canales</th>
                <th className="py-2.5 px-3 text-right">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {loading ? (
                <tr>
                  <td colSpan={10} className="py-8 text-center text-muted-foreground">
                    Cargando candidaturas desde SQLite...
                  </td>
                </tr>
              ) : jobsData?.items.length === 0 ? (
                <tr>
                  <td colSpan={10} className="py-8 text-center text-muted-foreground">
                    No se encontraron ofertas con los filtros seleccionados.
                  </td>
                </tr>
              ) : (
                jobsData?.items.map((job) => (
                  <tr key={job.id} className="hover:bg-muted/30 transition-colors">
                    <td className="py-2.5 px-3 font-semibold text-foreground truncate max-w-[140px]">
                      {job.company}
                    </td>
                    <td className="py-2.5 px-3 text-foreground font-medium truncate max-w-[220px]">
                      {job.title}
                    </td>
                    <td className="py-2.5 px-3 text-muted-foreground truncate max-w-[140px]">
                      {job.is_remote ? (
                        <span className="inline-flex items-center text-emerald-600 dark:text-emerald-400 font-medium">
                          Remoto
                        </span>
                      ) : (
                        job.location || "España"
                      )}
                    </td>
                    <td className="py-2.5 px-3 text-center">{getScoreBadge(job.score)}</td>
                    <td className="py-2.5 px-3 text-muted-foreground whitespace-nowrap font-mono text-[11px]">
                      {formatDateTime(job.created_at)}
                    </td>
                    <td className="py-2.5 px-3 whitespace-nowrap">
                      <a
                        href={job.canonical_url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 text-primary hover:underline"
                      >
                        <span className="capitalize">{job.source.replace("_", " ")}</span>
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    </td>
                    <td className="py-2.5 px-3 text-center whitespace-nowrap">
                      {getStatusBadge(job.status)}
                    </td>
                    <td className="py-2.5 px-3 text-center whitespace-nowrap">
                      <div className="flex items-center justify-center gap-1">
                        {job.has_cv ? (
                          <span title="CV Adaptado generado">
                            <Badge variant="outline" className="text-[10px] py-0 px-1 border-primary/40 text-primary">
                              CV
                            </Badge>
                          </span>
                        ) : (
                          <span className="text-muted-foreground text-[10px]">-</span>
                        )}
                        {job.has_letter && (
                          <span title="Carta de Presentación generada">
                            <Badge variant="outline" className="text-[10px] py-0 px-1 border-emerald-500/40 text-emerald-500">
                              Carta
                            </Badge>
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="py-2.5 px-3 text-center whitespace-nowrap">
                      <div className="flex items-center justify-center gap-1.5 text-[11px]">
                        {/* Telegram Status */}
                        <span
                          title={
                            job.telegram_notified === 1
                              ? "Notificado por Telegram"
                              : job.telegram_notified === -1
                              ? "Fallo al notificar por Telegram"
                              : "No enviado a Telegram"
                          }
                        >
                          <Send
                            className={`h-3.5 w-3.5 ${
                              job.telegram_notified === 1
                                ? "text-sky-500"
                                : job.telegram_notified === -1
                                ? "text-destructive"
                                : "text-muted-foreground/40"
                            }`}
                          />
                        </span>
                        {/* UI Saved Status */}
                        <span title="Conservado en interfaz web">
                          <Globe
                            className={`h-3.5 w-3.5 ${
                              job.ui_saved === 1 ? "text-emerald-500" : "text-muted-foreground/30"
                            }`}
                          />
                        </span>
                      </div>
                    </td>
                    <td className="py-2.5 px-3 text-right whitespace-nowrap">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleOpenDetail(job.id)}
                        className="h-7 px-2 text-xs flex items-center gap-1 hover:bg-accent"
                      >
                        <Eye className="h-3.5 w-3.5" /> Detalle
                      </Button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Paginación */}
        {jobsData && jobsData.total_pages > 1 && (
          <div className="flex items-center justify-between p-3 border-t bg-muted/20 text-xs">
            <span className="text-muted-foreground">
              Mostrando {jobsData.items.length} de {jobsData.total} candidaturas
            </span>

            <div className="flex items-center space-x-1">
              <Button
                size="sm"
                variant="outline"
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                disabled={currentPage <= 1}
                className="h-7 w-7 p-0"
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="px-2 font-mono">
                {currentPage} / {jobsData.total_pages}
              </span>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setCurrentPage((p) => Math.min(jobsData.total_pages, p + 1))}
                disabled={currentPage >= jobsData.total_pages}
                className="h-7 w-7 p-0"
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Modal / Drawer de Detalle de Oferta */}
      <Dialog
        open={detailModalOpen}
        onOpenChange={setDetailModalOpen}
        title={selectedJobDetail?.title || "Detalle de Oferta"}
        description={`${selectedJobDetail?.company || ""} · ${selectedJobDetail?.location || ""}`}
        maxWidth="2xl"
      >
        {detailLoading ? (
          <div className="py-12 text-center text-xs text-muted-foreground">
            Cargando análisis y documentos...
          </div>
        ) : selectedJobDetail ? (
          <div className="space-y-4 text-xs">
            {/* Cabecera de afinidad y estado */}
            <div className="flex flex-wrap items-center justify-between gap-2 p-3 bg-muted/40 rounded-lg border">
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground">Puntuación Afinada:</span>
                {getScoreBadge(selectedJobDetail.score)}
                <span className="text-muted-foreground text-[11px]">
                  ({selectedJobDetail.fit_level || "MODERADO"})
                </span>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-muted-foreground">Estado de Candidatura:</span>
                <Select
                  value={selectedJobDetail.status}
                  onChange={(e) => handleUpdateStatus(selectedJobDetail.id, e.target.value)}
                  className="h-7 text-xs w-32"
                >
                  <option value="evaluated">Evaluada</option>
                  <option value="notified">Notificada</option>
                  <option value="applied">Postulada</option>
                  <option value="interview">Entrevista</option>
                  <option value="rejected">Descartada</option>
                  <option value="archived">Archivada</option>
                </Select>
              </div>
            </div>

            {/* Descargas de Documentos */}
            <div className="p-3 bg-muted/20 border rounded-lg space-y-2">
              <span className="font-semibold text-foreground block">Documentos Generados para esta Vacante:</span>
              <div className="flex flex-wrap gap-2">
                {selectedJobDetail.has_cv ? (
                  <>
                    <a
                      href={api.getDocumentUrl(selectedJobDetail.id, "cv_pdf")}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-primary text-primary-foreground font-medium text-xs hover:bg-primary/90"
                    >
                      <Download className="h-3.5 w-3.5" /> Descargar CV (PDF)
                    </a>
                    <a
                      href={api.getDocumentUrl(selectedJobDetail.id, "cv_md")}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border bg-background font-medium text-xs hover:bg-accent"
                    >
                      <FileText className="h-3.5 w-3.5" /> Ver CV (.md)
                    </a>
                  </>
                ) : (
                  <span className="text-muted-foreground italic text-[11px]">
                    No se generó CV adaptado (puntuación menor al umbral o generación deshabilitada).
                  </span>
                )}

                {selectedJobDetail.has_letter && (
                  <>
                    <a
                      href={api.getDocumentUrl(selectedJobDetail.id, "letter_pdf")}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-emerald-600 text-white font-medium text-xs hover:bg-emerald-700"
                    >
                      <Download className="h-3.5 w-3.5" /> Descargar Carta (PDF)
                    </a>
                    <a
                      href={api.getDocumentUrl(selectedJobDetail.id, "letter_md")}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border bg-background font-medium text-xs hover:bg-accent"
                    >
                      <FileText className="h-3.5 w-3.5" /> Ver Carta (.md)
                    </a>
                  </>
                )}
              </div>
            </div>

            {/* Razonamiento IA */}
            {selectedJobDetail.reasoning && (
              <div className="space-y-1">
                <span className="font-semibold text-foreground block">Razonamiento del Modelo de IA:</span>
                <p className="bg-muted/40 p-3 rounded-md text-foreground/90 leading-relaxed text-xs border">
                  {selectedJobDetail.reasoning}
                </p>
              </div>
            )}

            {/* Habilidades Emparejadas y Faltantes */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="border rounded-md p-2.5 space-y-1.5 bg-emerald-500/5">
                <span className="font-semibold text-emerald-600 dark:text-emerald-400 block">
                  Habilidades Coincidentes ({selectedJobDetail.matched_skills?.length || 0}):
                </span>
                <div className="flex flex-wrap gap-1">
                  {selectedJobDetail.matched_skills?.map((s, idx) => (
                    <Badge key={idx} variant="success" className="text-[10px] py-0">
                      {s}
                    </Badge>
                  ))}
                  {(!selectedJobDetail.matched_skills || selectedJobDetail.matched_skills.length === 0) && (
                    <span className="text-muted-foreground italic text-[11px]">Ninguna identificada</span>
                  )}
                </div>
              </div>

              <div className="border rounded-md p-2.5 space-y-1.5 bg-amber-500/5">
                <span className="font-semibold text-amber-600 dark:text-amber-400 block">
                  Requisitos No Cubiertos ({selectedJobDetail.missing_skills?.length || 0}):
                </span>
                <div className="flex flex-wrap gap-1">
                  {selectedJobDetail.missing_skills?.map((s, idx) => (
                    <Badge key={idx} variant="warning" className="text-[10px] py-0">
                      {s}
                    </Badge>
                  ))}
                  {(!selectedJobDetail.missing_skills || selectedJobDetail.missing_skills.length === 0) && (
                    <span className="text-muted-foreground italic text-[11px]">Sin requisitos faltantes</span>
                  )}
                </div>
              </div>
            </div>

            {/* Enlace original */}
            <div className="pt-2 flex justify-between items-center text-xs text-muted-foreground">
              <span>Publicado: {selectedJobDetail.date_posted || "Reciente"}</span>
              <a
                href={selectedJobDetail.canonical_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-primary hover:underline font-medium"
              >
                Abrir oferta original en {selectedJobDetail.source} <ExternalLink className="h-3 w-3" />
              </a>
            </div>
          </div>
        ) : null}
      </Dialog>
    </div>
  );
}
