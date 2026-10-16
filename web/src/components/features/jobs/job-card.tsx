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
}

export function JobCard({ job, onOpenDetail }: JobCardProps) {
  const sourceMeta = PORTAL_SOURCES[job.source as keyof typeof PORTAL_SOURCES];

  const getScoreBadge = (score?: number | null) => {
    if (score === null || score === undefined) {
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
    <Card className="hover:border-primary/40 transition-all duration-150 bg-card/80 backdrop-blur-sm shadow-sm">
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
            <a
              href={job.canonical_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5"
            >
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
            onClick={() => onOpenDetail(job.id)}
            className="h-8 text-xs flex items-center gap-1"
          >
            <Eye className="h-3.5 w-3.5" />
            <span>Detalles</span>
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
