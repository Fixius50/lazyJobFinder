"use client";

import React from "react";
import { Cpu, Server, Play, Square, RotateCw } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { InfoTooltip } from "@/components/ui/info-tooltip";
import { ServiceInfo } from "@/types";

interface ServiceCardProps {
  id: "ollama" | "lazyjobfinder";
  title: string;
  tooltipInfo: string;
  icon: "cpu" | "server";
  service?: ServiceInfo;
  actionLoading?: string | null;
  onAction?: (service: string, action: "start" | "stop") => void;
  isInteractive?: boolean;
}

export function ServiceCard({
  id,
  title,
  tooltipInfo,
  icon,
  service,
  actionLoading,
  onAction,
  isInteractive = true,
}: ServiceCardProps) {
  const isHealthy = service?.status === "saludable";
  const isStarting = service?.status === "arrancando";
  const isError = service?.status === "error";
  const isStopped = !isHealthy && !isStarting && !isError;

  const currentLoading = actionLoading?.startsWith(id);

  // Determinar estilos visuales donde el fondo del botón/indicador cubre con el color de su estado
  const getStateButtonStyles = () => {
    if (isHealthy) {
      return "bg-emerald-500/20 text-emerald-400 border-emerald-500/40 hover:bg-emerald-500/30 shadow-sm shadow-emerald-950/20";
    }
    if (isStarting) {
      return "bg-amber-500/20 text-amber-300 border-amber-500/40 hover:bg-amber-500/30 animate-pulse";
    }
    if (isError) {
      return "bg-rose-500/20 text-rose-400 border-rose-500/40 hover:bg-rose-500/30";
    }
    // Detenido
    return "bg-muted/70 text-muted-foreground border-border/80 hover:bg-muted hover:text-foreground";
  };

  const getStatusLabel = () => {
    if (currentLoading) return "Procesando...";
    if (isHealthy) return isInteractive ? "En Ejecución · Detener" : "En Ejecución";
    if (isStarting) return "Iniciando servicio...";
    if (isError) return "Error en servicio";
    return isInteractive ? "Detenido · Arrancar" : "Detenido";
  };

  const handleToggle = () => {
    if (!isInteractive || !onAction || currentLoading) return;
    if (isHealthy) {
      onAction(id, "stop");
    } else {
      onAction(id, "start");
    }
  };

  return (
    <Card className="flex flex-col justify-between border bg-card/60 backdrop-blur-sm shadow-sm transition-all hover:border-border/80">
      <CardHeader className="pb-2 pt-3.5 px-4">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <div className={`p-1.5 rounded-lg border ${isHealthy ? "bg-primary/10 text-primary border-primary/20" : "bg-muted text-muted-foreground border-border/50"}`}>
              {icon === "cpu" ? <Cpu className="h-4 w-4" /> : <Server className="h-4 w-4" />}
            </div>
            <div className="flex items-center gap-1.5">
              <CardTitle className="text-sm font-semibold tracking-tight">{title}</CardTitle>
              <InfoTooltip content={tooltipInfo} />
            </div>
          </div>

          {/* Indicador de pulso de estado sutil */}
          <span
            className={`h-2 w-2 rounded-full transition-colors ${
              isHealthy
                ? "bg-emerald-400 shadow-sm shadow-emerald-400/80 animate-pulse"
                : isStarting
                ? "bg-amber-400 animate-ping"
                : isError
                ? "bg-rose-500"
                : "bg-muted-foreground/40"
            }`}
          />
        </div>
      </CardHeader>

      <CardContent className="pt-2 pb-3.5 px-4 space-y-3">
        {/* Botón interactivo con el fondo del color del estado */}
        <button
          type="button"
          disabled={!isInteractive || currentLoading}
          onClick={handleToggle}
          title={isInteractive ? (isHealthy ? "Clic para detener" : "Clic para arrancar") : undefined}
          className={`w-full py-2 px-3 rounded-lg border text-xs font-medium flex items-center justify-center gap-2 transition-all ${getStateButtonStyles()} ${
            !isInteractive ? "cursor-default" : "cursor-pointer active:scale-[0.98]"
          }`}
        >
          {currentLoading ? (
            <RotateCw className="h-3.5 w-3.5 animate-spin" />
          ) : isHealthy ? (
            <Square className="h-3 w-3 fill-current opacity-80" />
          ) : isStarting ? (
            <RotateCw className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Play className="h-3 w-3 fill-current opacity-80" />
          )}
          <span>{getStatusLabel()}</span>
        </button>
      </CardContent>
    </Card>
  );
}
