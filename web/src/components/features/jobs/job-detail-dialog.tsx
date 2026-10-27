"use client";

import React from "react";
import {
  RefreshCw,
  CheckCircle2,
  ExternalLink,
  Download,
  AlertTriangle,
  XCircle,
  Briefcase,
  Clock,
  GraduationCap,
  DollarSign,
  Sparkles,
} from "lucide-react";
import { Dialog } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { JobDetail } from "@/types";
import { api } from "@/lib/api";
import { JobScoreBadge, JobStatusBadge, JobModalityBadge } from "./job-badges";

interface JobDetailDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  jobDetail: JobDetail | null;
  loading: boolean;
  onUpdateStatus?: (id: number, status: string) => void;
}

export function JobDetailDialog({
  open,
  onOpenChange,
  jobDetail,
  loading,
}: JobDetailDialogProps) {
  const formatSalary = () => {
    if (!jobDetail) return null;
    const { salary_min, salary_max, salary_currency } = jobDetail;
    const curr = salary_currency || "€";
    if (salary_min && salary_max) {
      return `${salary_min.toLocaleString()} - ${salary_max.toLocaleString()} ${curr}`;
    }
    if (salary_min) return `Desde ${salary_min.toLocaleString()} ${curr}`;
    if (salary_max) return `Hasta ${salary_max.toLocaleString()} ${curr}`;
    return null;
  };

  const salaryFormatted = formatSalary();

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={jobDetail?.title || "Detalle de la Candidatura"}
      description={`${jobDetail?.company || "Empresa"} · ${jobDetail?.location || "Ubicación"}`}
      maxWidth="2xl"
    >
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <RefreshCw className="h-6 w-6 animate-spin text-primary" />
        </div>
      ) : jobDetail ? (
        <div className="space-y-4 max-h-[72dvh] overflow-y-auto pr-1 text-xs">
          {/* 1. Cabecera de Estado, Modalidad y Puntuación ATS */}
          <div className="flex flex-wrap items-center justify-between gap-2 p-3 rounded-lg bg-muted/30 border">
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground font-medium">Estado:</span>
              <JobStatusBadge status={jobDetail.status} size="md" />
            </div>

            <div className="flex items-center gap-2">
              <span className="text-muted-foreground font-medium">Modalidad:</span>
              <JobModalityBadge job={jobDetail} size="md" />
            </div>

            <div className="flex items-center gap-2">
              <span className="text-muted-foreground font-medium">Afinidad ATS:</span>
              <JobScoreBadge
                score={jobDetail.score}
                isEvaluating={jobDetail.status === "evaluating"}
                size="md"
              />
            </div>
          </div>

          {/* 2. Condiciones Laborales Reales desde Base de Datos SQLite */}
          {(jobDetail.contract_type || jobDetail.schedule || jobDetail.education_level || salaryFormatted) && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 p-2.5 rounded-lg border bg-card/60">
              {jobDetail.contract_type && (
                <div className="space-y-0.5">
                  <span className="text-3xs text-muted-foreground flex items-center gap-1 font-medium">
                    <Briefcase className="h-3 w-3 text-primary/70" /> Contrato
                  </span>
                  <p className="font-semibold text-2xs truncate" title={jobDetail.contract_type}>
                    {jobDetail.contract_type}
                  </p>
                </div>
              )}
              {jobDetail.schedule && (
                <div className="space-y-0.5">
                  <span className="text-3xs text-muted-foreground flex items-center gap-1 font-medium">
                    <Clock className="h-3 w-3 text-primary/70" /> Jornada
                  </span>
                  <p className="font-semibold text-2xs truncate" title={jobDetail.schedule}>
                    {jobDetail.schedule}
                  </p>
                </div>
              )}
              {jobDetail.education_level && (
                <div className="space-y-0.5">
                  <span className="text-3xs text-muted-foreground flex items-center gap-1 font-medium">
                    <GraduationCap className="h-3 w-3 text-primary/70" /> Formación
                  </span>
                  <p className="font-semibold text-2xs truncate" title={jobDetail.education_level}>
                    {jobDetail.education_level}
                  </p>
                </div>
              )}
              {salaryFormatted && (
                <div className="space-y-0.5">
                  <span className="text-3xs text-muted-foreground flex items-center gap-1 font-medium">
                    <DollarSign className="h-3 w-3 text-emerald-400" /> Salario
                  </span>
                  <p className="font-semibold text-2xs text-emerald-400 truncate" title={salaryFormatted}>
                    {salaryFormatted}
                  </p>
                </div>
              )}
            </div>
          )}

          {/* 3. Justificación y Razonamiento del Modelo Local de IA */}
          {jobDetail.reasoning && (
            <div className="p-3 rounded-lg bg-primary/5 border border-primary/20 space-y-1.5">
              <h4 className="font-semibold text-primary flex items-center gap-1.5 text-xs">
                <Sparkles className="h-3.5 w-3.5" /> Razonamiento del Modelo Local
              </h4>
              <p className="text-muted-foreground leading-relaxed whitespace-pre-wrap text-2xs">
                {jobDetail.reasoning}
              </p>
            </div>
          )}

          {/* 4. Puntos Fuertes y Carencias Evaluados por la IA */}
          {((jobDetail.strengths && jobDetail.strengths.length > 0) || (jobDetail.gaps && jobDetail.gaps.length > 0)) && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              {jobDetail.strengths && jobDetail.strengths.length > 0 && (
                <div className="p-2.5 rounded-lg border border-emerald-500/20 bg-emerald-500/5 space-y-1">
                  <h4 className="font-medium text-emerald-400 flex items-center gap-1 text-2xs">
                    <CheckCircle2 className="h-3 w-3" /> Puntos fuertes detectados:
                  </h4>
                  <ul className="list-disc list-inside space-y-0.5 text-3xs text-muted-foreground">
                    {jobDetail.strengths.map((str: string, i: number) => (
                      <li key={i}>{str}</li>
                    ))}
                  </ul>
                </div>
              )}

              {jobDetail.gaps && jobDetail.gaps.length > 0 && (
                <div className="p-2.5 rounded-lg border border-amber-500/20 bg-amber-500/5 space-y-1">
                  <h4 className="font-medium text-amber-400 flex items-center gap-1 text-2xs">
                    <AlertTriangle className="h-3 w-3" /> Carencias o discrepancias:
                  </h4>
                  <ul className="list-disc list-inside space-y-0.5 text-3xs text-muted-foreground">
                    {jobDetail.gaps.map((gap: string, i: number) => (
                      <li key={i}>{gap}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* 5. Competencias Coincidentes y Faltantes */}
          <div className="space-y-2">
            {jobDetail.matched_skills && jobDetail.matched_skills.length > 0 && (
              <div className="space-y-1">
                <span className="font-medium text-foreground text-2xs flex items-center gap-1">
                  <CheckCircle2 className="h-3 w-3 text-emerald-400" /> Habilidades coincidentes en tu CV:
                </span>
                <div className="flex flex-wrap gap-1">
                  {jobDetail.matched_skills.map((skill: string, i: number) => (
                    <span key={i} className="px-2 py-0.5 rounded bg-muted/80 text-3xs font-mono text-emerald-400 border border-emerald-500/20">
                      {skill}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {jobDetail.missing_skills && jobDetail.missing_skills.length > 0 && (
              <div className="space-y-1">
                <span className="font-medium text-muted-foreground text-2xs flex items-center gap-1">
                  <XCircle className="h-3 w-3 text-rose-400" /> Requisitos no detectados en tu CV:
                </span>
                <div className="flex flex-wrap gap-1">
                  {jobDetail.missing_skills.map((skill: string, i: number) => (
                    <span key={i} className="px-2 py-0.5 rounded bg-rose-500/10 text-3xs font-mono text-rose-400 border border-rose-500/20">
                      {skill}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* 6. Descripción Original de la Oferta */}
          {jobDetail.description && (
            <div className="space-y-1.5 pt-1">
              <h4 className="font-medium text-foreground text-2xs">Descripción original del puesto:</h4>
              <div className="p-3 rounded-md bg-muted/30 border text-muted-foreground leading-relaxed max-h-48 overflow-y-auto whitespace-pre-wrap font-sans text-2xs">
                {jobDetail.description}
              </div>
            </div>
          )}

          {/* 7. Acciones, Enlace Oficial y Descarga de Documentos */}
          <div className="flex flex-wrap items-center justify-between gap-2 pt-3 border-t">
            <a
              href={jobDetail.canonical_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline flex items-center gap-1 font-medium"
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
                  className="h-8 text-xs flex items-center gap-1 text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/10"
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
                  className="h-8 text-xs flex items-center gap-1 text-blue-400 border-blue-500/30 hover:bg-blue-500/10"
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
