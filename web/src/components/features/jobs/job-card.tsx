"use client";

import React, { useState, useEffect } from "react";
import {
  Building,
  MapPin,
  Calendar,
  ExternalLink,
  Download,
  FileText,
  Mail,
  Eye,
  RefreshCw,
  Sparkles,
  X,
  RotateCcw,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { JobListItem } from "@/types";
import { formatDateTime } from "@/lib/utils";
import { APPLICATION_STATUSES, PORTAL_SOURCES, ApplicationStatusKey } from "@/lib/constants";
import { api } from "@/lib/api";

import { toast } from "sonner";

import { JobScoreBadge, JobStatusBadge, JobModalityBadge } from "./job-badges";

interface JobCardProps {
  job: JobListItem;
  onOpenDetail: (id: number) => void;
  onUpdateStatus?: (id: number, newStatus: string) => void;
  onUpdateJob?: (updatedJob: JobListItem) => void;
}

export function JobCard({ job, onOpenDetail, onUpdateStatus, onUpdateJob }: JobCardProps) {
  const sourceMeta = PORTAL_SOURCES[job.source as keyof typeof PORTAL_SOURCES];
  const isEvaluating = job.status === "evaluating";
  const isDiscarded = job.status === "discarded";

  const [hasCv, setHasCv] = useState<boolean>(!!job.has_cv);
  const [hasLetter, setHasLetter] = useState<boolean>(!!job.has_letter);
  const [isGenerating, setIsGenerating] = useState<boolean>(job.status === "generating_docs");

  const isEvaluated = Boolean(
    (job.score !== null && job.score !== undefined && job.status !== "discovered" && job.status !== "evaluating") ||
    hasCv ||
    hasLetter
  );

  const handleToggleDiscard = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!onUpdateStatus) return;
    const newStatus = isDiscarded ? "evaluated" : "discarded";
    onUpdateStatus(job.id, newStatus);
  };

  useEffect(() => {
    setHasCv(!!job.has_cv);
    setHasLetter(!!job.has_letter);
    if (job.status === "generating_docs") {
      setIsGenerating(true);
    }
  }, [job.has_cv, job.has_letter, job.status]);

  const handleGenerateDocs = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (isGenerating) return;

    setIsGenerating(true);
    toast.promise(api.generateJobDocuments(job.id), {
      loading: `Generando CV y carta con IA para "${job.title.slice(0, 32)}..."`,
      success: (res) => {
        setHasCv(true);
        setHasLetter(true);
        if (onUpdateJob) {
          onUpdateJob({
            ...job,
            has_cv: true,
            has_letter: true,
            status: "evaluated",
          });
        }
        setIsGenerating(false);
        return "CV adaptado y carta listos para descargar.";
      },
      error: (err) => {
        setIsGenerating(false);
        return `Error generando documentos: ${err.message || err}`;
      },
    });
  };

  return (
    <Card
      className={`group flex flex-col justify-between hover:border-primary/50 hover:shadow-md transition-all duration-200 bg-card/80 backdrop-blur-sm border rounded-xl overflow-hidden h-full ${
        isDiscarded ? "opacity-75 hover:opacity-100 border-dashed border-border/80" : ""
      }`}
    >
      <CardContent className="p-3 sm:p-3.5 flex flex-col h-full justify-between space-y-3">
        {/* Cabecera de la Tarjeta: tags | sitio | modalidad | ojo */}
        <div className="space-y-2.5">
          <div className="flex items-center justify-between gap-1.5">
            <div className="flex items-center gap-1 flex-wrap min-w-0">
              <JobScoreBadge score={job.score} isEvaluating={isEvaluating} size="sm" />
              <JobStatusBadge status={job.status} size="sm" />
              <span className="text-3xs font-medium px-1.5 py-0.5 rounded bg-muted/90 text-muted-foreground shrink-0">
                {sourceMeta ? sourceMeta.label : job.source}
              </span>
              <JobModalityBadge job={job} size="sm" />
            </div>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => onOpenDetail(job.id)}
              className="h-6 w-6 p-0 rounded-md shrink-0 text-muted-foreground/60 hover:text-foreground hover:bg-muted/80 transition-colors"
              title="Ver detalles de la oferta"
            >
              <Eye className="h-3.5 w-3.5" />
            </Button>
          </div>

          {/* Título de la oferta con límite de 2 líneas */}
          <h3 className="text-xs sm:text-sm font-semibold text-foreground group-hover:text-primary transition-colors leading-snug">
            <a
              href={job.canonical_url}
              target="_blank"
              rel="noopener noreferrer"
              className="hover:underline flex items-start gap-1"
              title={job.title}
            >
              <span className="line-clamp-2">{job.title}</span>
              <ExternalLink className="h-3 w-3 shrink-0 opacity-40 group-hover:opacity-100 transition-opacity mt-0.5" />
            </a>
          </h3>

          {/* Metadatos esenciales: Empresa, Ubicación y Fecha */}
          <div className="space-y-1 text-2xs text-muted-foreground pt-0.5">
            <div className="flex items-center gap-1.5 truncate">
              <Building className="h-3 w-3 shrink-0 text-muted-foreground/70" />
              <span className="truncate font-medium text-foreground/80" title={job.company}>
                {job.company || "Empresa Confidencial"}
              </span>
            </div>

            <div className="flex items-center gap-1.5 truncate" title={job.location}>
              <MapPin className="h-3 w-3 shrink-0 text-muted-foreground/70" />
              <span className="truncate">{job.location || "España"}</span>
            </div>

            <div className="flex items-center gap-1 text-3xs text-muted-foreground/60">
              <Calendar className="h-2.5 w-2.5 shrink-0" />
              <span>{formatDateTime(job.created_at)}</span>
            </div>
          </div>
        </div>

        {/* Pie de la Tarjeta: Acciones de descarga, botón de generación y descarte */}
        <div className="pt-2 border-t border-border/40 flex items-center justify-between gap-1.5">
          <div className="flex items-center gap-1">
            {hasCv ? (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => window.open(api.getDocumentUrl(job.id, "cv_pdf"), "_blank")}
                title="Descargar CV adaptado en PDF"
                className="h-7 w-7 p-0 flex items-center justify-center shrink-0 text-emerald-400 hover:text-emerald-300 hover:bg-emerald-500/10"
              >
                <FileText className="h-3.5 w-3.5" />
              </Button>
            ) : null}

            {hasLetter ? (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => window.open(api.getDocumentUrl(job.id, "letter_pdf"), "_blank")}
                title="Descargar Carta adaptada en PDF"
                className="h-7 w-7 p-0 flex items-center justify-center shrink-0 text-blue-400 hover:text-blue-300 hover:bg-blue-500/10"
              >
                <Mail className="h-3.5 w-3.5" />
              </Button>
            ) : null}
          </div>

          <div className="flex items-center gap-1.5 ml-auto">
            {/* Botón de Generar CV y Carta bajo demanda (solo icono) */}
            {(isEvaluated || isGenerating) && (
              <Button
                size="sm"
                variant={hasCv && hasLetter ? "ghost" : "outline"}
                disabled={isGenerating}
                onClick={handleGenerateDocs}
                title={
                  hasCv && hasLetter
                    ? "Regenerar CV y carta adaptados con IA"
                    : "Generar CV y carta adaptados a esta oferta en particular"
                }
                className={`h-7 w-7 p-0 flex items-center justify-center shrink-0 transition-all ${
                  hasCv && hasLetter
                    ? "text-muted-foreground hover:text-primary hover:bg-primary/10"
                    : "bg-primary/10 text-primary border-primary/30 hover:bg-primary/20 hover:border-primary/50 shadow-xs"
                }`}
              >
                {isGenerating ? (
                  <RefreshCw className="h-3.5 w-3.5 animate-spin text-primary" />
                ) : hasCv && hasLetter ? (
                  <Sparkles className="h-3.5 w-3.5 text-amber-400" />
                ) : (
                  <Sparkles className="h-3.5 w-3.5 text-primary animate-pulse" />
                )}
              </Button>
            )}

            {/* Botón de Descartar / Recuperar oferta (intercambiado al pie, solo icono) */}
            {onUpdateStatus && (
              <Button
                size="sm"
                variant="ghost"
                onClick={handleToggleDiscard}
                className={`h-7 w-7 p-0 rounded-md shrink-0 transition-colors flex items-center justify-center ${
                  isDiscarded
                    ? "text-emerald-400 hover:text-emerald-300 hover:bg-emerald-500/15"
                    : "text-muted-foreground/60 hover:text-rose-400 hover:bg-rose-500/15"
                }`}
                title={isDiscarded ? "Recuperar a ofertas activas" : "Descartar oferta"}
              >
                {isDiscarded ? <RotateCcw className="h-3.5 w-3.5" /> : <X className="h-3.5 w-3.5" />}
              </Button>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
