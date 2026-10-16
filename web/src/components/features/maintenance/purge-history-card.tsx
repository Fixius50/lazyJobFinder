"use client";

import React, { useState } from "react";
import { ShieldAlert, Trash2, AlertTriangle, CheckCircle2 } from "lucide-react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog } from "@/components/ui/dialog";
import { api } from "@/lib/api";
import { CONFIRMATION_PHRASES } from "@/lib/constants";

interface PurgeHistoryCardProps {
  onHistoryCleared?: () => void;
  className?: string;
}

export function PurgeHistoryCard({ onHistoryCleared, className = "" }: PurgeHistoryCardProps) {
  const [modalOpen, setModalOpen] = useState<boolean>(false);
  const [confirmPhrase, setConfirmPhrase] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  const handleClearHistory = async () => {
    if (confirmPhrase !== CONFIRMATION_PHRASES.clear_history) {
      alert(`Frase incorrecta. Debes escribir exactamente: "${CONFIRMATION_PHRASES.clear_history}"`);
      return;
    }

    setIsLoading(true);
    try {
      const res = await api.maintenanceClearHistory(confirmPhrase);
      setModalOpen(false);
      setConfirmPhrase("");
      setFeedback(
        `${res.message} (Ofertas eliminadas: ${res.details?.jobs_deleted ?? 0}, Documentos: ${
          res.details?.documents_deleted ?? 0
        })`
      );
      setTimeout(() => setFeedback(null), 5000);
      if (onHistoryCleared) {
        onHistoryCleared();
      }
    } catch (e: any) {
      alert(`Fallo al borrar historial: ${e.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className={`space-y-3 ${className}`}>
      {feedback && (
        <div className="p-2.5 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-xs flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <span>{feedback}</span>
        </div>
      )}

      {/* Tarjeta de Mantenimiento con Botón Rojo */}
      <Card className="border border-destructive/20 bg-destructive/5 shadow-sm">
        <CardHeader className="pb-2 pt-3 px-3 sm:px-4">
          <CardTitle className="text-xs sm:text-sm text-destructive flex items-center gap-1.5 font-semibold">
            <ShieldAlert className="h-4 w-4 shrink-0" />
            Mantenimiento y Purga del Sistema
          </CardTitle>
          <CardDescription className="text-[11px]">
            Acciones seguras protegidas por frases de confirmación exacta
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 pt-1 px-3 sm:px-4">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 p-2.5 rounded-lg border bg-background/60">
            <div>
              <h4 className="font-semibold text-xs text-foreground">Borrar Historial de Ofertas</h4>
              <p className="text-[10px] text-muted-foreground leading-tight">
                Vacía las ofertas y PDFs generados. Tu perfil y configuración se conservan.
              </p>
            </div>
            <Button
              size="sm"
              variant="destructive"
              onClick={() => setModalOpen(true)}
              className="h-7 px-3 text-xs shrink-0 flex items-center gap-1 font-medium shadow-xs self-end sm:self-auto"
            >
              <Trash2 className="h-3 w-3" />
              Vaciar
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Modal de Confirmación Segura */}
      <Dialog
        open={modalOpen}
        onOpenChange={setModalOpen}
        title="Confirmar borrado completo de historial"
        description="Esta acción vaciará todas las ofertas detectadas en SQLite y eliminará los documentos generados. El perfil y la configuración se mantendrán intactos."
      >
        <div className="space-y-4 pt-2 text-xs">
          <div className="flex items-start space-x-2 text-amber-400 bg-amber-500/10 p-3 rounded-lg border border-amber-500/20">
            <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
            <span>
              Para evitar pérdidas involuntarias, escribe exactamente la frase de confirmación:
            </span>
          </div>

          <div className="p-2 rounded bg-muted/50 border text-center font-mono font-bold tracking-wider text-xs select-all">
            {CONFIRMATION_PHRASES.clear_history}
          </div>

          <Input
            value={confirmPhrase}
            onChange={(e) => setConfirmPhrase(e.target.value)}
            placeholder={`Escribe ${CONFIRMATION_PHRASES.clear_history}`}
            className="text-xs font-mono"
            autoFocus
          />

          <div className="flex justify-end space-x-2 pt-2 border-t">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setModalOpen(false);
                setConfirmPhrase("");
              }}
              disabled={isLoading}
              className="text-xs h-8"
            >
              Cancelar
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={handleClearHistory}
              disabled={confirmPhrase !== CONFIRMATION_PHRASES.clear_history || isLoading}
              className="text-xs h-8 flex items-center gap-1.5"
            >
              <Trash2 className="h-3.5 w-3.5" />
              {isLoading ? "Vaciando..." : "Confirmar Vaciar"}
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  );
}
