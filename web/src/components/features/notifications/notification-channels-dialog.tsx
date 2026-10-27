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
import { toast } from "sonner";

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
  const [telegramBotToken, setTelegramBotToken] = useState<string>("");
  const [telegramUserId, setTelegramUserId] = useState<string>("");
  const [umbralMinimo, setUmbralMinimo] = useState<number>(50);
  const [testingTelegram, setTestingTelegram] = useState<boolean>(false);
  const [linkingTelegram, setLinkingTelegram] = useState<boolean>(false);
  const [showAdvancedTelegram, setShowAdvancedTelegram] = useState<boolean>(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);

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
      setTelegramBotToken("");
      setUmbralMinimo(res.evaluacion?.umbral_minimo_puntuacion ?? 50);
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
      setTestResult(null);
    }
  }, [open]);

  const handleTestTelegram = async () => {
    setTestingTelegram(true);
    setTestResult(null);
    try {
      // Si el usuario ha escrito un nuevo token o ID, guardarlo primero
      if (telegramBotToken.trim() || telegramUserId.trim()) {
        await api.updateChannels({
          guardar_en_interfaz: true,
          enviar_telegram: true,
          telegram_bot_token: telegramBotToken.trim() || undefined,
          telegram_user_id: telegramUserId.trim() || undefined,
          telegram_adjuntar_docs: true,
          umbral_minimo_puntuacion: umbralMinimo,
        });
        await fetchSettings();
      }
      const res = await api.testTelegram();
      setTestResult({ success: true, message: res.message });
    } catch (err: any) {
      setTestResult({ success: false, message: err.message || "Error al enviar mensaje a Telegram." });
    } finally {
      setTestingTelegram(false);
    }
  };

  const handleAutoLinkTelegram = async () => {
    setLinkingTelegram(true);
    setTestResult(null);
    try {
      if (telegramBotToken.trim()) {
        await api.updateChannels({
          guardar_en_interfaz: true,
          enviar_telegram: true,
          telegram_bot_token: telegramBotToken.trim(),
          telegram_adjuntar_docs: true,
          umbral_minimo_puntuacion: umbralMinimo,
        });
      }
      const res = await api.autoLinkTelegram();
      setTelegramUserId(res.user_id);
      setTestResult({ success: true, message: res.message });
      await fetchSettings();
    } catch (err: any) {
      setTestResult({ success: false, message: err.message || "Error al vincular Telegram automáticamente." });
    } finally {
      setLinkingTelegram(false);
    }
  };

  const handleSaveChannels = async () => {
    setSaving(true);
    try {
      await api.updateChannels({
        guardar_en_interfaz: true, // Obligatorio por diseño
        enviar_telegram: enviarTelegram,
        telegram_bot_token: telegramBotToken.trim() || undefined,
        telegram_user_id: telegramUserId.trim(),
        telegram_adjuntar_docs: true, // Obligatorio por diseño
        umbral_minimo_puntuacion: umbralMinimo,
        infojobs_client_id: infojobsClientId.trim() || undefined,
        infojobs_client_secret: infojobsClientSecret.trim() || undefined,
      });
      toast.success("Preferencias y credenciales guardadas con éxito.");
      setSaveStatus("Preferencias y claves guardadas correctamente");
      setTimeout(() => {
        setSaveStatus(null);
        onOpenChange(false);
      }, 1000);
    } catch (err: any) {
      toast.error(`Error guardando preferencias: ${err.message || err}`);
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
                    className="text-3xs py-0"
                  >
                    {settings?.secrets_status.telegram_configured
                      ? "Configurado"
                      : settings?.secrets_status.telegram_token_present
                      ? "Token OK · Falta Chat ID"
                      : "Falta token .env"}
                  </Badge>
                </div>
                <p className="text-2xs text-muted-foreground">
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
              <div className="pt-2 border-t border-border/40 space-y-3">
                {/* Caso A: Si ya está configurado y vinculado */}
                {settings?.secrets_status.telegram_configured && !showAdvancedTelegram ? (
                  <div className="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2.5">
                        <div className="h-8 w-8 rounded-full bg-emerald-500/20 flex items-center justify-center shrink-0">
                          <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                        </div>
                        <div>
                          <div className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                            <span>Conectado con Telegram</span>
                            {settings.secrets_status.telegram_bot_username && (
                              <span className="text-3xs px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-mono">
                                @{settings.secrets_status.telegram_bot_username}
                              </span>
                            )}
                          </div>
                          <div className="text-3xs text-muted-foreground font-mono">
                            Chat ID: {telegramUserId}
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center justify-between pt-1 border-t border-emerald-500/15 text-3xs text-muted-foreground">
                      <span>Recibirás aquí las alertas y PDFs adaptados automáticamente.</span>
                      <button
                        type="button"
                        onClick={() => setShowAdvancedTelegram(true)}
                        className="text-primary hover:underline font-medium"
                      >
                        Cambiar bot o ID
                      </button>
                    </div>
                  </div>
                ) : (
                  /* Caso B: Configuración simplificada con 1 solo paso */
                  <div className="space-y-3">
                    {/* Token del Bot */}
                    <div className="space-y-1">
                      <div className="flex items-center justify-between">
                        <label htmlFor="modal-telegram-token" className="font-medium text-foreground text-xs flex items-center gap-1.5">
                          <KeyRound className="h-3.5 w-3.5 text-primary" />
                          1. Token de tu Bot de Telegram:
                        </label>
                        {settings?.secrets_status.telegram_token_present ? (
                          <span className="text-3xs text-emerald-400 font-mono">Configurado</span>
                        ) : (
                          <span className="text-3xs text-amber-400 font-mono">Pendiente</span>
                        )}
                      </div>
                      <Input
                        id="modal-telegram-token"
                        type="password"
                        placeholder={
                          settings?.secrets_status.telegram_token_present
                            ? "•••••••••••••••••••••••••••••••• (token guardado)"
                            : "Pega el token generado en @BotFather"
                        }
                        value={telegramBotToken}
                        onChange={(e) => setTelegramBotToken(e.target.value)}
                        className="text-xs h-8 font-mono bg-background"
                      />
                      <p className="text-3xs text-muted-foreground">
                        Crea tu bot gratis en Telegram hablando con <strong>@BotFather</strong> (escribe <code>/newbot</code>) y pega el token aquí.
                      </p>
                    </div>

                    {/* Vinculación con 1 Clic */}
                    <div className="p-3 rounded-xl bg-card border space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                          <Send className="h-3.5 w-3.5 text-primary" />
                          2. Vincular tu cuenta con 1 Clic
                        </span>
                        {settings?.secrets_status?.telegram_bot_username && (
                          <span className="text-3xs text-muted-foreground font-mono">
                            @{settings.secrets_status.telegram_bot_username}
                          </span>
                        )}
                      </div>
                      <p className="text-3xs text-muted-foreground leading-relaxed">
                        No necesitas buscar ningún ID numérico. Pulsa el botón para abrir tu bot en Telegram, haz clic en <strong>"Iniciar"</strong>, y pulsa <strong>Detectar</strong>.
                      </p>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1">
                        <a
                          href={settings?.secrets_status?.telegram_bot_username ? `https://t.me/${settings.secrets_status.telegram_bot_username}` : "#"}
                          target="_blank"
                          rel="noreferrer"
                          className="h-8 px-3 rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground text-xs font-medium flex items-center justify-center gap-1.5 transition-all shadow-sm"
                        >
                          <Send className="h-3.5 w-3.5" />
                          <span>Abrir bot en Telegram</span>
                          <ExternalLink className="h-3 w-3 ml-0.5 opacity-70" />
                        </a>

                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          onClick={handleAutoLinkTelegram}
                          disabled={linkingTelegram}
                          className="text-xs h-8 flex items-center justify-center gap-1.5 border border-border"
                        >
                          <UserCheck className={`h-3.5 w-3.5 ${linkingTelegram ? "animate-spin" : ""}`} />
                          <span>{linkingTelegram ? "Detectando..." : "Detectar vinculación"}</span>
                        </Button>
                      </div>
                    </div>

                    {/* Opción avanzada para quien desee escribir el ID manualmente */}
                    <div className="pt-1">
                      <details className="text-2xs text-muted-foreground group">
                        <summary className="cursor-pointer hover:text-foreground font-medium select-none">
                          ⚙️ Ajustes avanzados (introducir Chat ID a mano)
                        </summary>
                        <div className="mt-2 space-y-2 p-2.5 rounded-lg border bg-background/50">
                          <label htmlFor="modal-telegram-user-id" className="text-3xs text-foreground font-medium block">
                            Chat ID numérico personal:
                          </label>
                          <Input
                            id="modal-telegram-user-id"
                            type="text"
                            placeholder="Ej: 5978474268"
                            value={telegramUserId}
                            onChange={(e) => setTelegramUserId(e.target.value)}
                            className="text-xs h-8 font-mono bg-background"
                          />
                        </div>
                      </details>
                    </div>

                    {showAdvancedTelegram && settings?.secrets_status.telegram_configured && (
                      <div className="text-right">
                        <button
                          type="button"
                          onClick={() => setShowAdvancedTelegram(false)}
                          className="text-2xs text-muted-foreground hover:text-foreground underline"
                        >
                          Volver a vista conectada
                        </button>
                      </div>
                    )}
                  </div>
                )}

                {testResult && (
                  <div
                    className={`mt-2 p-2.5 rounded-lg text-2xs flex items-start gap-2 ${
                      testResult.success
                        ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
                        : "bg-destructive/10 text-destructive border border-destructive/30"
                    }`}
                  >
                    {testResult.success ? (
                      <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5 text-emerald-400" />
                    ) : (
                      <ExternalLink className="h-4 w-4 shrink-0 mt-0.5 text-destructive" />
                    )}
                    <span className="leading-relaxed">{testResult.message}</span>
                  </div>
                )}
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
                  className="text-3xs py-0"
                >
                  {settings?.secrets_status.infojobs_configured ? "API Conectada" : "Sin Claves"}
                </Badge>
              </div>
              <a
                href="https://developer.infojobs.net"
                target="_blank"
                rel="noreferrer"
                className="text-2xs text-primary hover:underline flex items-center gap-1"
              >
                <span>developer.infojobs.net</span>
                <ExternalLink className="h-3 w-3" />
              </a>
            </div>

            <p className="text-2xs text-muted-foreground">
              Introduce tus credenciales de desarrollador de InfoJobs para buscar ofertas oficiales sin restricciones de scraping.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 pt-1">
              <div className="space-y-1">
                <label className="text-2xs font-medium text-foreground">Client ID:</label>
                <Input
                  type="text"
                  placeholder="Ej: e82b13c..."
                  value={infojobsClientId}
                  onChange={(e) => setInfojobsClientId(e.target.value)}
                  className="text-xs h-8 font-mono bg-background"
                />
              </div>

              <div className="space-y-1">
                <label className="text-2xs font-medium text-foreground">
                  Client Secret:
                  {settings?.secrets_status.infojobs_secret_present && !infojobsClientSecret && (
                    <span className="text-3xs text-emerald-400 ml-1.5 font-normal">(Configurado)</span>
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
            <div className="flex justify-between text-3xs text-muted-foreground font-medium">
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
