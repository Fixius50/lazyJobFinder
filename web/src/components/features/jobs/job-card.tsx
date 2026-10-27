"use client";

import React, { useState, useEffect } from "react";
import {
  Building,
  MapPin,
  Calendar,
  ExternalLink,
  Download,
  Eye,
  RefreshCw,
  Sparkles,
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
  onUpdateStatus?: (newStatus: string) => void;
  onUpdateJob?: (updatedJob: JobListItem) => void;
}

export function JobCard({ job, onOpenDetail, onUpdateJob }: JobCardProps) {
  const sourceMeta = PORTAL_SOURCES[job.source as keyof typeof PORTAL_SOURCES];
  const isEvaluating = job.status === "evaluating";

  const [hasCv, setHasCv] = useState<boolean>(!!job.has_cv);
  const [hasLetter, setHasLetter] = useState<boolean>(!!job.has_letter);
  const [isGenerating, setIsGenerating] = useState<boolean>(job.status === "generating_docs");

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
    <Card className="group flex flex-col justify-between hover:border-primary/50 hover:shadow-md transition-all duration-200 bg-card/80 backdrop-blur-sm border rounded-xl overflow-hidden h-full">
      <CardContent className="p-3 sm:p-3.5 flex flex-col h-full justify-between space-y-3">
        {/* Cabecera de la Tarjeta: Badges de afinidad, estado y fuente */}
        <div className="space-y-2.5">
          <div className="flex items-center justify-between gap-1 flex-wrap">
            <div className="flex items-center gap-1 flex-wrap">
              <JobScoreBadge score={job.score} isEvaluating={isEvaluating} size="sm" />
              <JobStatusBadge status={job.status} size="sm" />
            </div>
            <div className="flex items-center gap-1">
              <span className="text-3xs font-medium px-1.5 py-0.5 rounded bg-muted/90 text-muted-foreground shrink-0">
                {sourceMeta ? sourceMeta.label : job.source}
              </span>
              <JobModalityBadge job={job} size="sm" />
            </div>
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

        {/* Pie de la Tarjeta: Acciones de descarga y botón de generación */}
        <div className="pt-2 border-t border-border/40 flex items-center justify-between gap-1.5">
          <div className="flex items-center gap-1">
            {hasCv ? (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => window.open(api.getDocumentUrl(job.id, "cv_pdf"), "_blank")}
                title="Descargar CV adaptado en PDF"
                className="h-7 px-1.5 text-3xs flex items-center gap-1 text-emerald-400 hover:text-emerald-300 hover:bg-emerald-500/10"
              >
                <Download className="h-3 w-3" />
                <span>CV</span>
              </Button>
            ) : null}

            {hasLetter ? (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => window.open(api.getDocumentUrl(job.id, "letter_pdf"), "_blank")}
                title="Descargar Carta en PDF"
                className="h-7 px-1.5 text-3xs flex items-center gap-1 text-blue-400 hover:text-blue-300 hover:bg-blue-500/10"
              >
                <Download className="h-3 w-3" />
                <span>Carta</span>
              </Button>
            ) : null}
          </div>

          <div className="flex items-center gap-1.5 ml-auto">
            {/* Botón de Generar CV y Carta bajo demanda (a la izquierda de Vista/Detalles) */}
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
              className={`h-7 px-2 text-2xs flex items-center gap-1 font-medium transition-all ${
                hasCv && hasLetter
                  ? "text-muted-foreground hover:text-primary hover:bg-primary/10"
                  : "bg-primary/10 text-primary border-primary/30 hover:bg-primary/20 hover:border-primary/50 shadow-xs"
              }`}
            >
              {isGenerating ? (
                <>
                  <RefreshCw className="h-3 w-3 animate-spin text-primary" />
                  <span>Generando...</span>
                </>
              ) : hasCv && hasLetter ? (
                <>
                  <Sparkles className="h-3 w-3 text-amber-400" />
                  <span className="hidden sm:inline">Regenerar</span>
                </>
              ) : (
                <>
                  <Sparkles className="h-3 w-3 text-primary animate-pulse" />
                  <span>Generar</span>
                </>
              )}
            </Button>

            <Button
              size="sm"
              variant="secondary"
              onClick={() => onOpenDetail(job.id)}
              className="h-7 px-2 text-xs flex items-center gap-1 font-medium shadow-xs hover:bg-secondary/80"
              title="Ver detalles de la oferta"
            >
              <Eye className="h-3 w-3" />
              <span>Detalles</span>
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
