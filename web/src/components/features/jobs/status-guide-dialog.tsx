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
                <Badge variant="secondary" className="text-[10px] py-0 px-1.5 font-medium">
                  Descubierta
                </Badge>
                <span className="text-[10px] text-muted-foreground font-mono">discovered</span>
              </div>
              <p className="text-muted-foreground text-[11px] leading-relaxed">
                El conector (Tecnoempleo, InfoJobs, Indeed, etc.) acaba de registrar la oferta desde la fuente pública en la base de datos local SQLite. Aún no ha sido evaluada por la IA.
              </p>
            </div>

            {/* Evaluada */}
            <div className="p-2.5 rounded-lg border bg-muted/30 space-y-1">
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="text-[10px] py-0 px-1.5 font-medium">
                  Evaluada
                </Badge>
                <span className="text-[10px] text-muted-foreground font-mono">evaluated</span>
              </div>
              <p className="text-muted-foreground text-[11px] leading-relaxed">
                El modelo IA local (Ollama) evaluó la oferta contra tu CV, otorgándole una puntuación de afinidad (0 a 100) y pros/contras. Supera el umbral mínimo pero no se notificó por Telegram (ej. si Telegram está desactivado).
              </p>
            </div>

            {/* Notificada */}
            <div className="p-2.5 rounded-lg border bg-amber-500/10 border-amber-500/20 space-y-1">
              <div className="flex items-center gap-2">
                <Badge variant="warning" className="text-[10px] py-0 px-1.5 font-medium">
                  Notificada
                </Badge>
                <span className="text-[10px] text-muted-foreground font-mono">notified</span>
              </div>
              <p className="text-muted-foreground text-[11px] leading-relaxed">
                La vacante superó el umbral de afinidad (≥65), se generaron los documentos adaptados (CV y carta en PDF) y se envió la ficha con adjuntos a tu bot de Telegram.
              </p>
            </div>

            {/* Descartada */}
            <div className="p-2.5 rounded-lg border bg-destructive/10 border-destructive/20 space-y-1">
              <div className="flex items-center gap-2">
                <Badge variant="destructive" className="text-[10px] py-0 px-1.5 font-medium">
                  Descartada
                </Badge>
                <span className="text-[10px] text-muted-foreground font-mono">discarded</span>
              </div>
              <p className="text-muted-foreground text-[11px] leading-relaxed">
                Descartada automáticamente por dos posibles razones:
                <br />• <strong>Pre-filtro:</strong> Contiene términos de exclusión (ej. Senior, 10 años experiencia...).
                <br />• <strong>Baja afinidad:</strong> El análisis de Ollama determinó que tu perfil no encaja o la puntuación quedó bajo el umbral mínimo (&lt;65).
              </p>
            </div>
          </div>
        </div>

        {/* Sección 2: Estados Manuales de Seguimiento del Candidato */}
        <div className="space-y-2.5">
          <div className="flex items-center gap-1.5 font-semibold text-foreground text-sm border-b pb-1.5">
            <UserCheck className="h-4 w-4 text-emerald-400" />
            <span>Estados Manuales de Seguimiento (Control del Usuario)</span>
          </div>

          <p className="text-[11px] text-muted-foreground">
            Puedes cambiar manualmente estos estados desde la tarjeta pulsando en <strong>«Ver Detalles y Documentos»</strong> para llevar el control de tus candidaturas reales:
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            {/* Postulada */}
            <div className="p-2.5 rounded-lg border bg-muted/30 space-y-1">
              <div className="flex items-center gap-2">
                <Badge variant="default" className="text-[10px] py-0 px-1.5 font-medium">
                  Postulada
                </Badge>
                <span className="text-[10px] text-muted-foreground font-mono">applied</span>
              </div>
              <p className="text-muted-foreground text-[11px] leading-relaxed">
                Márcala cuando hayas entrado al portal o enviado tu CV a la empresa para saber que ya estás inscrito.
              </p>
            </div>

            {/* Entrevista */}
            <div className="p-2.5 rounded-lg border bg-emerald-500/10 border-emerald-500/20 space-y-1">
              <div className="flex items-center gap-2">
                <Badge variant="success" className="text-[10px] py-0 px-1.5 font-medium">
                  Entrevista
                </Badge>
                <span className="text-[10px] text-muted-foreground font-mono">interview</span>
              </div>
              <p className="text-muted-foreground text-[11px] leading-relaxed">
                Márcala cuando el equipo de selección o RRHH te contacte para concertar una entrevista telefónica o técnica.
              </p>
            </div>

            {/* Rechazada */}
            <div className="p-2.5 rounded-lg border bg-destructive/10 border-destructive/20 space-y-1">
              <div className="flex items-center gap-2">
                <Badge variant="destructive" className="text-[10px] py-0 px-1.5 font-medium">
                  Rechazada
                </Badge>
                <span className="text-[10px] text-muted-foreground font-mono">rejected</span>
              </div>
              <p className="text-muted-foreground text-[11px] leading-relaxed">
                Márcala si la empresa te comunica que no continúas en el proceso o han decidido cerrar la posición.
              </p>
            </div>

            {/* Archivada */}
            <div className="p-2.5 rounded-lg border bg-muted/30 space-y-1">
              <div className="flex items-center gap-2">
                <Badge variant="secondary" className="text-[10px] py-0 px-1.5 font-medium">
                  Archivada
                </Badge>
                <span className="text-[10px] text-muted-foreground font-mono">archived</span>
              </div>
              <p className="text-muted-foreground text-[11px] leading-relaxed">
                Para guardar ofertas antiguas o no prioritarias fuera de la vista principal sin borrarlas de la base de datos.
              </p>
            </div>
          </div>
        </div>

        {/* Flujo Visual */}
        <div className="p-3 rounded-lg border bg-primary/5 text-[11px] space-y-1.5">
          <div className="flex items-center gap-1.5 font-semibold text-primary">
            <Sparkles className="h-3.5 w-3.5" />
            <span>Flujo habitual de una oferta:</span>
          </div>
          <div className="flex flex-wrap items-center gap-1 text-[11px] text-muted-foreground">
            <span className="font-medium text-foreground">Portal</span>
            <ArrowRight className="h-3 w-3" />
            <span>Descubierta</span>
            <ArrowRight className="h-3 w-3" />
            <span>Filtros &amp; Ollama</span>
            <ArrowRight className="h-3 w-3" />
            <span>Evaluada / Notificada</span>
            <ArrowRight className="h-3 w-3" />
            <span>Postulada</span>
            <ArrowRight className="h-3 w-3" />
            <span className="text-emerald-400 font-semibold">Entrevista</span>
          </div>
        </div>
      </div>
    </Dialog>
  );
}
