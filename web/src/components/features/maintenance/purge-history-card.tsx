"use client";

import React, { useState } from "react";
import { Trash2, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog } from "@/components/ui/dialog";
import { api } from "@/lib/api";
import { CONFIRMATION_PHRASES } from "@/lib/constants";

interface PurgeHistoryProps {
  onHistoryCleared?: () => void;
  className?: string;
}

/**
 * Botón y modal centralizado de vaciado de historial de candidaturas.
 * Protegido mediante frase de confirmación exacta para evitar pérdidas involuntarias.
 */
export function PurgeHistoryButton({ onHistoryCleared, className = "" }: PurgeHistoryProps) {
  const [modalOpen, setModalOpen] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const handleClearHistory = async () => {
    setIsLoading(true);
    try {
      await api.maintenanceClearHistory(CONFIRMATION_PHRASES.clear_history);
      setModalOpen(false);
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
    <>
      <Button
        size="sm"
        variant="destructive"
        onClick={() => setModalOpen(true)}
        className={`flex items-center gap-1.5 h-8 text-xs font-medium shadow-xs ${className}`}
        title="Vacía todas las ofertas registradas en SQLite y elimina PDFs generados"
      >
        <Trash2 className="h-3.5 w-3.5" />
        Vaciar Historial
      </Button>

      <Dialog
        open={modalOpen}
        onOpenChange={setModalOpen}
        title="¿Vaciar todo el historial de ofertas?"
        description="Esta acción eliminará de forma irreversible todas las ofertas registradas en la base de datos y los documentos generados. Tu currículum activo y tu configuración se mantendrán intactos."
      >
        <div className="space-y-4 pt-2 text-xs">
          <div className="flex items-start space-x-2 text-amber-400 bg-amber-500/10 p-3 rounded-lg border border-amber-500/20">
            <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
            <span>
              ¿Estás seguro de que deseas vaciar el historial? Una vez borrado, podrás realizar nuevas búsquedas limpias.
            </span>
          </div>

          <div className="flex justify-end space-x-2 pt-2 border-t">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setModalOpen(false)}
              disabled={isLoading}
              className="text-xs h-8"
            >
              Cancelar
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={handleClearHistory}
              disabled={isLoading}
              className="text-xs h-8 flex items-center gap-1.5"
            >
              <Trash2 className="h-3.5 w-3.5" />
              {isLoading ? "Vaciando..." : "Sí, Vaciar Historial"}
            </Button>
          </div>
        </div>
      </Dialog>
    </>
  );
}

// Export compatible por si se requiere en otras vistas
export const PurgeHistoryCard = PurgeHistoryButton;
