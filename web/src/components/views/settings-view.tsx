"use client";

import React, { useEffect, useState } from "react";
import {
  Bell,
  Search,
  Trash2,
  ShieldAlert,
  Save,
  CheckCircle2,
  Send,
  Globe,
  RefreshCw,
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Dialog } from "@/components/ui/dialog";
import { SettingsResponse, api } from "@/lib/api";
import { CONFIRMATION_PHRASES } from "@/lib/constants";

export function SettingsView() {
  const [settings, setSettings] = useState<SettingsResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [saveStatus, setSaveStatus] = useState<string | null>(null);

  // Estados de Canales
  const [guardarInterfaz, setGuardarInterfaz] = useState<boolean>(true);
  const [enviarTelegram, setEnviarTelegram] = useState<boolean>(true);
  const [adjuntarDocsTg, setAdjuntarDocsTg] = useState<boolean>(true);
  const [umbralMinimo, setUmbralMinimo] = useState<number>(65);

  // Estados de Búsqueda
  const [terminosStr, setTerminosStr] = useState<string>("");
  const [ubicacionesStr, setUbicacionesStr] = useState<string>("");
  const [exclusionesStr, setExclusionesStr] = useState<string>("");
  const [antiguedadHoras, setAntiguedadHoras] = useState<number>(48);

  // Modales de Confirmación de Mantenimiento
  const [modalClearHistoryOpen, setModalClearHistoryOpen] = useState<boolean>(false);
  const [confirmPhraseHistory, setConfirmPhraseHistory] = useState<string>("");
  const [maintActionFeedback, setMaintActionFeedback] = useState<string | null>(null);

  const fetchSettings = async () => {
    try {
      const res = await api.getSettings();
      setSettings(res);
      setGuardarInterfaz(res.notificaciones.guardar_en_interfaz ?? true);
      setEnviarTelegram(res.notificaciones.enviar_telegram ?? true);
      setAdjuntarDocsTg(res.notificaciones.telegram?.adjuntar_documentos ?? true);
      setUmbralMinimo(res.evaluacion?.umbral_minimo_puntuacion ?? 65);

      setTerminosStr(res.busqueda.terminos?.join(", ") || "");
      setUbicacionesStr(res.busqueda.ubicaciones?.join(", ") || "");
      setExclusionesStr(res.busqueda.filtros_exclusion?.join(", ") || "");
      setAntiguedadHoras(res.busqueda.antiguedad_horas ?? 48);
    } catch (e: any) {
      console.error("Error al cargar configuración:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSettings();
  }, []);

  const handleSaveChannels = async () => {
    try {
      await api.updateChannels({
        guardar_en_interfaz: guardarInterfaz,
        enviar_telegram: enviarTelegram,
        telegram_adjuntar_docs: adjuntarDocsTg,
        umbral_minimo_puntuacion: umbralMinimo,
      });
      setSaveStatus("Canales de notificación guardados correctamente");
      setTimeout(() => setSaveStatus(null), 3000);
      await fetchSettings();
    } catch (err: any) {
      alert(`Error guardando canales: ${err.message}`);
    }
  };

  const handleSaveSearch = async () => {
    try {
      const terminos = terminosStr.split(",").map((t) => t.trim()).filter(Boolean);
      const ubicaciones = ubicacionesStr.split(",").map((u) => u.trim()).filter(Boolean);
      const filtros_exclusion = exclusionesStr.split(",").map((e) => e.trim()).filter(Boolean);

      await api.updateSearchConfig({
        terminos,
        ubicaciones,
        filtros_exclusion,
        antiguedad_horas: antiguedadHoras,
        limite_por_fuente: settings?.busqueda.limite_por_fuente || 15,
      });
      setSaveStatus("Criterios de búsqueda actualizados");
      setTimeout(() => setSaveStatus(null), 3000);
      await fetchSettings();
    } catch (err: any) {
      alert(`Error guardando búsqueda: ${err.message}`);
    }
  };

  const handleClearHistory = async () => {
    try {
      const res = await api.maintenanceClearHistory(confirmPhraseHistory);
      setModalClearHistoryOpen(false);
      setConfirmPhraseHistory("");
      setMaintActionFeedback(
        `${res.message} (Ofertas eliminadas: ${res.details?.jobs_deleted ?? 0}, Documentos: ${
          res.details?.documents_deleted ?? 0
        })`
      );
    } catch (e: any) {
      alert(`Fallo al borrar historial: ${e.message}`);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12 text-xs text-muted-foreground gap-2">
        <RefreshCw className="h-4 w-4 animate-spin text-primary" />
        <span>Cargando configuración...</span>
      </div>
    );
  }

  return (
    <div className="space-y-4 sm:space-y-6 w-full">
      {/* Encabezado fluido */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b">
        <div>
          <h2 className="text-lg sm:text-xl font-bold tracking-tight">Configuración y Canales</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Gestión independiente de almacenamiento local, bot de Telegram y mantenimiento del sistema.
          </p>
        </div>

        {saveStatus && (
          <Badge variant="success" className="h-8 text-xs flex items-center gap-1.5 self-start sm:self-auto">
            <CheckCircle2 className="h-3.5 w-3.5" /> {saveStatus}
          </Badge>
        )}
      </div>

      {maintActionFeedback && (
        <div className="p-3 rounded-lg bg-primary/10 text-primary border border-primary/20 text-xs flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <span>{maintActionFeedback}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
        {/* Sección 1: Canales de Notificación */}
        <div className="space-y-4 sm:space-y-6">
          <Card className="border bg-card/80 backdrop-blur-sm shadow-sm">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Bell className="h-4 w-4 text-primary" />
                  Canales de Notificación
                </CardTitle>
                <Button size="sm" onClick={handleSaveChannels} className="h-7 text-xs flex items-center gap-1">
                  <Save className="h-3 w-3" /> Guardar Canales
                </Button>
              </div>
              <CardDescription className="text-xs">
                Activa o desactiva de forma desacoplada la persistencia en interfaz y el bot de Telegram
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
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
                  id="switch-ui-saved"
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
                    <Badge variant={settings?.secrets_status.telegram_configured ? "success" : "secondary"} className="text-[10px] py-0">
                      {settings?.secrets_status.telegram_configured ? "Token presente" : "Falta token"}
                    </Badge>
                  </div>
                  <p className="text-[11px] text-muted-foreground">
                    Envía resúmenes y alertas de empleo al usuario autorizado vía bot de Telegram.
                  </p>
                </div>
                <Switch
                  checked={enviarTelegram}
                  onCheckedChange={setEnviarTelegram}
                  id="switch-telegram"
                />
              </div>

              {/* Opción secundaria: Adjuntar PDFs por Telegram */}
              {enviarTelegram && (
                <div className="pl-4 sm:pl-6 border-l-2 border-primary/40 space-y-3 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="text-foreground font-medium">
                      Adjuntar documentos PDF generados en Telegram:
                    </span>
                    <Switch
                      checked={adjuntarDocsTg}
                      onCheckedChange={setAdjuntarDocsTg}
                      id="switch-attach-tg"
                    />
                  </div>
                </div>
              )}

              {/* Umbral mínimo de puntuación */}
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
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Sección 2: Criterios de Búsqueda y Mantenimiento */}
        <div className="space-y-4 sm:space-y-6">
          <Card className="border bg-card/80 backdrop-blur-sm shadow-sm">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Search className="h-4 w-4 text-primary" />
                  Criterios de Búsqueda de Ofertas
                </CardTitle>
                <Button size="sm" onClick={handleSaveSearch} className="h-7 text-xs flex items-center gap-1">
                  <Save className="h-3 w-3" /> Guardar Filtros
                </Button>
              </div>
              <CardDescription className="text-xs">
                Parámetros utilizados por los conectores (separar con comas)
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3.5 text-xs">
              <div className="space-y-1">
                <label className="font-medium text-foreground">Términos de búsqueda:</label>
                <Input
                  value={terminosStr}
                  onChange={(e) => setTerminosStr(e.target.value)}
                  placeholder="ej: junior java, desarrollador java junior, dam"
                  className="text-xs"
                />
              </div>

              <div className="space-y-1">
                <label className="font-medium text-foreground">Ubicaciones prioritarias:</label>
                <Input
                  value={ubicacionesStr}
                  onChange={(e) => setUbicacionesStr(e.target.value)}
                  placeholder="ej: Spain, Madrid, Remoto"
                  className="text-xs"
                />
              </div>

              <div className="space-y-1">
                <label className="font-medium text-foreground">Filtros de exclusión (descartar si contiene):</label>
                <Input
                  value={exclusionesStr}
                  onChange={(e) => setExclusionesStr(e.target.value)}
                  placeholder="ej: senior, lead, arquitecto, 5 años"
                  className="text-xs"
                />
              </div>
            </CardContent>
          </Card>

          {/* Mantenimiento Seguro */}
          <Card className="border border-destructive/20 bg-destructive/5 shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm text-destructive flex items-center gap-2">
                <ShieldAlert className="h-4 w-4" />
                Mantenimiento y Purga del Sistema
              </CardTitle>
              <CardDescription className="text-xs">
                Acciones seguras protegidas por frases de confirmación exacta
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 p-3 rounded-lg border bg-background/50">
                <div>
                  <h4 className="font-semibold text-xs text-foreground">Borrar Historial de Ofertas</h4>
                  <p className="text-[11px] text-muted-foreground">
                    Vacía las ofertas y PDFs generados. Tu perfil y configuración se conservan.
                  </p>
                </div>
                <Button
                  size="sm"
                  variant="destructive"
                  onClick={() => setModalClearHistoryOpen(true)}
                  className="text-xs h-8 shrink-0"
                >
                  <Trash2 className="h-3.5 w-3.5 mr-1" />
                  Vaciar
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Modal Confirmación Borrar Historial */}
      <Dialog
        open={modalClearHistoryOpen}
        onOpenChange={setModalClearHistoryOpen}
        title="Confirmar Limpieza de Historial"
        description="Esta acción eliminará todas las ofertas registradas y los PDFs de CVs/cartas generados."
      >
        <div className="space-y-4 text-xs">
          <p className="text-muted-foreground">
            Escribe exactamente la siguiente frase para confirmar:
          </p>
          <div className="p-2 rounded bg-muted font-mono font-bold text-center select-all">
            {CONFIRMATION_PHRASES.clear_history}
          </div>
          <Input
            value={confirmPhraseHistory}
            onChange={(e) => setConfirmPhraseHistory(e.target.value)}
            placeholder="Escribe la frase aquí..."
            className="text-xs"
          />
          <div className="flex justify-end gap-2 pt-2">
            <Button size="sm" variant="outline" onClick={() => setModalClearHistoryOpen(false)}>
              Cancelar
            </Button>
            <Button
              size="sm"
              variant="destructive"
              disabled={confirmPhraseHistory !== CONFIRMATION_PHRASES.clear_history}
              onClick={handleClearHistory}
            >
              Borrar Historial
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  );
}
