"use client";

import React from "react";
import { Play, Square, RotateCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { InfoTooltip } from "@/components/ui/info-tooltip";

interface ServiceGlobalActionsProps {
  actionLoading: string | null;
  loading: boolean;
  onAction: (service: string, action: "start" | "stop") => void;
  onRefresh: () => void;
}

export function ServiceGlobalActions({
  actionLoading,
  loading,
  onAction,
  onRefresh,
}: ServiceGlobalActionsProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 p-2.5 rounded-xl border bg-muted/30">
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <span className="font-medium text-foreground">Acciones Globales</span>
        <InfoTooltip content="Inicia o detiene los contenedores Docker locales del sistema (Ollama y servicios de fondo)." />
      </div>

      <div className="flex items-center gap-2">
        <Button
          size="sm"
          variant="default"
          onClick={() => onAction("all", "start")}
          disabled={actionLoading !== null}
          className="h-8 px-3 text-xs flex items-center gap-1.5 shadow-sm"
        >
          {actionLoading === "all-start" ? (
            <RotateCw className="h-3 w-3 animate-spin" />
          ) : (
            <Play className="h-3 w-3 fill-current" />
          )}
          <span>{actionLoading === "all-start" ? "Arrancando..." : "Arrancar Todo"}</span>
        </Button>

        <Button
          size="sm"
          variant="outline"
          onClick={() => onAction("all", "stop")}
          disabled={actionLoading !== null}
          className="h-8 px-3 text-xs flex items-center gap-1.5"
        >
          {actionLoading === "all-stop" ? (
            <RotateCw className="h-3 w-3 animate-spin" />
          ) : (
            <Square className="h-3 w-3" />
          )}
          <span>{actionLoading === "all-stop" ? "Deteniendo..." : "Detener Todo"}</span>
        </Button>

        <Button
          size="sm"
          variant="ghost"
          onClick={onRefresh}
          disabled={loading}
          className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground"
          title="Refrescar estado de los servicios"
        >
          <RotateCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
        </Button>
      </div>
    </div>
  );
}
