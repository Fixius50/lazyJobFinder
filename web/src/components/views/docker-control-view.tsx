"use client";

import React, { useEffect, useState } from "react";
import { AlertTriangle, Terminal } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { LogConsole } from "@/components/ui/log-console";
import { InfoTooltip } from "@/components/ui/info-tooltip";
import { ServiceCard } from "@/components/features/services/service-card";
import { ServiceGlobalActions } from "@/components/features/services/service-global-actions";
import { ServicesStatusResponse, api } from "@/lib/api";

export function DockerControlView() {
  const [data, setData] = useState<ServicesStatusResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const fetchStatus = async () => {
    try {
      const res = await api.getServicesStatus();
      setData(res);
      setErrorMsg(null);
    } catch (err: any) {
      setErrorMsg(err.message || "Error conectando con el backend local.");
    } finally {
      setLoading(false);
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

  return (
    <div className="space-y-4 w-full">
      {/* Encabezado limpio y minimalista con tooltip de información (?) */}
      <div className="flex items-center gap-2 pb-2.5 border-b">
        <h2 className="text-base sm:text-lg font-bold tracking-tight">Control de Servicios y Logs</h2>
        <InfoTooltip content="Monitorización en vivo y ciclo de vida de los contenedores Docker Ollama y lazyJobFinder." />
      </div>

      {errorMsg && (
        <div className="p-2.5 rounded-lg bg-destructive/15 text-destructive border border-destructive/20 text-xs flex items-center gap-2 animate-in fade-in">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Tarjetas minimalistas de Contenedores con botón de estado integrado */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
        {/* Tarjeta Motor Ollama (Interactivo con toggle de estado) */}
        <ServiceCard
          id="ollama"
          title="Motor Ollama"
          tooltipInfo="Contenedor Docker lazyjob_ollama ejecutando el modelo LLM local (qwen2.5:3b) en CPU. Puerto http://localhost:11434"
          icon="cpu"
          service={ollama}
          actionLoading={actionLoading}
          onAction={handleAction}
          isInteractive={true}
        />

        {/* Tarjeta lazyJobFinder App (Indicador de estado del Backend y Bot) */}
        <ServiceCard
          id="lazyjobfinder"
          title="lazyJobFinder App"
          tooltipInfo="Contenedor Docker lazyjob_app ejecutando la API FastAPI y el bot de Telegram. Puerto http://localhost:8000"
          icon="server"
          service={appService}
          actionLoading={actionLoading}
          isInteractive={false}
        />
      </div>

      {/* Fila inferior a las dos tarjetas con los botones de acciones globales */}
      <ServiceGlobalActions
        actionLoading={actionLoading}
        loading={loading}
        onAction={handleAction}
        onRefresh={fetchStatus}
      />

      {/* Consola de Registro en Vivo con cabecera unificada y limpia */}
      <LogConsole />
    </div>
  );
}
