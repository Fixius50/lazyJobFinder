"use client";

import React, { useEffect, useState } from "react";
import {
  Settings,
  Bell,
  Search,
  Trash2,
  AlertTriangle,
  ShieldAlert,
  Save,
  CheckCircle2,
  Square,
  ShieldCheck,
  Send,
  Globe,
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Dialog } from "@/components/ui/dialog";
import { SettingsResponse, api } from "@/lib/api";
import { CONFIRMATION_PHRASES } from "@/lib/constants";

export default function SettingsPage() {
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

  const [modalDownOpen, setModalDownOpen] = useState<boolean>(false);
  const [removeVolumesCheck, setRemoveVolumesCheck] = useState<boolean>(false);
  const [confirmPhraseDown, setConfirmPhraseDown] = useState<string>("");

  const [maintActionFeedback, setMaintActionFeedback] = useState<string | null>(null);

  const fetchSettings = async () => {
    try {
      const res = await api.getSettings();
      setSettings(res);
      setGuardarInterfaz(res.notificaciones.guardar_en_interfaz ?? true);
      setEnviarTelegram(res.notificaciones.enviar_telegram ?? true);
      setAdjuntarDocsTg(res.notificaciones.telegram?.adjuntar_documentos ?? true);
      setUmbralMinimo(res.evaluacion.umbral_minimo_puntuacion ?? 65);

      setTerminosStr((res.busqueda.terminos || []).join(", "));
      setUbicacionesStr((res.busqueda.ubicaciones || []).join(", "));
      setExclusionesStr((res.busqueda.filtros_exclusion || []).join(", "));
      setAntiguedadHoras(res.busqueda.antiguedad_horas || 48);
    } catch (err: any) {
      console.error("Error al cargar configuraciones:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSettings();
  }, []);

  const handleSaveChannels = async () => {
    try {
      setSaveStatus("Guardando canales...");
      await api.updateChannels({
        guardar_en_interfaz: guardarInterfaz,
        enviar_telegram: enviarTelegram,
        telegram_adjuntar_docs: adjuntarDocsTg,
        umbral_minimo_puntuacion: umbralMinimo,
      });
      setSaveStatus("Canales actualizados correctamente en settings.yaml");
      setTimeout(() => setSaveStatus(null), 3000);
      await fetchSettings();
    } catch (err: any) {
      alert(`Error guardando canales: ${err.message}`);
      setSaveStatus(null);
    }
  };

  const handleSaveSearchConfig = async () => {
    try {
      setSaveStatus("Guardando parámetros de búsqueda...");
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
      setSaveStatus("Configuración de búsqueda actualizada");
      setTimeout(() => setSaveStatus(null), 3000);
      await fetchSettings();
    } catch (err: any) {
      alert(`Error guardando búsqueda: ${err.message}`);
      setSaveStatus(null);
    }
  };

  const handleStopServices = async () => {
    if (!confirm("¿Detener los servicios de forma ordenada? Los datos y contenedores se conservarán.")) {
      return;
    }
    try {
      const res = await api.maintenanceStop();
      setMaintActionFeedback(res.message);
    } catch (e: any) {
      alert(`Error: ${e.message}`);
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

  const handleDownContainers = async () => {
    try {
      const res = await api.maintenanceDown(removeVolumesCheck, confirmPhraseDown);
      setModalDownOpen(false);
      setConfirmPhraseDown("");
      setRemoveVolumesCheck(false);
      setMaintActionFeedback(res.message);
    } catch (e: any) {
      alert(`Fallo al eliminar contenedores: ${e.message}`);
    }
  };

  if (loading) {
    return <div className="py-12 text-center text-xs text-muted-foreground">Cargando configuración...</div>;
  }

  return (
    <div className="space-y-6">
      {/* Encabezado */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b">
        <div>
          <h2 className="text-xl font-bold tracking-tight">Configuración y Canales de Notificación</h2>
          <p className="text-xs text-muted-foreground mt-1">
            Gestión independiente de almacenamiento local, bot de Telegram y mantenimiento del sistema.
          </p>
        </div>

        {saveStatus && (
          <Badge variant="success" className="h-7 text-xs flex items-center gap-1.5 animate-in fade-in">
            <CheckCircle2 className="h-3.5 w-3.5" /> {saveStatus}
          </Badge>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Sección 1: Canales de Notificación Independientes */}
        <div className="space-y-6">
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Bell className="h-4 w-4 text-primary" />
                  Canales de Notificación Independientes
                </CardTitle>
                <Button size="sm" onClick={handleSaveChannels} className="h-7 text-xs flex items-center gap-1">
                  <Save className="h-3 w-3" /> Guardar Canales
                </Button>
              </div>
              <CardDescription>
                Activa o desactiva de forma desacoplada la persistencia en interfaz y el bot de Telegram
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              {/* Canal 1: Interfaz Web Local */}
              <div className="flex items-start justify-between space-x-3 p-3 rounded-lg border bg-muted/20">
                <div className="space-y-0.5">
                  <div className="flex items-center gap-2">
                    <Globe className="h-4 w-4 text-emerald-500" />
                    <span className="font-semibold text-xs text-foreground">
                      Mostrar y conservar en la Interfaz Web
                    </span>
                  </div>
                  <p className="text-[11px] text-muted-foreground">
                    Guarda las candidaturas en SQLite y permite consultarlas en la pestaña Candidaturas.
                    Opera con 0 llamadas de red externas.
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
                    <Send className="h-4 w-4 text-sky-500" />
                    <span className="font-semibold text-xs text-foreground">
                      Enviar alertas por Telegram
                    </span>
                    <Badge variant={settings?.secrets_status.telegram_configured ? "success" : "secondary"} className="text-[10px] py-0">
                      {settings?.secrets_status.telegram_configured ? "Token presente" : "Falta token en .env"}
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
                <div className="pl-6 border-l-2 border-primary/40 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-foreground font-medium">
                      Adjuntar documentos PDF generados en Telegram:
                    </span>
                    <Switch
                      checked={adjuntarDocsTg}
                      onCheckedChange={setAdjuntarDocsTg}
                      id="switch-telegram-docs"
                    />
                  </div>

                  {/* Advertencia de Privacidad Explícita */}
                  <div className="p-3 bg-amber-500/10 border border-amber-500/25 rounded-md text-[11px] text-amber-700 dark:text-amber-400 space-y-1">
                    <div className="flex items-center gap-1.5 font-bold">
                      <ShieldAlert className="h-4 w-4 shrink-0" />
                      <span>Nota de Privacidad y Red</span>
                    </div>
                    <p className="leading-relaxed">
                      El envío de documentos por Telegram transmite los archivos del CV y carta a la
                      infraestructura externa de Telegram. Si deseas que los archivos permanezcan estrictamente
                      locales, desactiva esta opción o mantén únicamente activo el canal de Interfaz Web.
                    </p>
                  </div>
                </div>
              )}

              {/* Umbral de puntuación */}
              <div className="space-y-1.5 pt-2 border-t">
                <div className="flex justify-between items-center">
                  <label className="text-xs font-medium text-foreground">
                    Umbral mínimo de puntuación para generar documentos (0-100):
                  </label>
                  <span className="font-mono text-xs font-bold text-primary">{umbralMinimo}</span>
                </div>
                <input
                  type="range"
                  min="30"
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

        {/* Sección 2: Términos y Parámetros de Búsqueda */}
        <div className="space-y-6">
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Search className="h-4 w-4 text-primary" />
                  Parámetros del Motor de Búsqueda
                </CardTitle>
                <Button size="sm" onClick={handleSaveSearchConfig} className="h-7 text-xs flex items-center gap-1">
                  <Save className="h-3 w-3" /> Guardar Términos
                </Button>
              </div>
              <CardDescription>
                Consultas enviadas a Tecnoempleo RSS, InfoJobs y JobSpy (separadas por coma)
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 text-xs">
              <div className="space-y-1">
                <label className="font-medium text-foreground">Términos de búsqueda:</label>
                <Input
                  value={terminosStr}
                  onChange={(e) => setTerminosStr(e.target.value)}
                  placeholder="Junior Java, Full Stack Junior, Desarrollador DAM..."
                  className="text-xs"
                />
              </div>

              <div className="space-y-1">
                <label className="font-medium text-foreground">Ubicaciones y Modalidad:</label>
                <Input
                  value={ubicacionesStr}
                  onChange={(e) => setUbicacionesStr(e.target.value)}
                  placeholder="Spain, Remoto, Madrid, Barcelona..."
                  className="text-xs"
                />
              </div>

              <div className="space-y-1">
                <label className="font-medium text-foreground">Palabras clave de exclusión (Filtro determinista):</label>
                <Input
                  value={exclusionesStr}
                  onChange={(e) => setExclusionesStr(e.target.value)}
                  placeholder="Senior, Lead, Principal, 5+ años..."
                  className="text-xs"
                />
              </div>

              <div className="space-y-1">
                <label className="font-medium text-foreground">Antigüedad máxima de ofertas (horas):</label>
                <Input
                  type="number"
                  min="6"
                  max="168"
                  value={antiguedadHoras}
                  onChange={(e) => setAntiguedadHoras(parseInt(e.target.value, 10))}
                  className="text-xs w-28"
                />
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Sección 3: Mantenimiento, Apagado y Operaciones Destructivas */}
      <Card className="border-destructive/30">
        <CardHeader className="pb-3 border-b">
          <div className="flex items-center gap-2 text-destructive">
            <AlertTriangle className="h-4 w-4" />
            <CardTitle className="text-sm">Mantenimiento y Ciclo de Vida del Sistema</CardTitle>
          </div>
          <CardDescription>
            Operaciones de apagado y limpieza selectiva. Las acciones destructivas requieren confirmación explícita.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-4 space-y-4">
          {maintActionFeedback && (
            <div className="p-3 bg-primary/10 border border-primary/20 rounded-md text-xs text-primary font-medium">
              {maintActionFeedback}
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {/* 1. Detener servicios ordinariamente */}
            <div className="border rounded-lg p-3 bg-card space-y-2 flex flex-col justify-between">
              <div>
                <span className="font-semibold text-xs text-foreground block">
                  1. Detener Servicios (docker compose stop)
                </span>
                <p className="text-[11px] text-muted-foreground mt-1">
                  Apagado seguro de los contenedores sin borrar imágenes ni datos.
                </p>
              </div>
              <Button
                size="sm"
                variant="outline"
                onClick={handleStopServices}
                className="w-full text-xs h-8 flex items-center gap-1.5"
              >
                <Square className="h-3.5 w-3.5" /> Detener Servicios
              </Button>
            </div>

            {/* 2. Eliminar Contenedores (conservando volúmenes) */}
            <div className="border rounded-lg p-3 bg-card space-y-2 flex flex-col justify-between">
              <div>
                <span className="font-semibold text-xs text-foreground block">
                  2. Eliminar Contenedores (docker compose down)
                </span>
                <p className="text-[11px] text-muted-foreground mt-1">
                  Elimina los contenedores conservando la base de datos y los modelos de IA.
                </p>
              </div>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setModalDownOpen(true)}
                className="w-full text-xs h-8 hover:text-destructive"
              >
                Eliminar Contenedores...
              </Button>
            </div>

            {/* 3. Borrar Historial de Candidaturas */}
            <div className="border border-destructive/30 rounded-lg p-3 bg-destructive/5 space-y-2 flex flex-col justify-between">
              <div>
                <span className="font-semibold text-xs text-destructive block">
                  3. Purgar Historial de Candidaturas
                </span>
                <p className="text-[11px] text-muted-foreground mt-1">
                  Borra las ofertas, evaluaciones y documentos de SQLite conservando los logs.
                </p>
              </div>
              <Button
                size="sm"
                variant="destructive"
                onClick={() => setModalClearHistoryOpen(true)}
                className="w-full text-xs h-8 flex items-center gap-1.5"
              >
                <Trash2 className="h-3.5 w-3.5" /> Borrar Historial...
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Diálogo de Confirmación: Borrar Historial */}
      <Dialog
        open={modalClearHistoryOpen}
        onOpenChange={setModalClearHistoryOpen}
        title="Confirmación: Purgar Historial de Candidaturas"
        description="Esta acción eliminará todas las ofertas, evaluaciones y archivos generados almacenados en SQLite."
        maxWidth="md"
        footer={
          <>
            <Button size="sm" variant="outline" onClick={() => setModalClearHistoryOpen(false)}>
              Cancelar
            </Button>
            <Button
              size="sm"
              variant="destructive"
              disabled={confirmPhraseHistory !== CONFIRMATION_PHRASES.clear_history}
              onClick={handleClearHistory}
            >
              Confirmar Borrado
            </Button>
          </>
        }
      >
        <div className="space-y-3 text-xs">
          <p className="text-muted-foreground">
            Para evitar pérdidas accidentales de datos, escribe exactamente{" "}
            <code className="bg-muted px-1.5 py-0.5 rounded font-mono font-bold text-destructive">
              {CONFIRMATION_PHRASES.clear_history}
            </code>{" "}
            a continuación:
          </p>
          <Input
            value={confirmPhraseHistory}
            onChange={(e) => setConfirmPhraseHistory(e.target.value)}
            placeholder={`Escribe ${CONFIRMATION_PHRASES.clear_history}`}
            className="font-mono text-xs"
          />
        </div>
      </Dialog>

      {/* Diálogo de Confirmación: Eliminar Contenedores */}
      <Dialog
        open={modalDownOpen}
        onOpenChange={setModalDownOpen}
        title="Eliminar Contenedores Docker"
        description="Selecciona el alcance de la operación de apagado de contenedores."
        maxWidth="md"
        footer={
          <>
            <Button size="sm" variant="outline" onClick={() => setModalDownOpen(false)}>
              Cancelar
            </Button>
            <Button
              size="sm"
              variant={removeVolumesCheck ? "destructive" : "default"}
              disabled={
                removeVolumesCheck
                  ? confirmPhraseDown !== CONFIRMATION_PHRASES.destroy_volumes
                  : confirmPhraseDown !== CONFIRMATION_PHRASES.down_containers
              }
              onClick={handleDownContainers}
            >
              {removeVolumesCheck ? "Destruir Contenedores y Volúmenes" : "Eliminar Contenedores"}
            </Button>
          </>
        }
      >
        <div className="space-y-4 text-xs">
          <div className="p-3 bg-muted/40 rounded-lg space-y-2 border">
            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                id="check-remove-volumes"
                checked={removeVolumesCheck}
                onChange={(e) => setRemoveVolumesCheck(e.target.checked)}
                className="rounded accent-destructive"
              />
              <label htmlFor="check-remove-volumes" className="font-semibold text-foreground">
                Eliminar también los volúmenes persistentes (-v)
              </label>
            </div>
            <p className="text-[11px] text-muted-foreground pl-5">
              {removeVolumesCheck ? (
                <span className="text-destructive font-medium block">
                  ⚠️ PELIGRO: Esto borrará los modelos de IA descargados en Ollama y los datos persistentes.
                </span>
              ) : (
                "Recomendado: Los volúmenes se conservarán y los modelos de IA no tendrán que volver a descargarse."
              )}
            </p>
          </div>

          <div className="space-y-1.5">
            <p className="text-muted-foreground">
              Escribe exactamente{" "}
              <code className="bg-muted px-1.5 py-0.5 rounded font-mono font-bold text-foreground">
                {removeVolumesCheck ? CONFIRMATION_PHRASES.destroy_volumes : CONFIRMATION_PHRASES.down_containers}
              </code>:
            </p>
            <Input
              value={confirmPhraseDown}
              onChange={(e) => setConfirmPhraseDown(e.target.value)}
              placeholder="Escribe la frase requerida"
              className="font-mono text-xs"
            />
          </div>
        </div>
      </Dialog>
    </div>
  );
}
