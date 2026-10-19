"use client";

import React, { useEffect, useState } from "react";
import { Play, Square, RotateCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ServicesStatusResponse, api } from "@/lib/api";

export function ServiceToolbarActions() {
  const [data, setData] = useState<ServicesStatusResponse | null>(null);
  const [actionLoading, setActionLoading] = useState<"start" | "stop" | null>(null);

  const fetchStatus = async () => {
    try {
      const res = await api.getServicesStatus();
      setData(res);
    } catch (err: any) {
      console.warn("[ServiceToolbar] Error consultando servicios:", err);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 4000);
    return () => clearInterval(interval);
  }, []);

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
      await fetchStatus();
    } catch (err: any) {
      alert(`Error al ${action === "stop" ? "detener" : "iniciar"} servicios: ${err.message}`);
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
          ? "Servicios activos. Pulsa para detener todos los contenedores."
          : "Servicios detenidos. Pulsa para arrancar todos los contenedores."
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
          <span>Detener Todo</span>
        </>
      ) : (
        <>
          <Play className="h-3 w-3 fill-current" />
          <span>Arrancar Todo</span>
        </>
      )}
    </Button>
  );
}
