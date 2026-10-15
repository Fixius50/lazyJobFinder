"use client";

import React, { useState, useEffect } from "react";
import {
  Briefcase,
  Search,
  Activity,
  Settings,
  ShieldCheck,
  Play,
  RotateCw,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ApplicationsView } from "@/components/views/applications-view";
import { SearchCVView } from "@/components/views/search-cv-view";
import { DockerControlView } from "@/components/views/docker-control-view";
import { SettingsView } from "@/components/views/settings-view";
import { api } from "@/lib/api";

type TabKey = "applications" | "search" | "docker" | "settings";

export default function UnifiedDashboard() {
  const [activeTab, setActiveTab] = useState<TabKey>("applications");
  const [pipelineRunning, setPipelineRunning] = useState<boolean>(false);
  const [scanMessage, setScanMessage] = useState<string | null>(null);

  // Cargar tab desde la URL si existe (?tab=...)
  useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      const tabParam = params.get("tab") as TabKey;
      if (tabParam && ["applications", "search", "docker", "settings"].includes(tabParam)) {
        setActiveTab(tabParam);
      }
    }
  }, []);

  // Monitorización periódica del pipeline con aborto ante fallos
  useEffect(() => {
    let failedAttempts = 0;
    const checkPipeline = async () => {
      try {
        const pre = await api.getPreflight();
        setPipelineRunning(pre.pipeline.is_running);
        failedAttempts = 0;
      } catch (err) {
        failedAttempts += 1;
        console.warn(`[Pipeline Monitor] Fallo al consultar estado (${failedAttempts}/2):`, err);
        // Si hay 2 fallos consecutivos de red o socket, abortar inmediatamente cualquier animación de escaneo
        if (failedAttempts >= 2) {
          setPipelineRunning(false);
        }
      }
    };
    checkPipeline();
    const interval = setInterval(checkPipeline, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleTabChange = (tab: TabKey) => {
    setActiveTab(tab);
    if (typeof window !== "undefined") {
      const url = new URL(window.location.href);
      url.searchParams.set("tab", tab);
      window.history.replaceState({}, "", url.toString());
    }
  };

  const handleQuickScan = async () => {
    setScanMessage("Iniciando escaneo...");
    setPipelineRunning(true);
    try {
      const res = await api.triggerSearch();
      setScanMessage(res.message);
      setTimeout(() => setScanMessage(null), 4000);
    } catch (e: any) {
      console.error("[QuickScan] Error durante el escaneo:", e);
      alert(`Error al iniciar escaneo: ${e.message}`);
      setScanMessage(null);
      // Abortar animación inmediatamente para evitar que se quede pillado
      setPipelineRunning(false);
    }
  };

  const tabsConfig = [
    {
      key: "applications" as TabKey,
      label: "Candidaturas",
      icon: Briefcase,
      badge: "Ofertas",
    },
    {
      key: "search" as TabKey,
      label: "Búsqueda y CV",
      icon: Search,
    },
    {
      key: "docker" as TabKey,
      label: "Servicios y Logs",
      icon: Activity,
    },
    {
      key: "settings" as TabKey,
      label: "Configuración",
      icon: Settings,
    },
  ];

  return (
    <div className="flex flex-col min-h-[100dvh] w-full">
      {/* Barra de Navegación Superior Unificada (Sticky, Fluida y Relativa) */}
      <header className="sticky top-0 z-40 w-full border-b bg-background/80 backdrop-blur-md px-3 sm:px-6 lg:px-8">
        <div className="flex h-14 sm:h-16 items-center justify-between gap-2 max-w-7xl mx-auto">
          {/* Logo y Marca */}
          <div className="flex items-center gap-2.5 shrink-0">
            <div className="h-8 w-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center font-bold text-xs sm:text-sm shadow-sm ring-1 ring-primary/20">
              LJ
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-xs sm:text-sm tracking-tight text-foreground leading-none">
                  lazyJobFinder
                </span>
                <span className="hidden md:inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium text-emerald-400 ring-1 ring-inset ring-emerald-500/20">
                  <ShieldCheck className="h-3 w-3" /> 100% Local · 0 €
                </span>
              </div>
              <p className="hidden sm:block text-[10px] text-muted-foreground mt-0.5">
                Búsqueda, scoring IA y tailoring ATS sin intermediarios
              </p>
            </div>
          </div>

          {/* Selector de Pestañas Flotante Central (Sin transiciones lentas de página) */}
          <nav className="flex items-center gap-1 bg-muted/60 p-1 rounded-xl border max-w-full overflow-x-auto">
            {tabsConfig.map((t) => {
              const Icon = t.icon;
              const isActive = activeTab === t.key;
              return (
                <button
                  key={t.key}
                  type="button"
                  onClick={() => handleTabChange(t.key)}
                  className={`flex items-center gap-1.5 px-2.5 sm:px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all whitespace-nowrap ${
                    isActive
                      ? "bg-background text-foreground shadow-sm font-semibold ring-1 ring-border/50"
                      : "text-muted-foreground hover:text-foreground hover:bg-background/40"
                  }`}
                >
                  <Icon className={`h-3.5 w-3.5 shrink-0 ${isActive ? "text-primary" : "text-muted-foreground"}`} />
                  <span>{t.label}</span>
                </button>
              );
            })}
          </nav>

          {/* Acciones Rápidas del Header */}
          <div className="flex items-center gap-2 shrink-0">
            <Button
              size="sm"
              onClick={handleQuickScan}
              disabled={pipelineRunning}
              className="h-8 px-2.5 sm:px-3 text-xs flex items-center gap-1.5 shadow-sm"
            >
              {pipelineRunning ? (
                <>
                  <RotateCw className="h-3.5 w-3.5 animate-spin" />
                  <span className="hidden sm:inline">Escaneando...</span>
                </>
              ) : (
                <>
                  <Play className="h-3 w-3 fill-current" />
                  <span className="hidden sm:inline">Escanear Ahora</span>
                </>
              )}
            </Button>
          </div>
        </div>
      </header>

      {/* Mensaje de retroalimentación global */}
      {scanMessage && (
        <div className="bg-primary/10 border-b border-primary/20 py-1.5 px-4 text-center text-xs text-primary flex items-center justify-center gap-1.5 animate-in fade-in">
          <Sparkles className="h-3.5 w-3.5 shrink-0" />
          <span>{scanMessage}</span>
        </div>
      )}

      {/* Contenido Principal Fluido y 100% Relativo */}
      <main className="flex-1 w-full max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-6">
        <div className="w-full transition-opacity duration-200">
          {activeTab === "applications" && <ApplicationsView />}
          {activeTab === "search" && <SearchCVView />}
          {activeTab === "docker" && <DockerControlView />}
          {activeTab === "settings" && <SettingsView />}
        </div>
      </main>

      {/* Pie de Página Minimalista y Relativo */}
      <footer className="border-t py-3 px-4 text-center text-[11px] text-muted-foreground bg-card/30">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>lazyJobFinder · Arquitectura 100% soberana, local y privada</span>
          <span className="flex items-center gap-1 text-emerald-400">
            <ShieldCheck className="h-3.5 w-3.5" /> Procesamiento en RAM y SQLite local
          </span>
        </div>
      </footer>
    </div>
  );
}
