"use client";

import React, { useEffect, useState, useRef } from "react";
import {
  Upload,
  CheckCircle2,
  AlertCircle,
  FileCheck,
  FileText,
  Eye,
  RefreshCw,
  Trash2,
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
      const countMsg = res.re_evaluated_jobs !== undefined ? ` • ${res.re_evaluated_jobs} ofertas adaptadas` : "";
      setUploadMessage({
        text: `CV "${res.filename}" activado (${ext})${countMsg}.`,
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
      const res = await api.selectActiveCV(filename);
      const countMsg = res.re_evaluated_jobs !== undefined ? ` • ${res.re_evaluated_jobs} ofertas adaptadas` : "";
      setUploadMessage({
        text: `CV activo: "${filename}"${countMsg}.`,
        error: false,
      });
      await loadData();
      if (onCvChanged) onCvChanged();
    } catch (err: any) {
      console.error("[CvManager] Error seleccionando CV:", err);
      alert(`Error seleccionando CV: ${err.message}`);
    }
  };

  const handlePreview = async (filename?: string) => {
    setCvPreviewLoading(true);
    setCvPreviewOpen(true);
    try {
      const data = await api.previewActiveCV(filename);
      setCvPreviewData(data);
    } catch (err: any) {
      alert(`Error extrayendo texto: ${err.message}`);
      setCvPreviewOpen(false);
    } finally {
      setCvPreviewLoading(false);
    }
  };

  const [deletingFile, setDeletingFile] = useState<string | null>(null);

  const handleDeleteCV = async (filename: string) => {
    if (!window.confirm(`¿Eliminar definitivamente "${filename}" del almacenamiento local?`)) {
      return;
    }
    setDeletingFile(filename);
    try {
      const res = await api.deleteCV(filename);
      setUploadMessage({
        text: res.message || `CV "${filename}" eliminado correctamente.`,
        error: false,
      });
      await loadData();
      if (onCvChanged) onCvChanged();
    } catch (err: any) {
      alert(`Error al eliminar CV: ${err.message}`);
    } finally {
      setDeletingFile(null);
    }
  };

  const customCvs = cvList.filter((c) => !c.is_default);

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Tarjeta Unificada de CV Activo y Subida en una sola fila */}
      <Card className="border bg-card/80 backdrop-blur-sm shadow-sm">
        <CardHeader className="pb-2 pt-3 px-3 sm:px-4 border-b border-border/40">
          <div className="flex items-center gap-1.5">
            <FileCheck className="h-4 w-4 text-primary" />
            <CardTitle className="text-xs sm:text-sm font-semibold">Currículum Activo</CardTitle>
            <InfoTooltip content="Documento que evalúa la IA local frente a cada oferta para determinar la puntuación ATS y redactar documentos adaptados." />
          </div>
        </CardHeader>

        <CardContent className="space-y-2.5 pt-3 px-3 sm:px-4">
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileUpload}
            accept=".pdf,.md,.markdown,.txt"
            className="hidden"
            id="cv-file-upload-input"
            disabled={isUploading}
          />

          {/* Fila única compacta: Desplegable + Ojo + Subir (solo icono) + Papelera */}
          <div className="flex items-center gap-1.5">
            <div className="flex-1 min-w-0">
              <Select
                value={activeCV?.type === "none" || !activeCV ? "none" : activeCV?.filename}
                onChange={(e) => handleSelectCV(e.target.value)}
                className="text-xs w-full h-8 bg-background truncate font-medium"
              >
                <option value="none">Sin CV (Sin filtrado)</option>
                {customCvs.map((c) => (
                  <option key={c.filename} value={c.filename}>
                    {c.filename} ({c.size_bytes ? `${(c.size_bytes / 1024).toFixed(0)} KB` : ""})
                  </option>
                ))}
              </Select>
            </div>

            {/* Ojo: ver texto extraído del CV seleccionado */}
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => handlePreview(activeCV?.filename)}
              disabled={!activeCV || activeCV.type === "none"}
              className="h-8 w-8 p-0 shrink-0 text-primary hover:text-primary/80 hover:border-primary/50"
              title={activeCV?.type !== "none" ? "Previsualizar texto extraído de este CV" : "Sin CV seleccionado"}
            >
              <Eye className="h-4 w-4" />
            </Button>

            {/* Subir CV: solo símbolo de subir */}
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
              className="h-8 w-8 p-0 shrink-0 text-primary hover:text-primary/80 hover:border-primary/50"
              title="Subir nuevo currículum (PDF, Markdown o TXT)"
            >
              <Upload className={`h-4 w-4 ${isUploading ? "animate-bounce" : ""}`} />
            </Button>

            {/* Papelera: eliminar CV seleccionado */}
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => activeCV?.filename && handleDeleteCV(activeCV.filename)}
              disabled={!activeCV || activeCV.type === "none" || deletingFile === activeCV?.filename}
              className="h-8 w-8 p-0 shrink-0 text-muted-foreground hover:text-destructive hover:border-destructive/50"
              title={activeCV?.type !== "none" ? `Eliminar "${activeCV?.filename}"` : "Ningún CV seleccionado"}
            >
              <Trash2 className={`h-4 w-4 ${deletingFile ? "animate-spin" : ""}`} />
            </Button>
          </div>

          {/* Barra de Progreso Visual mientras se procesa la subida */}
          {isUploading && (
            <div className="pt-1">
              <CvProgressBar stage={uploadStage} progress={uploadProgress} />
            </div>
          )}

          {/* Mensaje de confirmación o alerta tras subir o eliminar */}
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
