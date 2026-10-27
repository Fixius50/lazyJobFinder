"use client";

import React, { useEffect, useState, useRef } from "react";
import {
  Upload,
  CheckCircle2,
  AlertCircle,
  FileCheck,
  Eye,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { Dialog } from "@/components/ui/dialog";
import { InfoTooltip } from "@/components/ui/info-tooltip";
import { CvProgressBar } from "@/components/features/cv/cv-progress-bar";
import { ActiveCVInfo, api, hasValidCv } from "@/lib/api";
import { toast } from "sonner";

interface CvManagerProps {
  onCvChanged?: (activeCv: ActiveCVInfo | null) => void;
  className?: string;
}

export function CvManager({ onCvChanged, className = "" }: CvManagerProps) {
  const [activeCV, setActiveCV] = useState<ActiveCVInfo | null>(null);
  const [cvList, setCvList] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isSelecting, setIsSelecting] = useState<boolean>(false);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [uploadStage, setUploadStage] = useState<string>("");
  const [uploadMessage, setUploadMessage] = useState<{ text: string; error: boolean } | null>(null);
  const [cvPreviewOpen, setCvPreviewOpen] = useState<boolean>(false);
  const [cvPreviewData, setCvPreviewData] = useState<any>(null);
  const [cvPreviewLoading, setCvPreviewLoading] = useState<boolean>(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadData = async (notify: boolean = true) => {
    try {
      const [cv, list] = await Promise.all([
        api.getActiveCV(),
        api.listUploadedCVs(),
      ]);
      setActiveCV(cv);
      setCvList(list);
      if (notify && onCvChanged) {
        onCvChanged(cv);
      }
      return cv;
    } catch (e: any) {
      console.error("[CvManager] Error cargando datos de CV:", e);
      return null;
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    // En montaje inicial no disparar onCvChanged para evitar tormenta de peticiones redundantes
    loadData(false);
  }, []);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setUploadProgress(15);
    setUploadStage("Leyendo archivo local...");
    setUploadMessage(null);

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
      await loadData(true);
    } catch (err: any) {
      clearInterval(progressInterval);
      setUploadProgress(0);
      setUploadStage("");
      setUploadMessage({ text: err.message || "Error al subir el archivo.", error: true });
      await loadData(true);
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
    setIsSelecting(true);
    // Actualización optimista inmediata en la UI (0 ms de respuesta visual)
    if (filename === "none") {
      setActiveCV({
        type: "none",
        filename: "Ninguno",
        path: "",
        size_bytes: 0,
        modified_at: "n/a",
        is_default: false,
        description: "Sin CV activo.",
        search_terms: [],
        primary_role: "",
      });
    } else {
      const found = cvList.find((c) => c.filename === filename);
      if (found) {
        setActiveCV((prev) => ({
          type: "custom",
          filename: found.filename,
          path: `data/uploaded_cvs/${found.filename}`,
          size_bytes: found.size_bytes,
          modified_at: found.modified_at,
          is_default: false,
          description: "CV personalizado cargado localmente.",
          search_terms: prev?.filename === found.filename ? prev?.search_terms : [],
          primary_role: prev?.filename === found.filename ? prev?.primary_role : "",
        }));
      }
    }

    try {
      const res = await api.selectActiveCV(filename);
      const countMsg = res.re_evaluated_jobs !== undefined ? ` • ${res.re_evaluated_jobs} ofertas adaptadas` : "";
      toast.success(`CV activo establecido: "${filename}"${countMsg}`);
      await loadData(true);
    } catch (err: any) {
      console.error("[CvManager] Error seleccionando CV:", err);
      toast.error(`Error seleccionando CV: ${err.message || err}`);
      await loadData(true);
    } finally {
      setIsSelecting(false);
    }
  };

  const handlePreview = async (filename?: string) => {
    setCvPreviewLoading(true);
    setCvPreviewOpen(true);
    try {
      const data = await api.previewActiveCV(filename);
      setCvPreviewData(data);
    } catch (err: any) {
      toast.error(`Error extrayendo texto del CV: ${err.message || err}`);
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
      toast.success(res.message || `CV "${filename}" eliminado correctamente.`);
      await loadData(true);
    } catch (err: any) {
      toast.error(`Error al eliminar CV: ${err.message || err}`);
    } finally {
      setDeletingFile(null);
    }
  };

  const customCvs = cvList.filter((c) => !c.is_default);

  return (
    <div className={`relative inline-flex flex-col ${className}`}>
      {/* Barra en una sola línea: Currículum Activo, ?, Desplegable, Ojo, Subir, Borrar */}
      <div className="flex items-center gap-1.5 bg-card/80 border border-border/60 rounded-lg px-2.5 py-1 backdrop-blur-sm shadow-xs">
        {/* Título y tooltip */}
        <div className="flex items-center gap-1 mr-1">
          <FileCheck className="h-4 w-4 text-primary shrink-0" />
          <span className="text-xs font-semibold whitespace-nowrap hidden sm:inline">Currículum Activo</span>
          <span className="text-xs font-semibold whitespace-nowrap sm:hidden">CV</span>
          <InfoTooltip content="Documento que evalúa la IA local frente a cada oferta para determinar la puntuación ATS y redactar documentos adaptados." />
        </div>

        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileUpload}
          accept=".pdf,.md,.markdown,.txt"
          className="hidden"
          id="cv-file-upload-input"
          disabled={isUploading}
        />

        {/* Desplegable de selección */}
        <div className="w-36 sm:w-48 md:w-56 lg:w-64">
          <Select
            value={!hasValidCv(activeCV) ? "none" : activeCV?.filename}
            onChange={(e) => handleSelectCV(e.target.value)}
            disabled={isUploading || isSelecting}
            className={`text-xs w-full h-8 bg-background/90 font-medium truncate ${isSelecting ? "opacity-60 cursor-wait" : ""}`}
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
          disabled={!hasValidCv(activeCV)}
          className="h-8 w-8 p-0 shrink-0 text-primary hover:text-primary/80 hover:border-primary/50"
          title={hasValidCv(activeCV) ? "Previsualizar texto extraído de este CV" : "Sin CV seleccionado"}
        >
          <Eye className="h-4 w-4" />
        </Button>

        {/* Subir CV: solo icono */}
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => fileInputRef.current?.click()}
          disabled={isUploading}
          className="h-8 w-8 p-0 shrink-0 text-primary hover:text-primary/80 hover:border-primary/50"
          title="Subir nuevo currículum (PDF, Markdown o TXT)"
        >
          <Upload className={`h-4 w-4 ${isUploading ? "animate-bounce text-amber-400" : ""}`} />
        </Button>

        {/* Papelera: eliminar CV seleccionado */}
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => activeCV?.filename && handleDeleteCV(activeCV.filename)}
          disabled={!hasValidCv(activeCV) || deletingFile === activeCV?.filename}
          className="h-8 w-8 p-0 shrink-0 text-muted-foreground hover:text-destructive hover:border-destructive/50"
          title={hasValidCv(activeCV) ? `Eliminar "${activeCV?.filename}"` : "Ningún CV seleccionado"}
        >
          <Trash2 className={`h-4 w-4 ${deletingFile ? "animate-spin text-destructive" : ""}`} />
        </Button>
      </div>

      {/* Barra de Progreso Visual flotante mientras se sube */}
      {isUploading && (
        <div className="absolute top-full left-0 right-0 mt-1 z-30 bg-background/95 p-2 rounded-md border shadow-md">
          <CvProgressBar stage={uploadStage} progress={uploadProgress} />
        </div>
      )}

      {/* Mensaje de confirmación o alerta tras subir o eliminar */}
      {uploadMessage && !isUploading && (
        <div
          className={`absolute top-full left-0 right-0 mt-1 z-30 p-1.5 px-2.5 rounded-md text-2xs flex items-center justify-between gap-1.5 shadow-md ${
            uploadMessage.error
              ? "bg-destructive/15 text-destructive border border-destructive/20"
              : "bg-emerald-500/15 text-emerald-400 border border-emerald-500/20"
          }`}
        >
          <div className="flex items-center gap-1.5 truncate">
            {uploadMessage.error ? (
              <AlertCircle className="h-3.5 w-3.5 shrink-0" />
            ) : (
              <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
            )}
            <span className="truncate">{uploadMessage.text}</span>
          </div>
          <button
            onClick={() => setUploadMessage(null)}
            className="text-muted-foreground hover:text-foreground text-xs font-bold ml-2 shrink-0"
          >
            ×
          </button>
        </div>
      )}

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
            <div className="flex items-center justify-between p-2.5 rounded bg-muted/40 border font-mono text-2xs">
              <span>Extensión: <strong>{cvPreviewData.extension}</strong></span>
              <span>Palabras: <strong>{cvPreviewData.word_count}</strong></span>
              <span>Caracteres: <strong>{cvPreviewData.char_count}</strong></span>
            </div>
            <div className="p-3 rounded bg-muted/20 border font-mono text-2xs whitespace-pre-wrap max-h-96 overflow-y-auto leading-relaxed">
              {cvPreviewData.text_preview}
            </div>
          </div>
        ) : null}
      </Dialog>
    </div>
  );
}
