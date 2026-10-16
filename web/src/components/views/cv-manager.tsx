"use client";

import React, { useEffect, useState, useRef } from "react";
import {
  Upload,
  CheckCircle2,
  AlertCircle,
  FileCheck,
  Eye,
  RefreshCw,
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select } from "@/components/ui/select";
import { Dialog } from "@/components/ui/dialog";
import { InfoTooltip } from "@/components/ui/info-tooltip";
import { CvProgressBar } from "@/components/features/cv/cv-progress-bar";
import { ActiveCVInfo, api } from "@/lib/api";

interface CvManagerProps {
  onCvChanged?: () => void;
  className?: string;
}

export function CvManager({ onCvChanged, className = "" }: CvManagerProps) {
  const [activeCV, setActiveCV] = useState<ActiveCVInfo | null>(null);
  const [cvList, setCvList] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [uploadStage, setUploadStage] = useState<string>("");
  const [uploadMessage, setUploadMessage] = useState<{ text: string; error: boolean } | null>(null);
  const [cvPreviewOpen, setCvPreviewOpen] = useState<boolean>(false);
  const [cvPreviewData, setCvPreviewData] = useState<any>(null);
  const [cvPreviewLoading, setCvPreviewLoading] = useState<boolean>(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadData = async () => {
    try {
      const [cv, list] = await Promise.all([
        api.getActiveCV(),
        api.listUploadedCVs(),
      ]);
      setActiveCV(cv);
      setCvList(list);
    } catch (e: any) {
      console.error("[CvManager] Error cargando datos de CV:", e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setUploadProgress(15);
    setUploadStage("Leyendo archivo local...");
    setUploadMessage(null);

    // Simulación progresiva de etapas mientras el servidor analiza y extrae texto con PyPDF / Markdown
    const progressInterval = setInterval(() => {
      setUploadProgress((prev) => {
        if (prev < 40) {
          setUploadStage("Transfiriendo archivo...");
          return prev + 12;
        }
        if (prev < 70) {
          setUploadStage("Extrayendo texto y formateando...");
          return prev + 10;
        }
        if (prev < 90) {
          setUploadStage("Verificando perfil ATS para IA local...");
          return prev + 4;
        }
        return prev;
      });
    }, 280);

    try {
      const res = await api.uploadCV(file);
      clearInterval(progressInterval);
      setUploadProgress(100);
      const ext = (res.type || res.filename?.split(".").pop() || "archivo").toUpperCase();
      setUploadMessage({
        text: `CV "${res.filename}" cargado (${ext}).`,
        error: false,
      });
      await loadData();
      if (onCvChanged) onCvChanged();
    } catch (err: any) {
      clearInterval(progressInterval);
      setUploadProgress(0);
      setUploadStage("");
      setUploadMessage({ text: err.message || "Error al subir el archivo.", error: true });
    } finally {
      setTimeout(() => {
        setIsUploading(false);
        setUploadProgress(0);
        setUploadStage("");
      }, 1500);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleSelectCV = async (filename: string) => {
    try {
      await api.selectActiveCV(filename);
      await loadData();
      if (onCvChanged) onCvChanged();
    } catch (err: any) {
      console.error("[CvManager] Error seleccionando CV:", err);
      alert(`Error seleccionando CV: ${err.message}`);
    }
  };

  const handlePreview = async () => {
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
  };

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Tarjeta Unificada de CV Activo y Subida en una sola fila */}
      <Card className="border bg-card/80 backdrop-blur-sm shadow-sm overflow-hidden">
        <CardHeader className="pb-2 pt-3 px-3 sm:px-4 border-b border-border/40">
          <div className="flex items-center justify-between gap-1">
            <div className="flex items-center gap-1.5">
              <FileCheck className="h-4 w-4 text-primary" />
              <CardTitle className="text-xs sm:text-sm font-semibold">Currículum Activo</CardTitle>
              <InfoTooltip content="Documento que evalúa la IA local frente a cada oferta para determinar la puntuación ATS y redactar documentos adaptados." />
            </div>
            <Badge variant={activeCV?.is_default ? "outline" : "secondary"} className="text-[10px] py-0">
              {activeCV?.type === "canonical" ? "Canónico" : "Personalizado"}
            </Badge>
          </div>
        </CardHeader>

        <CardContent className="space-y-3 pt-3 px-3 sm:px-4">
          {/* Ficha técnica compacta */}
          <div className="bg-muted/40 p-2 rounded-lg text-xs space-y-1 font-mono border">
            <div className="flex justify-between gap-2">
              <span className="text-muted-foreground shrink-0">Archivo:</span>
              <span className="font-semibold text-foreground truncate max-w-[150px]" title={activeCV?.filename}>
                {activeCV?.filename || "cv_base.md"}
              </span>
            </div>
            <div className="flex justify-between gap-2 text-[11px]">
              <span className="text-muted-foreground shrink-0">Tamaño:</span>
              <span>{activeCV?.size_bytes ? `${(activeCV.size_bytes / 1024).toFixed(1)} KB` : "0 KB"}</span>
            </div>
          </div>

          {/* Fila del Selector de CV con Botón Subir CV a la derecha */}
          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <label className="text-[11px] font-medium text-muted-foreground">Seleccionar CV Activo:</label>
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileUpload}
                accept=".pdf,.md,.markdown,.txt"
                className="hidden"
                id="cv-file-upload-input"
                disabled={isUploading}
              />
            </div>

            <div className="flex items-center gap-1.5">
              <div className="flex-1 min-w-0">
                <Select
                  value={activeCV?.is_default ? "default" : activeCV?.filename}
                  onChange={(e) => handleSelectCV(e.target.value)}
                  className="text-xs w-full h-8 bg-background truncate"
                >
                  <option value="default">cv_base.md (Base)</option>
                  {cvList
                    .filter((c) => !c.is_default)
                    .map((c) => (
                      <option key={c.filename} value={c.filename}>
                        {c.filename}
                      </option>
                    ))}
                </Select>
              </div>

              {/* Botón para subir CV ubicado a la derecha del selector */}
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => fileInputRef.current?.click()}
                disabled={isUploading}
                className="h-8 px-2.5 text-xs shrink-0 flex items-center gap-1 font-medium hover:border-primary/50 shadow-xs"
                title="Subir nuevo currículum en PDF, Markdown o TXT"
              >
                <Upload className={`h-3.5 w-3.5 ${isUploading ? "animate-bounce text-primary" : "text-primary"}`} />
                <span>Subir CV</span>
              </Button>
            </div>
          </div>

          {/* Barra de Progreso Visual mientras se procesa la subida */}
          {isUploading && (
            <div className="pt-1">
              <CvProgressBar stage={uploadStage} progress={uploadProgress} />
            </div>
          )}

          {/* Mensaje de confirmación o alerta tras subir */}
          {uploadMessage && (
            <div
              className={`p-2 rounded text-[11px] flex items-center gap-1.5 ${
                uploadMessage.error
                  ? "bg-destructive/15 text-destructive border border-destructive/20"
                  : "bg-emerald-500/15 text-emerald-400 border border-emerald-500/20"
              }`}
            >
              {uploadMessage.error ? (
                <AlertCircle className="h-3.5 w-3.5 shrink-0" />
              ) : (
                <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
              )}
              <span className="truncate">{uploadMessage.text}</span>
            </div>
          )}

          {/* Botón de Previsualización de Texto Extraído */}
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={handlePreview}
            className="w-full text-xs h-7 flex items-center justify-center gap-1.5 text-muted-foreground hover:text-foreground border border-dashed border-border/60 hover:border-primary/40"
          >
            <Eye className="h-3.5 w-3.5 text-primary" />
            <span>Previsualizar Texto Extraído</span>
          </Button>
        </CardContent>
      </Card>

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
