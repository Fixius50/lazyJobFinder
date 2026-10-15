"use client";

import React, { useEffect, useState } from "react";
import { Play, Square, RotateCw, CheckCircle2, AlertTriangle, XCircle, Clock, Server, Cpu } from "lucide-react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { LogConsole } from "@/components/ui/log-console";
import { ServicesStatusResponse, api } from "@/lib/api";

export default function ControlPage() {
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
    <div className="space-y-6">
      {/* Encabezado y Acciones Globales */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b">
        <div>
          <h2 className="text-xl font-bold tracking-tight">Control de Servicios Docker</h2>
          <p className="text-xs text-muted-foreground mt-1">
            Monitorización y ciclo de vida de los contenedores Ollama y lazyJobFinder.
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <Button
            size="sm"
            variant="default"
            onClick={() => handleAction("all", "start")}
            disabled={actionLoading !== null}
            className="flex items-center gap-1.5"
          >
            <Play className="h-3.5 w-3.5 fill-current" />
            Arrancar Todo
          </Button>

          <Button
            size="sm"
            variant="outline"
            onClick={() => handleAction("all", "stop")}
            disabled={actionLoading !== null}
            className="flex items-center gap-1.5 hover:text-amber-500"
          >
            <Square className="h-3.5 w-3.5 fill-current" />
            Detener Todo
          </Button>

          <Button
            size="sm"
            variant="ghost"
            onClick={() => handleAction("all", "restart")}
            disabled={actionLoading !== null}
            className="flex items-center gap-1.5"
          >
            <RotateCw className={`h-3.5 w-3.5 ${actionLoading?.includes("restart") ? "animate-spin" : ""}`} />
            Reiniciar
          </Button>
        </div>
      </div>

      {errorMsg && (
        <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-lg text-destructive text-xs flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Tarjetas de Estado de Servicios */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* Tarjeta Ollama */}
        <Card className="flex flex-col justify-between">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Cpu className="h-4 w-4 text-primary" />
                <CardTitle>Ollama IA</CardTitle>
              </div>
              {getStatusBadge(ollama?.status || "detenido")}
            </div>
            <CardDescription>Contenedor: lazyjob_ollama (Puerto 11434)</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="text-xs space-y-1 bg-muted/40 p-2.5 rounded-md font-mono">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Salud Docker:</span>
                <span className="font-medium text-foreground">{ollama?.health || "n/a"}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Contenedor ID:</span>
                <span className="text-foreground">{ollama?.id || "no asignado"}</span>
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
        <Card className="flex flex-col justify-between">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Server className="h-4 w-4 text-primary" />
                <CardTitle>lazyJobFinder App</CardTitle>
              </div>
              {getStatusBadge(appService?.status || "detenido")}
            </div>
            <CardDescription>Contenedor: lazyjob_app (Pipeline & Bot)</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="text-xs space-y-1 bg-muted/40 p-2.5 rounded-md font-mono">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Salud Docker:</span>
                <span className="font-medium text-foreground">{appService?.health || "n/a"}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Cerrojo Pipeline:</span>
                <span className={`font-medium ${data?.pipeline?.is_running ? "text-amber-500 font-bold" : "text-emerald-500"}`}>
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

        {/* Tarjeta Resumen Última Ejecución */}
        <Card className="flex flex-col justify-between md:col-span-2 lg:col-span-1">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle>Historial de Ejecución</CardTitle>
              <Badge variant={data?.pipeline?.has_run_today ? "success" : "secondary"}>
                {data?.pipeline?.has_run_today ? "Completado hoy" : "Pendiente hoy"}
              </Badge>
            </div>
            <CardDescription>Planificador diario APScheduler (08:30 AM)</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="text-xs space-y-1 bg-muted/40 p-2.5 rounded-md">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Último escaneo:</span>
                <span className="font-mono">{data?.pipeline?.last_run?.finished_at || "Sin registros"}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Ofertas nuevas:</span>
                <span className="font-mono font-semibold">{data?.pipeline?.last_run?.new_jobs ?? 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Relevantes (≥65):</span>
                <span className="font-mono font-semibold text-emerald-500">
                  {data?.pipeline?.last_run?.relevant_jobs ?? 0}
                </span>
              </div>
            </div>

            <div className="text-[11px] text-muted-foreground italic pt-2">
              * Para iniciar un escaneo inmediato, dirígete a la sección Búsqueda.
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Consola de Logs en Tiempo Real */}
      <div className="space-y-2">
        <h3 className="text-sm font-semibold tracking-tight text-foreground">
          Consola y Registros de Ejecución
        </h3>
        <LogConsole height="h-96" />
      </div>
    </div>
  );
}
