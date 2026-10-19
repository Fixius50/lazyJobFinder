"use client";

import React, { useEffect, useState } from "react";
import { Play, Square, RotateCw, Cpu, Server } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ServicesStatusResponse, api } from "@/lib/api";

export function ServiceToolbarActions() {
  const [data, setData] = useState<ServicesStatusResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

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

  const handleAction = async (service: string, action: "start" | "stop") => {
    const key = `${service}-${action}`;
    setActionLoading(key);
    try {
      await api.sendServiceAction(service, action);
      await fetchStatus();
    } catch (err: any) {
      alert(`Error en acción Docker: ${err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

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

  return (
    <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
      {/* 1. Indicador y control de Ollama ("arriba del todo") */}
      <div className="flex items-center gap-1 px-2 py-1 rounded-lg border bg-card/60 text-xs">
        <Cpu className="h-3.5 w-3.5 text-primary shrink-0" />
        <span className="font-medium text-[11px] hidden md:inline">Ollama:</span>
        <span
          className={`h-2 w-2 rounded-full shrink-0 ${
            isOllamaRunning ? "bg-emerald-400 animate-pulse" : "bg-rose-400"
          }`}
          title={isOllamaRunning ? "Ollama en ejecución" : "Ollama detenido"}
        />
        <Button
          size="sm"
          variant="ghost"
          onClick={() => handleAction("ollama", isOllamaRunning ? "stop" : "start")}
          disabled={actionLoading !== null}
          className="h-6 px-1.5 text-[10px] text-muted-foreground hover:text-foreground"
        >
          {actionLoading === "ollama-stop" || actionLoading === "ollama-start" ? (
            <RotateCw className="h-2.5 w-2.5 animate-spin" />
          ) : isOllamaRunning ? (
            "Detener"
          ) : (
            "Iniciar"
          )}
        </Button>
      </div>

      {/* 2. Indicador de la App Backend ("arriba del todo") */}
      <div className="flex items-center gap-1 px-2 py-1 rounded-lg border bg-card/60 text-xs">
        <Server className="h-3.5 w-3.5 text-sky-400 shrink-0" />
        <span className="font-medium text-[11px] hidden md:inline">App:</span>
        <span
          className={`h-2 w-2 rounded-full shrink-0 ${
            isAppRunning ? "bg-emerald-400" : "bg-rose-400"
          }`}
          title={isAppRunning ? "lazyJobFinder App en ejecución" : "App detenida"}
        />
        <span className="text-[10px] text-muted-foreground font-mono">8000</span>
      </div>

      {/* 3. Botones de Acciones Globales */}
      <Button
        size="sm"
        variant="default"
        onClick={() => handleAction("all", "start")}
        disabled={actionLoading !== null}
        className="h-8 px-2.5 text-xs flex items-center gap-1.5 shadow-sm"
        title="Arrancar todos los contenedores Docker locales"
      >
        {actionLoading === "all-start" ? (
          <RotateCw className="h-3 w-3 animate-spin" />
        ) : (
          <Play className="h-3 w-3 fill-current" />
        )}
        <span className="hidden sm:inline">Arrancar Todo</span>
      </Button>

      <Button
        size="sm"
        variant="outline"
        onClick={() => handleAction("all", "stop")}
        disabled={actionLoading !== null}
        className="h-8 px-2.5 text-xs flex items-center gap-1.5"
        title="Detener contenedores locales"
      >
        {actionLoading === "all-stop" ? (
          <RotateCw className="h-3 w-3 animate-spin" />
        ) : (
          <Square className="h-3 w-3" />
        )}
        <span className="hidden sm:inline">Detener Todo</span>
      </Button>
    </div>
  );
}
