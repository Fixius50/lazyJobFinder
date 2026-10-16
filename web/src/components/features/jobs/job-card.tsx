"use client";

import React from "react";
import {
  Building,
  MapPin,
  Calendar,
  ExternalLink,
  Download,
  Eye,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { JobListItem } from "@/types";
import { formatDateTime } from "@/lib/utils";
import { APPLICATION_STATUSES, PORTAL_SOURCES, ApplicationStatusKey } from "@/lib/constants";
import { api } from "@/lib/api";

interface JobCardProps {
  job: JobListItem;
  onOpenDetail: (id: number) => void;
  onUpdateStatus?: (newStatus: string) => void;
}

export function JobCard({ job, onOpenDetail }: JobCardProps) {
  const sourceMeta = PORTAL_SOURCES[job.source as keyof typeof PORTAL_SOURCES];

  const getScoreBadge = (score?: number | null) => {
    if (score === null || score === undefined) {
      return (
        <Badge variant="secondary" className="text-[10px] py-0 px-1.5 font-mono">
          Sin evaluar
        </Badge>
      );
    }
    if (score >= 80) {
      return (
        <Badge variant="success" className="text-[10px] py-0 px-1.5 font-mono font-bold">
          {score} / 100
        </Badge>
      );
    }
    if (score >= 65) {
      return (
        <Badge variant="warning" className="text-[10px] py-0 px-1.5 font-mono font-bold">
          {score} / 100
        </Badge>
      );
    }
    return (
      <Badge variant="destructive" className="text-[10px] py-0 px-1.5 font-mono font-bold">
        {score} / 100
      </Badge>
    );
  };

  const getStatusBadge = (status: string) => {
    const meta = APPLICATION_STATUSES[status as ApplicationStatusKey];
    if (meta) {
      return (
        <Badge variant={meta.badge} className="text-[10px] py-0 px-1.5">
          {meta.label}
        </Badge>
      );
    }
    return (
      <Badge variant="secondary" className="text-[10px] py-0 px-1.5">
        {status}
      </Badge>
    );
  };

  return (
    <Card className="group flex flex-col justify-between hover:border-primary/50 hover:shadow-md transition-all duration-200 bg-card/80 backdrop-blur-sm border rounded-xl overflow-hidden h-full">
      <CardContent className="p-3 sm:p-3.5 flex flex-col h-full justify-between space-y-3">
        {/* Cabecera de la Tarjeta: Badges de afinidad, estado y fuente */}
        <div className="space-y-2.5">
          <div className="flex items-center justify-between gap-1 flex-wrap">
            <div className="flex items-center gap-1 flex-wrap">
              {getScoreBadge(job.score)}
              {getStatusBadge(job.status)}
            </div>
            <div className="flex items-center gap-1">
              <span className="text-[10px] font-medium px-1.5 py-0.2 rounded bg-muted/90 text-muted-foreground shrink-0">
                {sourceMeta ? sourceMeta.label : job.source}
              </span>
              {job.is_remote ? (
                <span className="text-[9px] font-semibold px-1 py-0.2 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20 shrink-0">
                  Remoto
                </span>
              ) : null}
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
          <div className="space-y-1 text-[11px] text-muted-foreground pt-0.5">
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

            <div className="flex items-center gap-1 text-[10px] text-muted-foreground/60">
              <Calendar className="h-2.5 w-2.5 shrink-0" />
              <span>{formatDateTime(job.created_at)}</span>
            </div>
          </div>
        </div>

        {/* Pie de la Tarjeta: Acciones de descarga de documentos y botón de detalles */}
        <div className="pt-2 border-t border-border/40 flex items-center justify-between gap-1.5">
          <div className="flex items-center gap-1">
            {job.has_cv && (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => window.open(api.getDocumentUrl(job.id, "cv_pdf"), "_blank")}
                title="Descargar CV adaptado en PDF"
                className="h-7 px-1.5 text-[10px] flex items-center gap-1 text-emerald-400 hover:text-emerald-300 hover:bg-emerald-500/10"
              >
                <Download className="h-3 w-3" />
                <span>CV</span>
              </Button>
            )}
            {job.has_letter && (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => window.open(api.getDocumentUrl(job.id, "letter_pdf"), "_blank")}
                title="Descargar Carta en PDF"
                className="h-7 px-1.5 text-[10px] flex items-center gap-1 text-blue-400 hover:text-blue-300 hover:bg-blue-500/10"
              >
                <Download className="h-3 w-3" />
                <span>Carta</span>
              </Button>
            )}
          </div>

          <Button
            size="sm"
            variant="secondary"
            onClick={() => onOpenDetail(job.id)}
            className="h-7 px-2 text-xs flex items-center gap-1 ml-auto font-medium shadow-xs hover:bg-secondary/80"
          >
            <Eye className="h-3 w-3" />
            <span>Detalles</span>
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
