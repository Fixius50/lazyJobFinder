"use client";

import React, { useState } from "react";
import useSWR from "swr";
import { Play, Square, RotateCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ServicesStatusResponse, api } from "@/lib/api";
import { toast } from "sonner";

export function ServiceToolbarActions() {
  const [actionLoading, setActionLoading] = useState<"start" | "stop" | null>(null);

  const { data, mutate } = useSWR<ServicesStatusResponse>(
    "/system/status",
    api.getServicesStatus,
    {
      refreshInterval: 4000,
      revalidateOnFocus: true,
    }
  );

  const ollama = data?.services?.ollama;
  const appService = data?.services?.lazyjobfinder;

  const isOllamaRunning =
    ollama?.status === "saludable" ||
    ollama?.status === "arrancando" ||
    ollama?.raw_state === "running";
  const isAppRunning =
    appService?.status === "saludable" ||
    appService?.status === "arrancando" ||
    appService?.raw_state === "running";

  // Se considera activo si los contenedores están arriba
  const isRunning = isOllamaRunning || isAppRunning;

  const handleToggle = async () => {
    const action = isRunning ? "stop" : "start";
    setActionLoading(action);
    try {
      await api.sendServiceAction("all", action);
      await mutate();
      toast.success(action === "stop" ? "Servicios detenidos correctamente." : "Servicios iniciados.");
    } catch (err: any) {
      toast.error(`Error al ${action === "stop" ? "detener" : "iniciar"} servicios: ${err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <Button
      size="sm"
      onClick={handleToggle}
      disabled={actionLoading !== null}
      className={`h-8 px-3 text-xs flex items-center gap-1.5 font-medium transition-colors shadow-xs ${
        isRunning
          ? "bg-emerald-600 hover:bg-emerald-700 text-white border-0"
          : "bg-primary hover:bg-primary/90 text-primary-foreground border-0"
      }`}
      title={
        isRunning
          ? "Motor Ollama activo. Pulsa para detener los servicios de fondo (la web sigue accesible; usa start.bat para apagar todo)."
          : "Servicios de fondo detenidos. Pulsa para arrancar el motor Ollama."
      }
    >
      {actionLoading === "stop" ? (
        <>
          <RotateCw className="h-3 w-3 animate-spin" />
          <span>Deteniendo...</span>
        </>
      ) : actionLoading === "start" ? (
        <>
          <RotateCw className="h-3 w-3 animate-spin" />
          <span>Arrancando...</span>
        </>
      ) : isRunning ? (
        <>
          <Square className="h-3 w-3 fill-current" />
          <span>Detener Servicios</span>
        </>
      ) : (
        <>
          <Play className="h-3 w-3 fill-current" />
          <span>Arrancar Servicios</span>
        </>
      )}
    </Button>
  );
}
