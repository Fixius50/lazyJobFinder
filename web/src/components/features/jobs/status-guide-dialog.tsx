"use client";

import React from "react";
import { UserCheck, Bot, Sparkles, ArrowRight } from "lucide-react";
import { Dialog } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { APPLICATION_STATUSES, ApplicationStatusKey } from "@/lib/constants";
import { JobStatusBadge } from "./job-badges";

interface StatusGuideDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

interface StatusDocItem {
  key: ApplicationStatusKey;
  description: string;
}

const AUTOMATIC_STATUSES: StatusDocItem[] = [
  {
    key: "discovered",
    description:
      "Registrada en la base de datos local SQLite desde un portal público (InfoJobs, Tecnoempleo, Indeed, LinkedIn, etc.). Pendiente de análisis por la IA.",
  },
  {
    key: "evaluating",
    description:
      "El motor de inferencia local Ollama está analizando activamente la oferta frente a tu CV activo y perfil profesional.",
  },
  {
    key: "generating_docs",
    description:
      "La IA está adaptando el currículum vitae y redactando la carta de presentación personalizada para los requisitos de esta vacante.",
  },
  {
    key: "evaluated",
    description:
      "Evaluación completada con éxito. Supera el umbral de afinidad configurado y dispone de puntuación ATS, justificación y habilidades coincidentes.",
  },
  {
    key: "discarded",
    description:
      "Descartada automáticamente por baja afinidad con tu CV (< umbral mínimo) o por coincidencia con palabras clave de exclusión.",
  },
];

const MANUAL_STATUSES: StatusDocItem[] = [
  {
    key: "interview",
    description:
      "Márcala manualmente cuando el equipo de selección o RRHH te contacte para concertar una entrevista telefónica o técnica.",
  },
  {
    key: "rejected",
    description:
      "Márcala si la empresa te comunica que no continúas en el proceso de selección o si la posición ha sido cerrada.",
  },
];

export function StatusGuideDialog({ open, onOpenChange }: StatusGuideDialogProps) {
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Guía de Estados y Ciclo de Vida de Candidaturas"
      description="Conoce el ciclo de vida automático del pipeline y el seguimiento manual de cada oferta en lazyJobFinder."
      maxWidth="2xl"
      footer={
        <div className="flex justify-end w-full">
          <Button size="sm" onClick={() => onOpenChange(false)} className="text-xs">
            Entendido
          </Button>
        </div>
      }
    >
      <div className="space-y-5 text-xs text-foreground/90 max-h-[70vh] overflow-y-auto pr-1">
        {/* Sección 1: Estados Automáticos del Pipeline */}
        <div className="space-y-2.5">
          <div className="flex items-center gap-1.5 font-semibold text-foreground text-sm border-b pb-1.5">
            <Bot className="h-4 w-4 text-primary" />
            <span>Estados Automáticos (Scraping, IA y Generación de Docs)</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            {AUTOMATIC_STATUSES.map(({ key, description }) => (
              <div key={key} className="p-2.5 rounded-lg border bg-muted/20 space-y-1">
                <div className="flex items-center gap-2">
                  <JobStatusBadge status={key} size="sm" />
                  <span className="text-3xs text-muted-foreground font-mono">{key}</span>
                </div>
                <p className="text-muted-foreground text-2xs leading-relaxed">{description}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Sección 2: Estados de Seguimiento Manual del Candidato */}
        <div className="space-y-2.5">
          <div className="flex items-center gap-1.5 font-semibold text-foreground text-sm border-b pb-1.5">
            <UserCheck className="h-4 w-4 text-emerald-400" />
            <span>Estados de Seguimiento del Candidato (Control Manual)</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            {MANUAL_STATUSES.map(({ key, description }) => (
              <div key={key} className="p-2.5 rounded-lg border bg-muted/20 space-y-1">
                <div className="flex items-center gap-2">
                  <JobStatusBadge status={key} size="sm" />
                  <span className="text-3xs text-muted-foreground font-mono">{key}</span>
                </div>
                <p className="text-muted-foreground text-2xs leading-relaxed">{description}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Flujo Visual */}
        <div className="p-3 rounded-lg border bg-primary/5 text-2xs space-y-1.5">
          <div className="flex items-center gap-1.5 font-semibold text-primary">
            <Sparkles className="h-3.5 w-3.5" />
            <span>Flujo habitual de una oferta:</span>
          </div>
          <div className="flex flex-wrap items-center gap-1.5 text-2xs text-muted-foreground">
            <span className="font-medium text-foreground">Portal</span>
            <ArrowRight className="h-3 w-3" />
            <span>Descubierta</span>
            <ArrowRight className="h-3 w-3" />
            <span>Evaluando (Ollama)</span>
            <ArrowRight className="h-3 w-3" />
            <span>Generando docs</span>
            <ArrowRight className="h-3 w-3" />
            <span>Evaluada / Descartada</span>
            <ArrowRight className="h-3 w-3" />
            <span className="text-emerald-400 font-semibold">Entrevista</span>
          </div>
        </div>
      </div>
    </Dialog>
  );
}
