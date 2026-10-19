"use client";

import React, { useState, useEffect } from "react";
import {
  Bell,
  Send,
  UserCheck,
  CheckCircle2,
  Save,
  RotateCw,
  KeyRound,
  ExternalLink,
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

  // Estados de Telegram
  const [enviarTelegram, setEnviarTelegram] = useState<boolean>(true);
  const [telegramUserId, setTelegramUserId] = useState<string>("");
  const [umbralMinimo, setUmbralMinimo] = useState<number>(65);

  // Estados de InfoJobs API
  const [infojobsClientId, setInfojobsClientId] = useState<string>("");
  const [infojobsClientSecret, setInfojobsClientSecret] = useState<string>("");

  const fetchSettings = async () => {
    try {
      setLoading(true);
      const res = await api.getSettings();
      setSettings(res);
      setEnviarTelegram(res.notificaciones.enviar_telegram ?? true);
      setTelegramUserId(
        res.secrets_status?.telegram_user_id ||
          res.notificaciones?.telegram?.allowed_user_id ||
          ""
      );
      setUmbralMinimo(res.evaluacion?.umbral_minimo_puntuacion ?? 65);
      setInfojobsClientId(res.secrets_status?.infojobs_client_id || "");
      setInfojobsClientSecret("");
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
        guardar_en_interfaz: true, // Obligatorio por diseño
        enviar_telegram: enviarTelegram,
        telegram_user_id: telegramUserId.trim(),
        telegram_adjuntar_docs: true, // Obligatorio por diseño
        umbral_minimo_puntuacion: umbralMinimo,
        infojobs_client_id: infojobsClientId.trim() || undefined,
        infojobs_client_secret: infojobsClientSecret.trim() || undefined,
      });
      setSaveStatus("Preferencias y claves guardadas correctamente");
      setTimeout(() => {
        setSaveStatus(null);
        onOpenChange(false);
      }, 1500);
    } catch (err: any) {
      alert(`Error guardando preferencias: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Preferencias de Notificación y Conexiones API"
      description="Gestiona las alertas automáticas de Telegram, tu umbral de afinidad IA y tus credenciales de la API oficial de InfoJobs."
      maxWidth="lg"
    >
      {loading ? (
        <div className="flex items-center justify-center py-10 gap-2 text-xs text-muted-foreground">
          <RotateCw className="h-4 w-4 animate-spin text-primary" />
          <span>Cargando configuración...</span>
        </div>
      ) : (
        <div className="space-y-4 pt-2 text-xs">
          {saveStatus && (
            <div className="p-2.5 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-2 text-xs animate-in fade-in">
              <CheckCircle2 className="h-4 w-4 shrink-0" />
              <span>{saveStatus}</span>
            </div>
          )}

          {/* Sección 1: Telegram */}
          <div className="space-y-3 p-3.5 rounded-xl border bg-card/60">
            <div className="flex items-start justify-between space-x-3">
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
                      ? "Token OK · Falta Chat ID"
                      : "Falta token .env"}
                  </Badge>
                </div>
                <p className="text-[11px] text-muted-foreground">
                  Recibe resúmenes matutinos y los documentos PDF de CV y carta generados directamente en tu chat privado.
                </p>
              </div>
              <Switch
                checked={enviarTelegram}
                onCheckedChange={setEnviarTelegram}
                id="switch-modal-telegram"
              />
            </div>

            {enviarTelegram && (
              <div className="pt-2 border-t border-border/40 space-y-1.5">
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
            )}
          </div>

          {/* Sección 2: InfoJobs API */}
          <div className="space-y-3 p-3.5 rounded-xl border bg-card/60">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <KeyRound className="h-4 w-4 text-amber-400" />
                <span className="font-semibold text-xs text-foreground">
                  API Oficial de InfoJobs
                </span>
                <Badge
                  variant={settings?.secrets_status.infojobs_configured ? "success" : "secondary"}
                  className="text-[10px] py-0"
                >
                  {settings?.secrets_status.infojobs_configured ? "API Conectada" : "Sin Claves"}
                </Badge>
              </div>
              <a
                href="https://developer.infojobs.net"
                target="_blank"
                rel="noreferrer"
                className="text-[11px] text-primary hover:underline flex items-center gap-1"
              >
                <span>developer.infojobs.net</span>
                <ExternalLink className="h-3 w-3" />
              </a>
            </div>

            <p className="text-[11px] text-muted-foreground">
              Introduce tus credenciales de desarrollador de InfoJobs para buscar ofertas oficiales sin restricciones de scraping.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 pt-1">
              <div className="space-y-1">
                <label className="text-[11px] font-medium text-foreground">Client ID:</label>
                <Input
                  type="text"
                  placeholder="Ej: e82b13c..."
                  value={infojobsClientId}
                  onChange={(e) => setInfojobsClientId(e.target.value)}
                  className="text-xs h-8 font-mono bg-background"
                />
              </div>

              <div className="space-y-1">
                <label className="text-[11px] font-medium text-foreground">
                  Client Secret:
                  {settings?.secrets_status.infojobs_secret_present && !infojobsClientSecret && (
                    <span className="text-[10px] text-emerald-400 ml-1.5 font-normal">(Configurado)</span>
                  )}
                </label>
                <Input
                  type="password"
                  placeholder={
                    settings?.secrets_status.infojobs_secret_present
                      ? "•••••••••••••••• (dejar en blanco para conservar)"
                      : "Introduce tu Client Secret"
                  }
                  value={infojobsClientSecret}
                  onChange={(e) => setInfojobsClientSecret(e.target.value)}
                  className="text-xs h-8 font-mono bg-background"
                />
              </div>
            </div>
          </div>

          {/* Sección 3: Puntuación mínima de afinidad */}
          <div className="p-3.5 rounded-xl border bg-card/60 space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-foreground">Puntuación mínima de afinidad para postular:</span>
              <span className="font-bold text-primary font-mono text-sm">{umbralMinimo} / 100</span>
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
            <div className="flex justify-between text-[10px] text-muted-foreground font-medium">
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
                  <span>Guardar Preferencias</span>
                </>
              )}
            </Button>
          </div>
        </div>
      )}
    </Dialog>
  );
}
