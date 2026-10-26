"use client";

import React from "react";
import { Info, Sparkles, UserCheck, Bot, FileText, ArrowRight, ShieldCheck } from "lucide-react";
import { Dialog } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface StatusGuideDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function StatusGuideDialog({ open, onOpenChange }: StatusGuideDialogProps) {
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Guía de Estados y Etiquetas de Candidaturas"
      description="Conoce el ciclo de vida automático y manual de cada oferta en lazyJobFinder."
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
        {/* Sección 1: Estados Automáticos (Sistema e IA) */}
        <div className="space-y-2.5">
          <div className="flex items-center gap-1.5 font-semibold text-foreground text-sm border-b pb-1.5">
            <Bot className="h-4 w-4 text-primary" />
            <span>Estados Automáticos (Scraping, IA y Notificación)</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            {/* Descubierta */}
            <div className="p-2.5 rounded-lg border bg-muted/30 space-y-1">
              <div className="flex items-center gap-2">
                <Badge variant="secondary" className="text-3xs py-0 px-1.5 font-medium">
                  Descubierta
                </Badge>
                <span className="text-3xs text-muted-foreground font-mono">discovered</span>
              </div>
              <p className="text-muted-foreground text-2xs leading-relaxed">
                El conector (Tecnoempleo, InfoJobs, Indeed, etc.) acaba de registrar la oferta desde la fuente pública en la base de datos local SQLite. Aún no ha sido evaluada por la IA.
              </p>
            </div>

            {/* Evaluada */}
            <div className="p-2.5 rounded-lg border bg-muted/30 space-y-1">
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="text-3xs py-0 px-1.5 font-medium">
                  Evaluada
                </Badge>
                <span className="text-3xs text-muted-foreground font-mono">evaluated</span>
              </div>
              <p className="text-muted-foreground text-2xs leading-relaxed">
                El modelo IA local (Ollama) evaluó la vacante contra tu currículum activo, otorgándole una puntuación de afinidad (0 a 100), pros y contras. Supera el umbral mínimo configurado.
              </p>
            </div>

            {/* Descartada */}
            <div className="p-2.5 rounded-lg border bg-destructive/10 border-destructive/20 space-y-1">
              <div className="flex items-center gap-2">
                <Badge variant="destructive" className="text-3xs py-0 px-1.5 font-medium">
                  Descartada
                </Badge>
                <span className="text-3xs text-muted-foreground font-mono">discarded</span>
              </div>
              <p className="text-muted-foreground text-2xs leading-relaxed">
                Descartada automáticamente por dos posibles razones:
                <br />• <strong>Pre-filtro:</strong> Contiene términos de exclusión (ej. Senior, Lead...).
                <br />• <strong>Baja afinidad:</strong> El análisis de Ollama determinó que tu perfil no encaja o la puntuación quedó bajo el umbral mínimo (&lt;65).
              </p>
            </div>
          </div>
        </div>

        {/* Sección 2: Estados de Seguimiento del Candidato */}
        <div className="space-y-2.5">
          <div className="flex items-center gap-1.5 font-semibold text-foreground text-sm border-b pb-1.5">
            <UserCheck className="h-4 w-4 text-emerald-400" />
            <span>Estados de Seguimiento del Candidato</span>
          </div>

          <p className="text-2xs text-muted-foreground">
            Estados para llevar el control de tus candidaturas reales tras la evaluación de la IA:
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            {/* Entrevista */}
            <div className="p-2.5 rounded-lg border bg-emerald-500/10 border-emerald-500/20 space-y-1">
              <div className="flex items-center gap-2">
                <Badge variant="success" className="text-3xs py-0 px-1.5 font-medium">
                  Entrevista
                </Badge>
                <span className="text-3xs text-muted-foreground font-mono">interview</span>
              </div>
              <p className="text-muted-foreground text-2xs leading-relaxed">
                Márcala cuando el equipo de selección o RRHH te contacte para concertar una entrevista telefónica o técnica.
              </p>
            </div>

            {/* Rechazada */}
            <div className="p-2.5 rounded-lg border bg-destructive/10 border-destructive/20 space-y-1">
              <div className="flex items-center gap-2">
                <Badge variant="destructive" className="text-3xs py-0 px-1.5 font-medium">
                  Rechazada
                </Badge>
                <span className="text-3xs text-muted-foreground font-mono">rejected</span>
              </div>
              <p className="text-muted-foreground text-2xs leading-relaxed">
                Márcala si la empresa te comunica que no continúas en el proceso de selección o cierran la posición.
              </p>
            </div>
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
            <span>Filtros &amp; Ollama</span>
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
