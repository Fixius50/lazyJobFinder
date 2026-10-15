"use client";

import React, { useEffect, useState, useRef } from "react";
import {
  Upload,
  CheckCircle2,
  AlertCircle,
  Play,
  Cpu,
  Database,
  RefreshCw,
  FileCheck,
  Eye,
  Sparkles,
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select } from "@/components/ui/select";
import { Dialog } from "@/components/ui/dialog";
import { ActiveCVInfo, PreflightResponse, api } from "@/lib/api";

export function SearchCVView() {
  const [activeCV, setActiveCV] = useState<ActiveCVInfo | null>(null);
  const [cvList, setCvList] = useState<any[]>([]);
  const [preflight, setPreflight] = useState<PreflightResponse | null>(null);
  const [isPreflightLoading, setIsPreflightLoading] = useState<boolean>(true);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadMessage, setUploadMessage] = useState<{ text: string; error: boolean } | null>(null);
  const [isSearchRunning, setIsSearchRunning] = useState<boolean>(false);
  const [searchFeedback, setSearchFeedback] = useState<string | null>(null);
  const [cvPreviewOpen, setCvPreviewOpen] = useState<boolean>(false);
  const [cvPreviewData, setCvPreviewData] = useState<any>(null);
  const [cvPreviewLoading, setCvPreviewLoading] = useState<boolean>(false);
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

    setIsUploading(true);
    setUploadMessage(null);
    try {
      const res = await api.uploadCV(file);
      setUploadMessage({
        text: `CV "${res.filename}" subido correctamente (${res.type.toUpperCase()}).`,
        error: false,
      });
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
      await api.selectActiveCV(filename);
      await loadData();
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
    <div className="space-y-4 sm:space-y-6 w-full">
      {/* Encabezado fluido */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b">
        <div>
          <h2 className="text-lg sm:text-xl font-bold tracking-tight">Gestión de CV y Búsqueda Manual</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Carga segura de currículum local (PDF, Markdown o Texto) y control del motor de ofertas.
          </p>
        </div>

        <Button
          size="sm"
          variant="outline"
          onClick={loadData}
          disabled={isPreflightLoading}
          className="flex items-center gap-1.5 h-8 text-xs self-start sm:self-auto"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${isPreflightLoading ? "animate-spin" : ""}`} />
          Actualizar
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 sm:gap-6">
        {/* Columna Izquierda: CV Activo y Subida */}
        <div className="space-y-4 sm:space-y-6 lg:col-span-5">
          {/* Tarjeta de CV Activo */}
          <Card className="border bg-card/80 backdrop-blur-sm shadow-sm">
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
              <CardDescription className="text-xs">
                Documento que contrasta la IA local con cada oferta encontrada
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="bg-muted/40 p-3 rounded-lg text-xs space-y-1.5 font-mono border">
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
                  className="text-xs w-full"
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

              {/* Botón de Previsualización de Texto Extraído */}
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={async () => {
                  setCvPreviewLoading(true);
                  setCvPreviewOpen(true);
                  try {
                    const data = await api.previewActiveCV();
                    setCvPreviewData(data);
                  } catch (err: any) {
                    alert(`Error extrayendo texto: ${err.message}`);
                    setCvPreviewOpen(false);
                  } finally {
                    setCvPreviewLoading(false);
                  }
                }}
                className="w-full text-xs h-8 flex items-center justify-center gap-1.5"
              >
                <Eye className="h-3.5 w-3.5 text-primary" />
                Previsualizar Texto Extraído por la IA
              </Button>
            </CardContent>
          </Card>

          {/* Tarjeta de Subida */}
          <Card className="border bg-card/80 backdrop-blur-sm shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm flex items-center gap-2">
                <Upload className="h-4 w-4 text-primary" />
                Subir Nuevo Currículum
              </CardTitle>
              <CardDescription className="text-xs">
                Formatos admitidos: <strong>PDF</strong>, <strong>Markdown (.md)</strong> o <strong>Texto (.txt)</strong> hasta 5 MB.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileUpload}
                accept=".pdf,.md,.markdown,.txt"
                className="hidden"
                id="cv-file-upload"
              />
              <label
                htmlFor="cv-file-upload"
                className="border-2 border-dashed rounded-lg p-5 flex flex-col items-center justify-center cursor-pointer hover:border-primary/60 transition-colors bg-muted/20 text-center space-y-2 block"
              >
                <Upload className="h-7 w-7 text-muted-foreground" />
                <span className="text-xs font-medium text-foreground">
                  {isUploading ? "Analizando y extrayendo texto..." : "Haz clic o arrastra un PDF / Markdown aquí"}
                </span>
                <span className="text-[11px] text-muted-foreground">
                  Se extraerá el texto directamente sin alterar tu perfil maestro
                </span>
              </label>

              {uploadMessage && (
                <div
                  className={`p-2.5 rounded text-xs flex items-center gap-2 ${
                    uploadMessage.error
                      ? "bg-destructive/15 text-destructive border border-destructive/20"
                      : "bg-emerald-500/15 text-emerald-400 border border-emerald-500/20"
                  }`}
                >
                  {uploadMessage.error ? <AlertCircle className="h-4 w-4 shrink-0" /> : <CheckCircle2 className="h-4 w-4 shrink-0" />}
                  <span>{uploadMessage.text}</span>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Columna Derecha: Diagnóstico Preflight y Lanzador de Búsqueda */}
        <div className="space-y-4 sm:space-y-6 lg:col-span-7">
          {/* Tarjeta de Lanzamiento Manual */}
          <Card className="border bg-card/80 backdrop-blur-sm shadow-sm">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Play className="h-4 w-4 text-primary fill-current" />
                  Ejecutar Pipeline Manual
                </CardTitle>
                <Badge variant={isSearchRunning ? "warning" : "success"}>
                  {isSearchRunning ? "Búsqueda en curso" : "Listo para escanear"}
                </Badge>
              </div>
              <CardDescription className="text-xs">
                Inicia el rastreo de ofertas en Tecnoempleo, Indeed y LinkedIn, deduplicando y puntuando con Ollama.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="p-3.5 rounded-lg bg-muted/40 border space-y-2.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Umbral mínimo de evaluación:</span>
                  <span className="font-semibold text-primary">≥ 65 puntos</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Garantía de veracidad:</span>
                  <span className="font-medium text-emerald-400 flex items-center gap-1">
                    <CheckCircle2 className="h-3 w-3" /> ProfileVerifier Activo (0 invenciones)
                  </span>
                </div>
              </div>

              <div className="flex flex-col sm:flex-row items-center gap-3">
                <Button
                  onClick={handleTriggerSearch}
                  disabled={isSearchRunning || isPreflightLoading || !preflight?.can_execute}
                  className="w-full sm:w-auto px-6 h-9 text-xs flex items-center justify-center gap-2"
                >
                  <Play className="h-3.5 w-3.5 fill-current" />
                  {isSearchRunning ? "Escaneando portales..." : "Escanear Ofertas Ahora"}
                </Button>

                {searchFeedback && (
                  <span className="text-xs text-muted-foreground flex items-center gap-1.5">
                    <Sparkles className="h-3.5 w-3.5 text-primary shrink-0" />
                    {searchFeedback}
                  </span>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Tarjeta de Estado Preflight */}
          <Card className="border bg-card/80 backdrop-blur-sm shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                Diagnóstico de Componentes Preflight
              </CardTitle>
              <CardDescription className="text-xs">
                Comprobaciones previas al rastreo para garantizar estabilidad
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                {/* Ollama Status */}
                <div className="p-3 rounded-lg border bg-muted/20 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="font-medium flex items-center gap-1.5">
                      <Cpu className="h-3.5 w-3.5 text-primary" /> Motor Ollama
                    </span>
                    <Badge variant={preflight?.ollama?.healthy ? "success" : "destructive"}>
                      {preflight?.ollama?.healthy ? "Operativo" : "Desconectado"}
                    </Badge>
                  </div>
                  <div className="text-[11px] text-muted-foreground">
                    Modelos: <span className="text-foreground font-mono">{preflight?.ollama?.models?.join(", ") || "qwen2.5:3b-instruct"}</span>
                  </div>
                </div>

                {/* Base de Datos SQLite */}
                <div className="p-3 rounded-lg border bg-muted/20 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="font-medium flex items-center gap-1.5">
                      <Database className="h-3.5 w-3.5 text-primary" /> SQLite WAL
                    </span>
                    <Badge variant={preflight?.database?.healthy ? "success" : "destructive"}>
                      {preflight?.database?.healthy ? "Conectada" : "Error"}
                    </Badge>
                  </div>
                  <div className="text-[11px] text-muted-foreground">
                    Estado: <span className="text-foreground font-semibold">{preflight?.database?.healthy ? "Operativa" : "Comprobar volumen"}</span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Modal de Previsualización de Texto Extraído */}
      <Dialog
        open={cvPreviewOpen}
        onOpenChange={setCvPreviewOpen}
        title="Texto Extraído del CV Activo"
        description={`Visualización exacta de lo que lee el extractor para evaluar afinidad (${cvPreviewData?.extension?.toUpperCase() || "PDF/MD"})`}
      >
        {cvPreviewLoading ? (
          <div className="flex items-center justify-center py-10">
            <RefreshCw className="h-6 w-6 animate-spin text-primary" />
          </div>
        ) : cvPreviewData ? (
          <div className="space-y-3 max-h-[70dvh] overflow-y-auto pr-1 text-xs">
            <div className="flex items-center justify-between p-2.5 rounded bg-muted/40 border font-mono text-[11px]">
              <span>Extensión: <strong>{cvPreviewData.extension}</strong></span>
              <span>Palabras: <strong>{cvPreviewData.word_count}</strong></span>
              <span>Caracteres: <strong>{cvPreviewData.char_count}</strong></span>
            </div>
            <div className="p-3 rounded bg-muted/20 border font-mono text-[11px] whitespace-pre-wrap max-h-96 overflow-y-auto leading-relaxed">
              {cvPreviewData.text_preview}
            </div>
          </div>
        ) : null}
      </Dialog>
    </div>
  );
}
