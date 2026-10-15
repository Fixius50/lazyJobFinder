"use client";

import React, { useEffect, useState } from "react";
import { Play, Square, RotateCw, CheckCircle2, AlertTriangle, XCircle, Clock, Server, Cpu, RefreshCw, Terminal } from "lucide-react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { LogConsole } from "@/components/ui/log-console";
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

  const handleAction = async (service: string, action: "start" | "stop" | "restart") => {
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

  const getStatusBadge = (statusStr: string) => {
    switch (statusStr?.toLowerCase()) {
      case "saludable":
        return (
          <Badge variant="success" className="flex items-center gap-1">
            <CheckCircle2 className="h-3 w-3" /> Saludable
          </Badge>
        );
      case "arrancando":
        return (
          <Badge variant="warning" className="flex items-center gap-1">
            <Clock className="h-3 w-3 animate-spin" /> Arrancando
          </Badge>
        );
      case "error":
        return (
          <Badge variant="destructive" className="flex items-center gap-1">
            <XCircle className="h-3 w-3" /> Error
          </Badge>
        );
      case "detenido":
      default:
        return (
          <Badge variant="secondary" className="flex items-center gap-1">
            <Square className="h-2.5 w-2.5" /> Detenido
          </Badge>
        );
    }
  };

  const ollama = data?.services?.ollama;
  const appService = data?.services?.lazyjobfinder;

  return (
    <div className="space-y-4 sm:space-y-6 w-full">
      {/* Encabezado fluido */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b">
        <div>
          <h2 className="text-lg sm:text-xl font-bold tracking-tight">Control de Servicios y Logs en Tiempo Real</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Monitorización en vivo y ciclo de vida de los contenedores Docker Ollama y lazyJobFinder.
          </p>
        </div>

        <div className="flex items-center space-x-2 self-start sm:self-auto">
          <Button
            size="sm"
            variant="default"
            onClick={() => handleAction("all", "start")}
            disabled={actionLoading !== null}
            className="flex items-center gap-1.5 h-8 text-xs"
          >
            <Play className="h-3.5 w-3.5 fill-current" />
            Arrancar Todo
          </Button>

          <Button
            size="sm"
            variant="outline"
            onClick={() => handleAction("all", "stop")}
            disabled={actionLoading !== null}
            className="flex items-center gap-1.5 h-8 text-xs"
          >
            <Square className="h-3.5 w-3.5" />
            Detener Todo
          </Button>

          <Button
            size="sm"
            variant="ghost"
            onClick={fetchStatus}
            disabled={loading}
            className="h-8 px-2"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          </Button>
        </div>
      </div>

      {errorMsg && (
        <div className="p-3 rounded-lg bg-destructive/15 text-destructive border border-destructive/20 text-xs flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Grid relativo de Contenedores */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Tarjeta Ollama */}
        <Card className="flex flex-col justify-between border bg-card/80 backdrop-blur-sm shadow-sm">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Cpu className="h-4 w-4 text-primary" />
                <CardTitle className="text-sm">Motor Ollama Local</CardTitle>
              </div>
              {getStatusBadge(ollama?.status || "detenido")}
            </div>
            <CardDescription className="text-xs">
              Contenedor: lazyjob_ollama (Inferencia Q4_K_M en CPU)
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="text-xs space-y-1.5 bg-muted/40 p-3 rounded-lg font-mono border">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Salud Docker:</span>
                <span className="font-medium text-foreground">{ollama?.health || "n/a"}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Puerto:</span>
                <span className="text-foreground">http://localhost:11434</span>
              </div>
            </div>

            <div className="flex items-center gap-2 pt-1 border-t">
              <Button
                size="sm"
                variant="outline"
                className="w-full text-xs h-8"
                onClick={() => handleAction("ollama", "start")}
                disabled={actionLoading !== null || ollama?.status === "saludable"}
              >
                Arrancar
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="w-full text-xs h-8"
                onClick={() => handleAction("ollama", "stop")}
                disabled={actionLoading !== null || ollama?.status === "detenido"}
              >
                Detener
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="px-2 h-8"
                onClick={() => handleAction("ollama", "restart")}
                disabled={actionLoading !== null}
                title="Reiniciar contenedor Ollama"
              >
                <RotateCw className="h-3.5 w-3.5" />
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Tarjeta lazyJobFinder App */}
        <Card className="flex flex-col justify-between border bg-card/80 backdrop-blur-sm shadow-sm">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Server className="h-4 w-4 text-primary" />
                <CardTitle className="text-sm">lazyJobFinder App</CardTitle>
              </div>
              {getStatusBadge(appService?.status || "detenido")}
            </div>
            <CardDescription className="text-xs">
              Contenedor: lazyjob_app (Backend FastAPI & Bot Telegram)
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="text-xs space-y-1.5 bg-muted/40 p-3 rounded-lg font-mono border">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Salud Docker:</span>
                <span className="font-medium text-foreground">{appService?.health || "n/a"}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Cerrojo Pipeline:</span>
                <span className={`font-medium ${data?.pipeline?.is_running ? "text-amber-400 font-bold" : "text-emerald-400"}`}>
                  {data?.pipeline?.is_running ? "En ejecución activa" : "Inactivo (disponible)"}
                </span>
              </div>
            </div>

            <div className="flex items-center gap-2 pt-1 border-t">
              <Button
                size="sm"
                variant="outline"
                className="w-full text-xs h-8"
                onClick={() => handleAction("lazyjobfinder", "start")}
                disabled={actionLoading !== null || appService?.status === "saludable"}
              >
                Arrancar
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="w-full text-xs h-8"
                onClick={() => handleAction("lazyjobfinder", "stop")}
                disabled={actionLoading !== null || appService?.status === "detenido"}
              >
                Detener
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="px-2 h-8"
                onClick={() => handleAction("lazyjobfinder", "restart")}
                disabled={actionLoading !== null}
                title="Reiniciar contenedor App"
              >
                <RotateCw className="h-3.5 w-3.5" />
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Consola de Logs con CSS Relativo y fluidez */}
      <Card className="border bg-card/80 backdrop-blur-sm shadow-sm overflow-hidden">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <Terminal className="h-4 w-4 text-primary" />
            Consola de Registro en Vivo (Server-Sent Events)
          </CardTitle>
          <CardDescription className="text-xs">
            Transmisión continua de eventos del pipeline, evaluador Ollama y bot sin recargar la página.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-3 sm:p-4">
          <LogConsole />
        </CardContent>
      </Card>
    </div>
  );
}
