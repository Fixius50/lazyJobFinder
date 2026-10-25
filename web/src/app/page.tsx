"use client";

import React, { useState, useEffect } from "react";
import {
  Cpu,
  Database,
  Bell,
  Terminal,
  Info,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApplicationsView } from "@/components/views/applications-view";
import { TerminalLogsDialog } from "@/components/features/terminal/terminal-logs-dialog";
import { NotificationChannelsDialog } from "@/components/features/notifications/notification-channels-dialog";
import { StatusGuideDialog } from "@/components/features/jobs/status-guide-dialog";
import { PreflightResponse, api } from "@/lib/api";

export default function UnifiedDashboard() {
  const [pipelineRunning, setPipelineRunning] = useState<boolean>(false);
  const [preflight, setPreflight] = useState<PreflightResponse | null>(null);
  const [terminalOpen, setTerminalOpen] = useState<boolean>(false);
  const [notificationsOpen, setNotificationsOpen] = useState<boolean>(false);
  const [statusGuideOpen, setStatusGuideOpen] = useState<boolean>(false);

  // Monitorización periódica del pipeline y preflight con detección de caídas
  useEffect(() => {
    let failedAttempts = 0;
    const checkPipeline = async () => {
      try {
        const pre = await api.getPreflight();
        setPreflight(pre);
        setPipelineRunning(pre.pipeline.is_running);
        failedAttempts = 0;
      } catch (err) {
        failedAttempts += 1;
        console.warn(`[Pipeline Monitor] Fallo al consultar estado (${failedAttempts}/2):`, err);
        if (failedAttempts >= 2) {
          setPipelineRunning(false);
        }
      }
    };
    checkPipeline();
    const interval = setInterval(checkPipeline, 5000);
    return () => clearInterval(interval);
  }, []);

  // Apagado instantáneo al cerrar la pestaña o el navegador
  useEffect(() => {
    const handleBeforeUnload = () => {
      try {
        if (navigator.sendBeacon) {
          navigator.sendBeacon("/api/system/shutdown");
        } else {
          fetch("/api/system/shutdown", { method: "POST", keepalive: true });
        }
      } catch {
        // Ignorar si el navegador ya ha cancelado la red
      }
    };

    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
    };
  }, []);

  return (
    <div className="flex flex-col min-h-[100dvh] w-full">
      {/* Barra de Navegación Superior Unificada */}
      <header className="sticky top-0 z-40 w-full border-b bg-background/80 backdrop-blur-md px-4 sm:px-[3vw] lg:px-[5vw]">
        <div className="flex h-14 sm:h-16 items-center justify-between gap-3 w-full">
          {/* Logo y Marca */}
          <div className="flex items-center gap-2.5 shrink-0">
            <div className="h-8 w-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center font-bold text-xs sm:text-sm shadow-sm ring-1 ring-primary/20">
              LJ
            </div>
            <span className="font-bold text-sm tracking-tight text-foreground leading-none">
              lazyJobFinder
            </span>
          </div>

          {/* Acciones del Header: Diagnóstico, Terminal, Notificaciones y Guía */}
          <div className="flex items-center gap-2.5 shrink-0">
            {/* Indicadores de Diagnóstico: Motor Ollama y SQLite WAL */}
            <div className="hidden lg:flex items-center gap-2">
              {/* Motor Ollama */}
              <div
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-2xs font-medium border transition-colors ${
                  preflight?.ollama?.healthy
                    ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                    : "bg-rose-500/10 text-rose-400 border-rose-500/20"
                }`}
                title={
                  preflight?.ollama?.healthy
                    ? `Motor Ollama Operativo: ${preflight.ollama.models?.join(", ") || "qwen2.5:3b-instruct"}`
                    : `Motor Ollama Desconectado (${preflight?.ollama?.error || "Comprobar servicio"})`
                }
              >
                <Cpu className="h-3 w-3" />
                <span>Ollama: {preflight?.ollama?.healthy ? "Operativo" : "Desconectado"}</span>
                <span
                  className={`h-1.5 w-1.5 rounded-full ${
                    preflight?.ollama?.healthy ? "bg-emerald-400 animate-pulse" : "bg-rose-400"
                  }`}
                />
              </div>

              {/* SQLite WAL */}
              <div
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-2xs font-medium border transition-colors ${
                  preflight?.database?.healthy
                    ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                    : "bg-rose-500/10 text-rose-400 border-rose-500/20"
                }`}
                title={
                  preflight?.database?.healthy
                    ? "Base de datos SQLite en modo WAL conectada y operativa"
                    : `Error SQLite: ${preflight?.database?.error || "Comprobar volumen"}`
                }
              >
                <Database className="h-3 w-3" />
                <span>SQLite WAL: {preflight?.database?.healthy ? "Conectada" : "Error"}</span>
                <span
                  className={`h-1.5 w-1.5 rounded-full ${
                    preflight?.database?.healthy ? "bg-emerald-400" : "bg-rose-400"
                  }`}
                />
              </div>
            </div>

            {/* Botón de Terminal / Consola de Registros en Modal */}
            <Button
              size="sm"
              variant="outline"
              onClick={() => setTerminalOpen(true)}
              className="h-8 px-2 sm:px-2.5 text-xs flex items-center gap-1.5 shadow-sm"
              title="Abrir Terminal y Registros del Pipeline en Vivo"
            >
              <Terminal className="h-3.5 w-3.5 text-primary" />
              <span className="hidden sm:inline">Terminal</span>
            </Button>

            {/* Botón de Campana para Canales de Notificación */}
            <Button
              size="sm"
              variant="outline"
              onClick={() => setNotificationsOpen(true)}
              className="h-8 px-2 sm:px-2.5 text-xs flex items-center gap-1.5 shadow-sm relative"
              title="Configurar Canales de Notificación (Telegram e Interfaz)"
            >
              <Bell className="h-3.5 w-3.5 text-primary" />
              <span className="hidden sm:inline">Notificaciones</span>
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
            </Button>

            {/* Botón de Información ("i") para Guía de Estados */}
            <Button
              size="sm"
              variant="outline"
              onClick={() => setStatusGuideOpen(true)}
              className="h-8 px-2 sm:px-2.5 text-xs flex items-center gap-1 shadow-sm"
              title="Guía de Estados y Etiquetas de las Ofertas"
            >
              <Info className="h-3.5 w-3.5 text-primary" />
              <span className="hidden sm:inline">Guía</span>
            </Button>
          </div>
        </div>
      </header>

      {/* Modal Desplegable de Terminal y Logs */}
      <TerminalLogsDialog
        open={terminalOpen}
        onOpenChange={setTerminalOpen}
      />

      {/* Modal Desplegable de Canales de Notificación */}
      <NotificationChannelsDialog
        open={notificationsOpen}
        onOpenChange={setNotificationsOpen}
      />

      {/* Modal Desplegable de Guía de Estados */}
      <StatusGuideDialog
        open={statusGuideOpen}
        onOpenChange={setStatusGuideOpen}
      />

      {/* Contenido Principal: Exclusivamente Vista de Candidaturas */}
      <main className="flex-1 w-full px-4 sm:px-[3vw] lg:px-[5vw] py-4 sm:py-6">
        <ApplicationsView />
      </main>
    </div>
  );
}
