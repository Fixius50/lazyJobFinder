"use client";

import React from "react";
import {
  RefreshCw,
  CheckCircle2,
  ExternalLink,
  Download,
  AlertTriangle,
  XCircle,
  X,
  RotateCcw,
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
  onUpdateStatus,
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
      title={
        jobDetail ? (
          <a
            href={jobDetail.canonical_url}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:underline hover:text-primary transition-colors inline-flex items-center gap-1.5 group"
            title="Abrir oferta en portal oficial"
          >
            <span>{jobDetail.title}</span>
            <ExternalLink className="h-3.5 w-3.5 opacity-50 group-hover:opacity-100 transition-opacity shrink-0" />
          </a>
        ) : (
          "Detalle de la Candidatura"
        )
      }
      description={`${jobDetail?.company || "Empresa"} · ${jobDetail?.location || "Ubicación"}`}
      maxWidth="xl"
    >
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <RefreshCw className="h-6 w-6 animate-spin text-primary" />
        </div>
      ) : jobDetail ? (
        <div className="space-y-3.5 max-h-[75dvh] overflow-y-auto pr-1 text-xs">
          {/* 1. Cabecera integrada: Badges a la izquierda + Acciones (Descartar, CV, Carta) a la derecha */}
          <div className="flex flex-wrap items-center justify-between gap-2 pb-2.5 border-b border-border/40">
            {/* Badges de afinidad, estado, modalidad y condiciones */}
            <div className="flex flex-wrap items-center gap-1.5">
              <JobScoreBadge
                score={jobDetail.score}
                isEvaluating={jobDetail.status === "evaluating"}
                size="sm"
              />
              <JobStatusBadge status={jobDetail.status} size="sm" />
              <JobModalityBadge job={jobDetail} size="sm" />
              {salaryFormatted && (
                <span className="text-3xs font-medium px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono">
                  {salaryFormatted}
                </span>
              )}
              {jobDetail.contract_type && (
                <span className="text-3xs text-muted-foreground px-2 py-0.5 rounded bg-muted/60 border border-border/40">
                  {jobDetail.contract_type}
                </span>
              )}
              {jobDetail.schedule && (
                <span className="text-3xs text-muted-foreground px-2 py-0.5 rounded bg-muted/60 border border-border/40">
                  {jobDetail.schedule}
                </span>
              )}
            </div>

            {/* Acciones principales trasladadas del footer al header */}
            <div className="flex items-center gap-1.5 shrink-0 ml-auto">
              {onUpdateStatus && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    const nextStatus = jobDetail.status === "discarded" ? "evaluated" : "discarded";
                    onUpdateStatus(jobDetail.id, nextStatus);
                    onOpenChange(false);
                  }}
                  className={`h-7 px-2.5 text-2xs flex items-center gap-1.5 font-medium ${
                    jobDetail.status === "discarded"
                      ? "text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/10"
                      : "text-rose-400 border-rose-500/30 hover:bg-rose-500/10"
                  }`}
                  title={jobDetail.status === "discarded" ? "Recuperar a ofertas activas" : "Descartar esta oferta"}
                >
                  {jobDetail.status === "discarded" ? (
                    <>
                      <RotateCcw className="h-3 w-3" />
                      <span>Recuperar</span>
                    </>
                  ) : (
                    <>
                      <X className="h-3 w-3" />
                      <span>Descartar</span>
                    </>
                  )}
                </Button>
              )}

              {jobDetail.has_cv && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => window.open(api.getDocumentUrl(jobDetail.id, "cv_pdf"), "_blank")}
                  className="h-7 px-2.5 text-2xs flex items-center gap-1 text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/10"
                  title="Descargar CV Adaptado en PDF"
                >
                  <Download className="h-3 w-3" />
                  <span>CV Adaptado</span>
                </Button>
              )}

              {jobDetail.has_letter && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => window.open(api.getDocumentUrl(jobDetail.id, "letter_pdf"), "_blank")}
                  className="h-7 px-2.5 text-2xs flex items-center gap-1 text-blue-400 border-blue-500/30 hover:bg-blue-500/10"
                  title="Descargar Carta Adaptada en PDF"
                >
                  <Download className="h-3 w-3" />
                  <span>Carta Adaptada</span>
                </Button>
              )}
            </div>
          </div>

          {/* 2. Razonamiento IA en estilo cita editorial limpio */}
          {jobDetail.reasoning && (
            <blockquote className="border-l-2 border-primary/60 pl-3 py-1.5 text-2xs text-muted-foreground/90 italic leading-relaxed bg-primary/5 rounded-r">
              “{jobDetail.reasoning}”
            </blockquote>
          )}

          {/* 3. Puntos fuertes y carencias en micro-tags horizontales */}
          {((jobDetail.strengths && jobDetail.strengths.length > 0) || (jobDetail.gaps && jobDetail.gaps.length > 0)) && (
            <div className="space-y-2">
              {jobDetail.strengths && jobDetail.strengths.length > 0 && (
                <div className="space-y-1">
                  <span className="text-3xs font-semibold text-emerald-400/90 uppercase tracking-wider flex items-center gap-1">
                    <CheckCircle2 className="h-3 w-3" /> Puntos fuertes
                  </span>
                  <div className="flex flex-wrap gap-1">
                    {jobDetail.strengths.map((str: string, i: number) => (
                      <span
                        key={i}
                        className="inline-flex items-center text-3xs px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-300 border border-emerald-500/20"
                      >
                        {str}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {jobDetail.gaps && jobDetail.gaps.length > 0 && (
                <div className="space-y-1">
                  <span className="text-3xs font-semibold text-amber-400/90 uppercase tracking-wider flex items-center gap-1">
                    <AlertTriangle className="h-3 w-3" /> Carencias o discrepancias
                  </span>
                  <div className="flex flex-wrap gap-1">
                    {jobDetail.gaps.map((gap: string, i: number) => (
                      <span
                        key={i}
                        className="inline-flex items-center text-3xs px-2 py-0.5 rounded-md bg-amber-500/10 text-amber-300 border border-amber-500/20"
                      >
                        {gap}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* 4. Habilidades coincidentes y faltantes en micro-pills */}
          <div className="space-y-2">
            {jobDetail.matched_skills && jobDetail.matched_skills.length > 0 && (
              <div className="space-y-1">
                <span className="text-3xs font-semibold text-muted-foreground uppercase tracking-wider">
                  Habilidades coincidentes ({jobDetail.matched_skills.length})
                </span>
                <div className="flex flex-wrap gap-1">
                  {jobDetail.matched_skills.map((skill: string, i: number) => (
                    <span
                      key={i}
                      className="px-2 py-0.5 rounded bg-muted/80 text-3xs font-mono text-emerald-400 border border-emerald-500/20"
                    >
                      {skill}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {jobDetail.missing_skills && jobDetail.missing_skills.length > 0 && (
              <div className="space-y-1">
                <span className="text-3xs font-semibold text-muted-foreground uppercase tracking-wider">
                  Requisitos no detectados ({jobDetail.missing_skills.length})
                </span>
                <div className="flex flex-wrap gap-1">
                  {jobDetail.missing_skills.map((skill: string, i: number) => (
                    <span
                      key={i}
                      className="px-2 py-0.5 rounded bg-rose-500/10 text-3xs font-mono text-rose-400 border border-rose-500/20"
                    >
                      {skill}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* 5. Descripción original del puesto */}
          {jobDetail.description && (
            <div className="space-y-1 pt-1">
              <span className="text-3xs font-semibold text-muted-foreground uppercase tracking-wider">
                Descripción original
              </span>
              <div className="p-2.5 rounded-md bg-muted/20 border border-border/40 text-muted-foreground leading-relaxed max-h-36 overflow-y-auto whitespace-pre-wrap font-sans text-2xs">
                {jobDetail.description}
              </div>
            </div>
          )}
        </div>
      ) : null}
    </Dialog>
  );
}
