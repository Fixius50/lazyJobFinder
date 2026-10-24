"use client";

import React, { useEffect, useState } from "react";
import { Terminal, Cpu, Server, RefreshCw } from "lucide-react";
import { Dialog } from "@/components/ui/dialog";
import { LogConsole } from "@/components/ui/log-console";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ServicesStatusResponse, api } from "@/lib/api";

interface TerminalLogsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function TerminalLogsDialog({ open, onOpenChange }: TerminalLogsDialogProps) {
  const [data, setData] = useState<ServicesStatusResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  const fetchStatus = async () => {
    setLoading(true);
    try {
      const res = await api.getServicesStatus();
      setData(res);
    } catch {
      // Silencioso si falla
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open) {
      fetchStatus();
      const interval = setInterval(fetchStatus, 6000);
      return () => clearInterval(interval);
    }
  }, [open]);

  const ollama = data?.services?.ollama;
  const appService = data?.services?.lazyjobfinder;
  const isAppUp = appService?.status === "saludable" || appService?.raw_state === "running";
  const isOllamaUp = ollama?.status === "saludable" || ollama?.raw_state === "running";

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Terminal y Registros del Sistema"
      description="Consola interactiva con registros en tiempo real del pipeline de búsqueda, motor IA Ollama y contenedores"
      maxWidth="5xl"
    >
      <div className="space-y-4">
        {/* Barra superior compacta con estado de servicios Docker */}
        <div className="flex flex-wrap items-center justify-between gap-2 p-2.5 rounded-lg bg-muted/40 border text-xs">
          <div className="flex items-center gap-3">
            {/* Contenedor lazyJobFinder App */}
            <div className="flex items-center gap-1.5">
              <Server className="h-3.5 w-3.5 text-muted-foreground" />
              <span className="font-medium">App Backend:</span>
              <Badge
                variant="outline"
                className={`text-3xs py-0 px-1.5 ${
                  isAppUp
                    ? "border-emerald-500/30 text-emerald-400 bg-emerald-500/10"
                    : "border-zinc-700 text-zinc-400"
                }`}
              >
                {appService?.status || "Operativo"}
              </Badge>
            </div>

            {/* Contenedor Motor Ollama */}
            <div className="flex items-center gap-1.5">
              <Cpu className="h-3.5 w-3.5 text-muted-foreground" />
              <span className="font-medium">Motor Ollama:</span>
              <Badge
                variant="outline"
                className={`text-3xs py-0 px-1.5 ${
                  isOllamaUp
                    ? "border-emerald-500/30 text-emerald-400 bg-emerald-500/10"
                    : "border-rose-500/30 text-rose-400 bg-rose-500/10"
                }`}
              >
                {ollama?.status || "Operativo"}
              </Badge>
            </div>
          </div>

          <Button
            variant="ghost"
            size="sm"
            onClick={fetchStatus}
            disabled={loading}
            className="h-6 px-2 text-xs text-muted-foreground hover:text-foreground"
            title="Refrescar estado de contenedores"
          >
            <RefreshCw className={`h-3 w-3 mr-1 ${loading ? "animate-spin" : ""}`} />
            <span>Actualizar</span>
          </Button>
        </div>

        {/* Consola de Registros Interactiva */}
        <LogConsole height="h-[55vh]" />
      </div>
    </Dialog>
  );
}
