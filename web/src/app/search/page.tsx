"use client";

import React, { useEffect, useState, useRef } from "react";
import { Upload, FileText, CheckCircle2, AlertCircle, Play, ShieldAlert, Cpu, Database, RefreshCw, FileCheck } from "lucide-react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select } from "@/components/ui/select";
import { LogConsole } from "@/components/ui/log-console";
import { ActiveCVInfo, PreflightResponse, api } from "@/lib/api";

export default function SearchAndCVPage() {
  const [activeCV, setActiveCV] = useState<ActiveCVInfo | null>(null);
  const [cvList, setCvList] = useState<any[]>([]);
  const [preflight, setPreflight] = useState<PreflightResponse | null>(null);
  const [isPreflightLoading, setIsPreflightLoading] = useState<boolean>(true);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadMessage, setUploadMessage] = useState<{ text: string; error: boolean } | null>(null);
  const [isSearchRunning, setIsSearchRunning] = useState<boolean>(false);
  const [searchFeedback, setSearchFeedback] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadData = async () => {
    try {
      const [cv, list, pre] = await Promise.all([
        api.getActiveCV(),
        api.listUploadedCVs(),
        api.getPreflight(),
      ]);
      setActiveCV(cv);
      setCvList(list);
      setPreflight(pre);
      setIsSearchRunning(pre.pipeline.is_running);
    } catch (e: any) {
      console.error("Error cargando datos de búsqueda y CV:", e);
    } finally {
      setIsPreflightLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(async () => {
      try {
        const pre = await api.getPreflight();
        setPreflight(pre);
        setIsSearchRunning(pre.pipeline.is_running);
      } catch {}
    }, 4000);
    return () => clearInterval(interval);
  }, []);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validación de tipo de archivo
    const validExtensions = [".pdf", ".md", ".txt"];
    const ext = file.name.substring(file.name.lastIndexOf(".")).toLowerCase();
    if (!validExtensions.includes(ext)) {
      setUploadMessage({
        text: `Formato inválido (${ext}). Formatos permitidos: PDF, Markdown (.md) y Texto (.txt).`,
        error: true,
      });
      return;
    }

    // Validación de tamaño (5 MB)
    if (file.size > 5 * 1024 * 1024) {
      setUploadMessage({
        text: `El archivo supera los 5 MB permitidos (${(file.size / (1024 * 1024)).toFixed(2)} MB).`,
        error: true,
      });
      return;
    }

    setIsUploading(true);
    setUploadMessage(null);

    try {
      const res = await api.uploadCV(file);
      setUploadMessage({ text: res.message || "Archivo subido correctamente.", error: false });
      await loadData();
    } catch (err: any) {
      setUploadMessage({ text: err.message || "Error al subir el archivo.", error: true });
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleSelectCV = async (filename: string) => {
    try {
      const res = await api.selectActiveCV(filename);
      setActiveCV(res.active_info);
    } catch (err: any) {
      alert(`Error seleccionando CV: ${err.message}`);
    }
  };

  const handleTriggerSearch = async () => {
    setSearchFeedback(null);
    try {
      const res = await api.triggerSearch();
      setSearchFeedback(res.message);
      setIsSearchRunning(true);
      await loadData();
    } catch (err: any) {
      setSearchFeedback(`Error: ${err.message}`);
    }
  };

  return (
    <div className="space-y-6">
      {/* Encabezado */}
      <div className="pb-2 border-b">
        <h2 className="text-xl font-bold tracking-tight">Gestión de CV y Búsqueda Manual</h2>
        <p className="text-xs text-muted-foreground mt-1">
          Carga segura de currículum local y lanzamiento controlado del pipeline de ofertas.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Columna Izquierda: Subida y CV Activo */}
        <div className="space-y-6 lg:col-span-1">
          {/* Tarjeta de CV Activo */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm flex items-center gap-2">
                  <FileCheck className="h-4 w-4 text-primary" />
                  CV Activo para Evaluación
                </CardTitle>
                <Badge variant={activeCV?.is_default ? "outline" : "secondary"}>
                  {activeCV?.type === "canonical" ? "Canónico" : "Personalizado"}
                </Badge>
              </div>
              <CardDescription>Referencia documental utilizada para contrastar afinidad</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="bg-muted/40 p-3 rounded-md text-xs space-y-1.5 font-mono">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Archivo:</span>
                  <span className="font-semibold text-foreground truncate max-w-[180px]">
                    {activeCV?.filename || "cv_base.md"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Ruta:</span>
                  <span className="text-muted-foreground truncate max-w-[180px]">{activeCV?.path}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Tamaño:</span>
                  <span>{activeCV?.size_bytes ? `${(activeCV.size_bytes / 1024).toFixed(1)} KB` : "0 KB"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Modificado:</span>
                  <span>{activeCV?.modified_at || "n/a"}</span>
                </div>
              </div>

              {/* Selector de CV */}
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-foreground">Cambiar CV Activo:</label>
                <Select
                  value={activeCV?.is_default ? "default" : activeCV?.filename}
                  onChange={(e) => handleSelectCV(e.target.value)}
                  className="text-xs"
                >
                  <option value="default">cv_base.md (Perfil Base Canónico)</option>
                  {cvList
                    .filter((c) => !c.is_default)
                    .map((c) => (
                      <option key={c.filename} value={c.filename}>
                        {c.filename}
                      </option>
                    ))}
                </Select>
              </div>
            </CardContent>
          </Card>

          {/* Tarjeta de Subida Segura de CV */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm flex items-center gap-2">
                <Upload className="h-4 w-4 text-primary" />
                Subir Nuevo CV
              </CardTitle>
              <CardDescription>
                Admite PDF, Markdown (.md) y Texto (.txt) hasta 5 MB.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.md,.txt"
                onChange={handleFileUpload}
                className="hidden"
                id="cv-file-input"
              />

              <div
                onClick={() => fileInputRef.current?.click()}
                className="border-2 border-dashed border-muted-foreground/30 hover:border-primary/60 rounded-lg p-6 text-center cursor-pointer transition-colors bg-muted/20 hover:bg-muted/30"
              >
                <FileText className="h-8 w-8 mx-auto text-muted-foreground/60 mb-2" />
                <span className="text-xs font-medium text-foreground block">
                  Haz clic para seleccionar tu CV
                </span>
                <span className="text-[11px] text-muted-foreground block mt-1">
                  Se almacenará exclusivamente en data/uploaded_cvs/
                </span>
              </div>

              {uploadMessage && (
                <div
                  className={`p-2.5 rounded-md text-xs flex items-center gap-2 ${
                    uploadMessage.error
                      ? "bg-destructive/10 text-destructive border border-destructive/20"
                      : "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20"
                  }`}
                >
                  {uploadMessage.error ? (
                    <AlertCircle className="h-4 w-4 shrink-0" />
                  ) : (
                    <CheckCircle2 className="h-4 w-4 shrink-0" />
                  )}
                  <span>{uploadMessage.text}</span>
                </div>
              )}

              {/* Nota de Privacidad Estricta */}
              <div className="p-2.5 bg-muted/40 rounded-md border text-[11px] text-muted-foreground flex items-start gap-2">
                <ShieldAlert className="h-4 w-4 text-emerald-500 shrink-0 mt-0.5" />
                <span>
                  <strong>Garantía de Privacidad:</strong> La subida de archivos guarda el archivo en almacenamiento
                  local. <u>Jamás</u> se transmite a servicios cloud de IA ni sobrescribe el perfil canónico.
                </span>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Columna Derecha: Pre-flight Check y Ejecución */}
        <div className="space-y-6 lg:col-span-2">
          {/* Tarjeta de Pre-flight Check */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm">Comprobación Previa (Pre-flight Check)</CardTitle>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={loadData}
                  disabled={isPreflightLoading}
                  className="h-7 text-xs flex items-center gap-1"
                >
                  <RefreshCw className={`h-3 w-3 ${isPreflightLoading ? "animate-spin" : ""}`} />
                  Verificar
                </Button>
              </div>
              <CardDescription>
                Validación de dependencias operativas antes de permitir una búsqueda manual
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {/* 1. Ollama */}
                <div className="border rounded-md p-3 bg-muted/30 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold flex items-center gap-1.5">
                      <Cpu className="h-3.5 w-3.5 text-primary" /> Ollama
                    </span>
                    <Badge variant={preflight?.ollama.healthy ? "success" : "destructive"}>
                      {preflight?.ollama.healthy ? "Operativo" : "Inaccesible"}
                    </Badge>
                  </div>
                  <p className="text-[11px] text-muted-foreground truncate">
                    {preflight?.ollama.healthy
                      ? `Modelos: ${preflight?.ollama.models?.join(", ") || "qwen2.5"}`
                      : preflight?.ollama.error || "Servicio detenido"}
                  </p>
                </div>

                {/* 2. Cerrojo de Pipeline */}
                <div className="border rounded-md p-3 bg-muted/30 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold flex items-center gap-1.5">
                      <Play className="h-3.5 w-3.5 text-primary" /> Cerrojo
                    </span>
                    <Badge variant={preflight?.pipeline.is_running ? "warning" : "success"}>
                      {preflight?.pipeline.is_running ? "Ocupado" : "Libre"}
                    </Badge>
                  </div>
                  <p className="text-[11px] text-muted-foreground">
                    {preflight?.pipeline.is_running
                      ? "Búsqueda en curso activo"
                      : "Sin tareas concurrentes"}
                  </p>
                </div>

                {/* 3. Base de Datos SQLite */}
                <div className="border rounded-md p-3 bg-muted/30 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold flex items-center gap-1.5">
                      <Database className="h-3.5 w-3.5 text-primary" /> SQLite
                    </span>
                    <Badge variant={preflight?.database.healthy ? "success" : "destructive"}>
                      {preflight?.database.healthy ? "Conectada" : "Error"}
                    </Badge>
                  </div>
                  <p className="text-[11px] text-muted-foreground">Modo WAL + Transacciones</p>
                </div>
              </div>

              {/* Botón de Lanzamiento Manual */}
              <div className="pt-3 border-t flex flex-col sm:flex-row items-center justify-between gap-3">
                <div>
                  <span className="text-xs font-medium text-foreground block">
                    ¿Deseas escanear ofertas en este momento?
                  </span>
                  <span className="text-[11px] text-muted-foreground block">
                    Consultará InfoJobs, Tecnoempleo RSS y JobSpy aplicando deduplicación difusa y scoring local.
                  </span>
                </div>

                <Button
                  onClick={handleTriggerSearch}
                  disabled={!preflight?.can_execute || isSearchRunning}
                  className="w-full sm:w-auto flex items-center gap-2 h-9 px-5 shrink-0"
                >
                  <Play className={`h-4 w-4 fill-current ${isSearchRunning ? "animate-pulse" : ""}`} />
                  {isSearchRunning ? "Búsqueda en curso..." : "Iniciar Búsqueda Manual"}
                </Button>
              </div>

              {searchFeedback && (
                <div className="p-2.5 rounded-md bg-primary/10 border border-primary/20 text-xs text-primary font-medium">
                  {searchFeedback}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Consola de Logs del Pipeline */}
          <div className="space-y-2">
            <h3 className="text-sm font-semibold tracking-tight text-foreground">
              Monitor de Escaneo en Tiempo Real
            </h3>
            <LogConsole height="h-80" />
          </div>
        </div>
      </div>
    </div>
  );
}
