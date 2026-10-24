"use client";

import React from "react";
import {
  RefreshCw,
  CheckCircle2,
  ExternalLink,
  Download,
} from "lucide-react";
import { Dialog } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { JobDetail } from "@/types";
import { APPLICATION_STATUSES } from "@/lib/constants";
import { api } from "@/lib/api";

interface JobDetailDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  jobDetail: JobDetail | null;
  loading: boolean;
  onUpdateStatus: (id: number, status: string) => void;
}

export function JobDetailDialog({
  open,
  onOpenChange,
  jobDetail,
  loading,
  onUpdateStatus,
}: JobDetailDialogProps) {
  const getScoreBadge = (score?: number | null) => {
    if (jobDetail?.status === "evaluating") {
      return (
        <Badge variant="warning" className="animate-pulse flex items-center gap-1">
          <RefreshCw className="h-3 w-3 animate-spin" />
          Evaluando...
        </Badge>
      );
    }
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

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={jobDetail?.title || "Detalle de la Candidatura"}
      description={`${jobDetail?.company || "Empresa"} · ${jobDetail?.location || "Ubicación"}`}
    >
      {loading ? (
        <div className="flex items-center justify-center py-8">
          <RefreshCw className="h-5 w-5 animate-spin text-primary" />
        </div>
      ) : jobDetail ? (
        <div className="space-y-4 max-h-[70dvh] overflow-y-auto pr-1 text-xs">
          {/* Cabecera de Estado y Puntuación */}
          <div className="flex flex-wrap items-center justify-between gap-2 p-3 rounded-lg bg-muted/40 border">
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground font-medium">Estado:</span>
              <Select
                value={jobDetail.status}
                onChange={(e) => onUpdateStatus(jobDetail.id, e.target.value)}
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
              {getScoreBadge(jobDetail.score)}
            </div>
          </div>

          {/* Justificación de la IA si existe */}
          {jobDetail.reasoning && (
            <div className="p-3 rounded-lg bg-primary/5 border border-primary/20 space-y-1">
              <h4 className="font-semibold text-primary flex items-center gap-1.5">
                <CheckCircle2 className="h-3.5 w-3.5" /> Razonamiento del Modelo Local
              </h4>
              <p className="text-muted-foreground leading-relaxed whitespace-pre-wrap">
                {jobDetail.reasoning}
              </p>
            </div>
          )}

          {/* Competencias y Habilidades Coincidentes */}
          {jobDetail.matched_skills && jobDetail.matched_skills.length > 0 && (
            <div className="space-y-1.5">
              <h4 className="font-medium text-foreground">Habilidades coincidentes:</h4>
              <div className="flex flex-wrap gap-1">
                {jobDetail.matched_skills.map((skill: string, i: number) => (
                  <span key={i} className="px-2 py-0.5 rounded bg-muted text-2xs font-mono text-primary">
                    {skill}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Descripción Completa de la Oferta */}
          {jobDetail.description && (
            <div className="space-y-1.5">
              <h4 className="font-medium text-foreground">Descripción original del puesto:</h4>
              <div className="p-3 rounded-md bg-muted/30 border text-muted-foreground leading-relaxed max-h-48 overflow-y-auto whitespace-pre-wrap font-sans text-2xs">
                {jobDetail.description}
              </div>
            </div>
          )}

          {/* Enlace y Documentos */}
          <div className="flex flex-wrap items-center justify-between gap-2 pt-3 border-t">
            <a
              href={jobDetail.canonical_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline flex items-center gap-1"
            >
              Abrir oferta en portal oficial
              <ExternalLink className="h-3 w-3" />
            </a>

            <div className="flex items-center gap-2">
              {jobDetail.has_cv && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => window.open(api.getDocumentUrl(jobDetail.id, "cv_pdf"), "_blank")}
                  className="h-8 text-xs flex items-center gap-1"
                >
                  <Download className="h-3.5 w-3.5" />
                  CV Adaptado
                </Button>
              )}

              {jobDetail.has_letter && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => window.open(api.getDocumentUrl(jobDetail.id, "letter_pdf"), "_blank")}
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
  );
}
