"use client";

import React, { useState, useEffect } from "react";
import {
  Bell,
  Globe,
  Send,
  UserCheck,
  CheckCircle2,
  Save,
  RotateCw,
} from "lucide-react";
import { Dialog } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { SettingsResponse, api } from "@/lib/api";

interface NotificationChannelsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function NotificationChannelsDialog({
  open,
  onOpenChange,
}: NotificationChannelsDialogProps) {
  const [settings, setSettings] = useState<SettingsResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [saveStatus, setSaveStatus] = useState<string | null>(null);

  // Estados de Canales
  const [guardarInterfaz, setGuardarInterfaz] = useState<boolean>(true);
  const [enviarTelegram, setEnviarTelegram] = useState<boolean>(true);
  const [telegramUserId, setTelegramUserId] = useState<string>("");
  const [adjuntarDocsTg, setAdjuntarDocsTg] = useState<boolean>(true);
  const [umbralMinimo, setUmbralMinimo] = useState<number>(65);

  const fetchSettings = async () => {
    try {
      setLoading(true);
      const res = await api.getSettings();
      setSettings(res);
      setGuardarInterfaz(res.notificaciones.guardar_en_interfaz ?? true);
      setEnviarTelegram(res.notificaciones.enviar_telegram ?? true);
      setTelegramUserId(
        res.secrets_status?.telegram_user_id ||
          res.notificaciones?.telegram?.allowed_user_id ||
          ""
      );
      setAdjuntarDocsTg(res.notificaciones.telegram?.adjuntar_documentos ?? true);
      setUmbralMinimo(res.evaluacion?.umbral_minimo_puntuacion ?? 65);
    } catch (e: any) {
      console.error("Error cargando configuración de canales:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open) {
      fetchSettings();
    }
  }, [open]);

  const handleSaveChannels = async () => {
    setSaving(true);
    try {
      await api.updateChannels({
        guardar_en_interfaz: guardarInterfaz,
        enviar_telegram: enviarTelegram,
        telegram_user_id: telegramUserId.trim() || undefined,
        telegram_adjuntar_docs: adjuntarDocsTg,
        umbral_minimo_puntuacion: umbralMinimo,
      });
      setSaveStatus("Canales de notificación guardados correctamente");
      setTimeout(() => {
        setSaveStatus(null);
        onOpenChange(false);
      }, 1500);
    } catch (err: any) {
      alert(`Error guardando canales: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Canales de Notificación y Preferencias"
      description="Activa o desactiva de forma desacoplada la persistencia en la interfaz web y las alertas automáticas de Telegram."
      maxWidth="lg"
    >
      {loading ? (
        <div className="flex items-center justify-center py-10 gap-2 text-xs text-muted-foreground">
          <RotateCw className="h-4 w-4 animate-spin text-primary" />
          <span>Cargando canales...</span>
        </div>
      ) : (
        <div className="space-y-4 pt-2 text-xs">
          {saveStatus && (
            <div className="p-2.5 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-2 text-xs animate-in fade-in">
              <CheckCircle2 className="h-4 w-4 shrink-0" />
              <span>{saveStatus}</span>
            </div>
          )}

          {/* Canal 1: Interfaz Web Local */}
          <div className="flex items-start justify-between space-x-3 p-3 rounded-lg border bg-muted/20">
            <div className="space-y-0.5">
              <div className="flex items-center gap-2">
                <Globe className="h-4 w-4 text-emerald-400" />
                <span className="font-semibold text-xs text-foreground">
                  Mostrar y conservar en la Interfaz Web
                </span>
              </div>
              <p className="text-[11px] text-muted-foreground">
                Guarda las candidaturas en SQLite y permite consultarlas en la pestaña Candidaturas (0 llamadas de red externas).
              </p>
            </div>
            <Switch
              checked={guardarInterfaz}
              onCheckedChange={setGuardarInterfaz}
              id="switch-modal-ui-saved"
            />
          </div>

          {/* Canal 2: Telegram */}
          <div className="flex items-start justify-between space-x-3 p-3 rounded-lg border bg-muted/20">
            <div className="space-y-0.5">
              <div className="flex items-center gap-2">
                <Send className="h-4 w-4 text-sky-400" />
                <span className="font-semibold text-xs text-foreground">
                  Enviar alertas por Telegram
                </span>
                <Badge
                  variant={settings?.secrets_status.telegram_configured ? "success" : "secondary"}
                  className="text-[10px] py-0"
                >
                  {settings?.secrets_status.telegram_configured
                    ? "Configurado"
                    : settings?.secrets_status.telegram_token_present
                    ? "Token OK · Falta ID"
                    : "Falta token"}
                </Badge>
              </div>
              <p className="text-[11px] text-muted-foreground">
                Envía resúmenes y alertas de empleo al usuario autorizado vía bot de Telegram.
              </p>
            </div>
            <Switch
              checked={enviarTelegram}
              onCheckedChange={setEnviarTelegram}
              id="switch-modal-telegram"
            />
          </div>

          {/* Opciones de Telegram si está activo */}
          {enviarTelegram && (
            <div className="pl-4 sm:pl-5 border-l-2 border-primary/40 space-y-3 bg-muted/10 p-3 rounded-r-lg">
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label htmlFor="modal-telegram-user-id" className="font-medium text-foreground text-xs flex items-center gap-1.5">
                    <UserCheck className="h-3.5 w-3.5 text-primary" />
                    ID de Usuario de Telegram (Chat ID):
                  </label>
                  {telegramUserId ? (
                    <span className="text-[10px] text-emerald-400 font-mono">ID: {telegramUserId}</span>
                  ) : (
                    <span className="text-[10px] text-amber-400 font-mono">Sin configurar</span>
                  )}
                </div>
                <Input
                  id="modal-telegram-user-id"
                  type="text"
                  placeholder="Ej: 123456789 (tu ID numérico personal)"
                  value={telegramUserId}
                  onChange={(e) => setTelegramUserId(e.target.value)}
                  className="text-xs h-8 font-mono bg-background"
                />
                <p className="text-[10px] text-muted-foreground leading-relaxed">
                  Para saber tu ID numérico, abre Telegram y pulsa Iniciar en el bot <strong>@userinfobot</strong> o envíale un mensaje a tu propio bot. Solo este ID recibirá las alertas.
                </p>
              </div>

              <div className="flex items-center justify-between pt-2 border-t border-border/40">
                <span className="text-foreground font-medium text-xs">
                  Adjuntar documentos PDF generados en Telegram:
                </span>
                <Switch
                  checked={adjuntarDocsTg}
                  onCheckedChange={setAdjuntarDocsTg}
                  id="switch-modal-attach-tg"
                />
              </div>
            </div>
          )}

          {/* Puntuación mínima de afinidad */}
          <div className="p-3 rounded-lg border bg-muted/10 space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="font-medium text-foreground">Puntuación mínima de afinidad:</span>
              <span className="font-bold text-primary font-mono">{umbralMinimo} / 100</span>
            </div>
            <input
              type="range"
              min="40"
              max="90"
              step="5"
              value={umbralMinimo}
              onChange={(e) => setUmbralMinimo(parseInt(e.target.value, 10))}
              className="w-full h-1.5 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
            />
            <div className="flex justify-between text-[10px] text-muted-foreground">
              <span>Flexible (40)</span>
              <span>Recomendado (65)</span>
              <span>Estricto (90)</span>
            </div>
          </div>

          {/* Botones de acción del Modal */}
          <div className="flex items-center justify-end gap-2 pt-3 border-t">
            <Button
              size="sm"
              variant="outline"
              onClick={() => onOpenChange(false)}
              className="h-8 text-xs"
            >
              Cerrar
            </Button>
            <Button
              size="sm"
              onClick={handleSaveChannels}
              disabled={saving}
              className="h-8 text-xs flex items-center gap-1.5 shadow-sm"
            >
              {saving ? (
                <>
                  <RotateCw className="h-3 w-3 animate-spin" />
                  <span>Guardando...</span>
                </>
              ) : (
                <>
                  <Save className="h-3 w-3" />
                  <span>Guardar Canales</span>
                </>
              )}
            </Button>
          </div>
        </div>
      )}
    </Dialog>
  );
}
