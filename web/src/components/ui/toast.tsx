"use client";

import React, { useEffect, useState, useCallback } from "react";
import { CheckCircle2, AlertCircle, Info, AlertTriangle, X } from "lucide-react";

export type ToastType = "info" | "success" | "error" | "warning";

export interface ToastItem {
  id: string;
  message: string;
  type: ToastType;
  duration: number;
}

type ToastListener = (toasts: ToastItem[]) => void;

let currentToasts: ToastItem[] = [];
const listeners = new Set<ToastListener>();

function notify() {
  listeners.forEach((listener) => listener([...currentToasts]));
}

export function showToast(message: string, type: ToastType = "info", duration = 4500) {
  const id = Math.random().toString(36).substring(2, 9) + Date.now().toString(36);
  const newToast: ToastItem = { id, message, type, duration };
  
  // Limitar a máximo 4 notificaciones simultáneas
  currentToasts = [...currentToasts.slice(-3), newToast];
  notify();

  if (duration > 0) {
    setTimeout(() => {
      dismissToast(id);
    }, duration);
  }

  return id;
}

export function dismissToast(id: string) {
  currentToasts = currentToasts.filter((t) => t.id !== id);
  notify();
}

export const toast = {
  info: (msg: string, duration = 4500) => showToast(msg, "info", duration),
  success: (msg: string, duration = 4500) => showToast(msg, "success", duration),
  error: (msg: string, duration = 5000) => showToast(msg, "error", duration),
  warning: (msg: string, duration = 4500) => showToast(msg, "warning", duration),
  dismiss: dismissToast,
};

export function Toaster() {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  useEffect(() => {
    const handleUpdate = (updated: ToastItem[]) => setToasts(updated);
    listeners.add(handleUpdate);

    // Interceptar automáticamente cualquier alert(...) nativo del navegador para que fluya por aquí
    const originalAlert = window.alert;
    window.alert = (msg?: any) => {
      const text = String(msg ?? "");
      const lower = text.toLowerCase();
      if (lower.includes("error") || lower.includes("fallo") || lower.includes("exception")) {
        toast.error(text);
      } else if (
        lower.includes("éxito") ||
        lower.includes("exito") ||
        lower.includes("correctamente") ||
        lower.includes("guardad") ||
        lower.includes("iniciad") ||
        lower.includes("activad")
      ) {
        toast.success(text);
      } else if (lower.includes("aviso") || lower.includes("advertencia") || lower.includes("cuidado")) {
        toast.warning(text);
      } else {
        toast.info(text);
      }
    };

    return () => {
      listeners.delete(handleUpdate);
      window.alert = originalAlert;
    };
  }, []);

  if (toasts.length === 0) return null;

  return (
    <div
      className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm sm:max-w-md w-full px-3 sm:px-0 pointer-events-none"
      aria-live="polite"
    >
      {toasts.map((t) => {
        const isError = t.type === "error";
        const isSuccess = t.type === "success";
        const isWarning = t.type === "warning";

        let borderClasses = "border-primary/40 bg-card/95 text-foreground";
        let icon = <Info className="h-4 w-4 text-primary shrink-0 mt-0.5" />;

        if (isError) {
          borderClasses = "border-rose-500/40 bg-card/95 text-rose-200 shadow-rose-950/20";
          icon = <AlertCircle className="h-4 w-4 text-rose-400 shrink-0 mt-0.5" />;
        } else if (isSuccess) {
          borderClasses = "border-emerald-500/40 bg-card/95 text-emerald-200 shadow-emerald-950/20";
          icon = <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0 mt-0.5" />;
        } else if (isWarning) {
          borderClasses = "border-amber-500/40 bg-card/95 text-amber-200 shadow-amber-950/20";
          icon = <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" />;
        }

        return (
          <div
            key={t.id}
            className={`pointer-events-auto flex items-start gap-2.5 p-3 rounded-xl border backdrop-blur-md shadow-xl transition-all animate-in slide-in-from-bottom-2 duration-200 ${borderClasses}`}
            role="status"
          >
            {icon}
            <div className="flex-1 text-xs leading-relaxed font-medium break-words">
              {t.message}
            </div>
            <button
              type="button"
              onClick={() => dismissToast(t.id)}
              className="text-muted-foreground hover:text-foreground transition-colors p-0.5 rounded shrink-0 -mr-1 -mt-0.5"
              title="Cerrar notificación"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
