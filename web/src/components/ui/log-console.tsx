"use client";

import React, { useEffect, useRef, useState } from "react";
import { Terminal, RefreshCw, Trash2, ArrowDown, Wifi, WifiOff } from "lucide-react";
import { Button } from "./button";
import { Badge } from "./badge";
import { Tabs } from "./tabs";
import { SystemLogItem, api } from "@/lib/api";

interface LogConsoleProps {
  initialLogs?: SystemLogItem[];
  height?: string;
}

export function LogConsole({ initialLogs = [], height = "h-80" }: LogConsoleProps) {
  const [logs, setLogs] = useState<SystemLogItem[]>(initialLogs);
  const [activeTab, setActiveTab] = useState<string>("all");
  const [autoScroll, setAutoScroll] = useState<boolean>(true);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [containerRawLogs, setContainerRawLogs] = useState<string>("");
  const scrollRef = useRef<HTMLDivElement>(null);

  // Carga inicial y refresco manual
  const fetchLogs = async () => {
    setIsLoading(true);
    try {
      if (activeTab === "container_ollama") {
        const res = await api.getContainerLogs("ollama", 100);
        setContainerRawLogs(res.logs);
      } else if (activeTab === "container_app") {
        const res = await api.getContainerLogs("lazyjobfinder", 100);
        setContainerRawLogs(res.logs);
      } else {
        const sourceFilter = activeTab === "all" ? undefined : activeTab;
        const res = await api.getSystemLogs(150, undefined, sourceFilter);
        setLogs(res.reverse()); // Cronológico
      }
    } catch (e) {
      console.error("Error al cargar logs:", e);
    } finally {
      setIsLoading(false);
    }
  };

  // Conexión SSE para logs del sistema en tiempo real
  useEffect(() => {
    if (activeTab === "container_ollama" || activeTab === "container_app") {
      fetchLogs();
      return;
    }

    const sseUrl = `${api.getBaseUrl()}/system/logs/stream${activeTab !== "all" ? `?source=${activeTab}` : ""}`;
    const eventSource = new EventSource(sseUrl);

    eventSource.onopen = () => {
      setIsConnected(true);
    };

    eventSource.addEventListener("log", (event) => {
      try {
        const item: SystemLogItem = JSON.parse(event.data);
        setLogs((prev) => {
          if (prev.some((p) => p.id === item.id)) return prev;
          return [...prev, item];
        });
      } catch (err) {
        console.error("[SSE] Fallo parseando evento SSE:", err);
      }
    });

    eventSource.onerror = (err) => {
      console.warn("[SSE] EventSource desconectado o error de socket:", err);
      setIsConnected(false);
      eventSource.close();
    };

    return () => {
      eventSource.close();
      setIsConnected(false);
    };
  }, [activeTab]);

  // Auto-scroll hacia el final
  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, containerRawLogs, autoScroll]);

  const clearView = () => {
    setLogs([]);
    setContainerRawLogs("");
  };

  const getLevelColor = (level: string) => {
    switch (level.toUpperCase()) {
      case "CRITICAL":
      case "ERROR":
        return "text-red-400 font-bold";
      case "WARNING":
        return "text-amber-400";
      case "INFO":
      default:
        return "text-emerald-400";
    }
  };

  return (
    <div className="flex flex-col rounded-xl border border-zinc-800 bg-zinc-950 text-zinc-100 shadow-xl overflow-hidden font-mono text-xs">
      {/* Barra de cabecera de la consola */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-800 px-4 py-2 bg-zinc-900/80">
        <div className="flex items-center space-x-2">
          <Terminal className="h-4 w-4 text-zinc-400" />
          <span className="font-semibold text-zinc-200">Consola del Sistema</span>
          {isConnected ? (
            <Badge variant="outline" className="border-emerald-500/40 text-emerald-400 text-[10px] py-0 px-1.5 flex items-center gap-1">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
              SSE En vivo
            </Badge>
          ) : (
            <Badge variant="outline" className="border-zinc-700 text-zinc-400 text-[10px] py-0 px-1.5 flex items-center gap-1">
              <WifiOff className="h-3 w-3" /> Polling
            </Badge>
          )}
        </div>

        {/* Selector de canal de logs */}
        <div className="flex items-center space-x-1">
          <Tabs
            value={activeTab}
            onValueChange={setActiveTab}
            className="h-7 bg-zinc-800/80 text-[11px]"
            items={[
              { label: "Todo", value: "all" },
              { label: "Pipeline", value: "pipeline" },
              { label: "Docker App", value: "container_app" },
              { label: "Docker Ollama", value: "container_ollama" },
            ]}
          />

          <Button
            variant="ghost"
            size="sm"
            onClick={fetchLogs}
            disabled={isLoading}
            className="h-7 px-2 text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800"
            title="Refrescar logs manualmente"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? "animate-spin" : ""}`} />
          </Button>

          <Button
            variant="ghost"
            size="sm"
            onClick={() => setAutoScroll(!autoScroll)}
            className={`h-7 px-2 text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 ${
              autoScroll ? "text-primary font-bold" : ""
            }`}
            title="Auto-scroll automático"
          >
            <ArrowDown className="h-3.5 w-3.5" />
          </Button>

          <Button
            variant="ghost"
            size="sm"
            onClick={clearView}
            className="h-7 px-2 text-zinc-400 hover:text-red-400 hover:bg-zinc-800"
            title="Limpiar visualización"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      {/* Contenedor desplazable de logs */}
      <div
        ref={scrollRef}
        className={`${height} overflow-y-auto p-4 space-y-1.5 select-text leading-relaxed`}
      >
        {activeTab === "container_ollama" || activeTab === "container_app" ? (
          <pre className="whitespace-pre-wrap text-zinc-300 font-mono text-[11px]">
            {containerRawLogs || "Esperando registros del contenedor..."}
          </pre>
        ) : logs.length === 0 ? (
          <div className="text-zinc-500 italic py-6 text-center">
            No hay registros disponibles en este canal aún.
          </div>
        ) : (
          logs.map((log) => (
            <div key={log.id} className="flex items-start space-x-2 text-[11px] hover:bg-zinc-900/40 px-1 py-0.5 rounded">
              <span className="text-zinc-500 select-none shrink-0 font-normal">{log.timestamp}</span>
              <span className={`shrink-0 uppercase px-1 rounded text-[10px] ${getLevelColor(log.level)}`}>
                [{log.level}]
              </span>
              <span className="text-zinc-400 shrink-0 select-none">[{log.source}]</span>
              <span className="text-zinc-200 break-words">{log.message}</span>
              {log.details && <span className="text-zinc-500 italic">({log.details})</span>}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
