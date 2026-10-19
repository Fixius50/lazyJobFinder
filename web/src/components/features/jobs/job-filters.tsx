"use client";

import React from "react";
import { Search, SlidersHorizontal, MapPin, RotateCcw, Ban, Save } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { InfoTooltip } from "@/components/ui/info-tooltip";
import { APPLICATION_STATUSES, PORTAL_SOURCES } from "@/lib/constants";

interface JobFiltersProps {
  searchTerm: string;
  onSearchTermChange: (term: string) => void;
  locationTerm: string;
  onLocationTermChange: (term: string) => void;
  exclusionTerm?: string;
  onExclusionTermChange?: (term: string) => void;
  selectedSource: string;
  onSourceChange: (source: string) => void;
  selectedStatus: string;
  onStatusChange: (status: string) => void;
  selectedModality: string;
  onModalityChange: (modality: string) => void;
  minScore: number;
  onMinScoreChange: (score: number) => void;
  onSubmitSearch: (e: React.FormEvent) => void;
  onResetFilters?: () => void;
  onSaveCriteria?: () => void;
}

export function JobFilters({
  searchTerm,
  onSearchTermChange,
  locationTerm,
  onLocationTermChange,
  exclusionTerm = "",
  onExclusionTermChange,
  selectedSource,
  onSourceChange,
  selectedStatus,
  onStatusChange,
  selectedModality,
  onModalityChange,
  minScore,
  onMinScoreChange,
  onSubmitSearch,
  onResetFilters,
  onSaveCriteria,
}: JobFiltersProps) {
  // Color e indicador según la escala definida por el usuario
  const getScoreBadgeColor = (score: number) => {
    if (score >= 75) return "text-emerald-400 bg-emerald-500/10 border-emerald-500/20";
    if (score >= 50) return "text-blue-400 bg-blue-500/10 border-blue-500/20";
    if (score >= 25) return "text-amber-400 bg-amber-500/10 border-amber-500/20";
    return "text-muted-foreground bg-muted border-border/50";
  };

  const getScoreLabel = (score: number) => {
    if (score >= 100) return "≥ 100% · Seguro";
    if (score >= 75) return `≥ ${score}% · Óptima`;
    if (score >= 50) return `≥ ${score}% · Posible`;
    if (score >= 25) return `≥ ${score}% · Poco probable`;
    return "≥ 0% · Cualquiera";
  };

  const hasActiveFilters =
    Boolean(searchTerm) ||
    Boolean(locationTerm) ||
    Boolean(exclusionTerm) ||
    Boolean(selectedSource) ||
    Boolean(selectedStatus) ||
    Boolean(selectedModality) ||
    minScore > 0;

  return (
    <Card className="border bg-card/70 backdrop-blur-sm shadow-sm overflow-visible">
      <CardHeader className="pb-2 pt-3 px-3 sm:px-4 border-b border-border/40">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <SlidersHorizontal className="h-3.5 w-3.5 text-primary" />
            <CardTitle className="text-xs sm:text-sm font-semibold">Criterios y Filtros de Búsqueda</CardTitle>
            <InfoTooltip content="Configura los términos de búsqueda, ubicaciones, filtros de exclusión y parámetros de afinidad utilizados tanto en la visualización como en los conectores." />
          </div>
          {hasActiveFilters && onResetFilters && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={onResetFilters}
              className="h-6 px-1.5 text-[11px] text-muted-foreground hover:text-foreground flex items-center gap-1"
              title="Restablecer todos los filtros"
            >
              <RotateCcw className="h-3 w-3" />
              Limpiar
            </Button>
          )}
        </div>
      </CardHeader>

      <CardContent className="p-3 sm:p-4 space-y-3 overflow-visible">
        <form onSubmit={onSubmitSearch} className="space-y-3">
          {/* Términos de búsqueda / Puesto */}
          <div className="space-y-1">
            <label className="text-[11px] font-medium text-muted-foreground">Términos de búsqueda:</label>
            <div className="relative w-full">
              <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
              <Input
                type="text"
                placeholder="ej: Desarrollador Junior, Full Stack, React..."
                value={searchTerm}
                onChange={(e) => onSearchTermChange(e.target.value)}
                className="pl-8 text-xs h-8 w-full bg-background"
              />
            </div>
          </div>

          {/* Ubicaciones prioritarias / Ubicación */}
          <div className="space-y-1">
            <label className="text-[11px] font-medium text-muted-foreground flex items-center gap-1">
              <MapPin className="h-3 w-3 text-primary" />
              Ubicaciones prioritarias:
            </label>
            <div className="relative w-full">
              <Input
                type="text"
                list="world-locations"
                placeholder="ej: Spain, Madrid, Barcelona, Remoto..."
                value={locationTerm}
                onChange={(e) => onLocationTermChange(e.target.value)}
                className="text-xs h-8 w-full bg-background"
              />
              <datalist id="world-locations">
                <option value="España" />
                <option value="Spain" />
                <option value="Madrid" />
                <option value="Barcelona" />
                <option value="Valencia" />
                <option value="Sevilla" />
                <option value="Málaga" />
                <option value="Bilbao" />
                <option value="Galicia" />
                <option value="Zaragoza" />
                <option value="Remoto" />
                <option value="Teletrabajo" />
                <option value="Europa" />
                <option value="Internacional" />
                <option value="Reino Unido" />
                <option value="Alemania" />
                <option value="Francia" />
                <option value="Estados Unidos" />
                <option value="Latinoamérica" />
              </datalist>
            </div>
          </div>

          {/* Filtros de exclusión (descartar si contiene) */}
          <div className="space-y-1">
            <label className="text-[11px] font-medium text-muted-foreground flex items-center gap-1">
              <Ban className="h-3 w-3 text-destructive" />
              Filtros de exclusión (descartar si contiene):
            </label>
            <Input
              type="text"
              placeholder="ej: Senior, Lead, Architect, 5+ años..."
              value={exclusionTerm}
              onChange={(e) => onExclusionTermChange?.(e.target.value)}
              className="text-xs h-8 w-full bg-background"
            />
          </div>

          {/* Selectores de Modalidad, Portal y Estado */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-1 gap-2 pt-1 text-xs">
            {/* Modalidad de Trabajo */}
            <div className="space-y-1">
              <label className="text-[11px] font-medium text-muted-foreground">Modalidad:</label>
              <Select
                value={selectedModality}
                onChange={(e) => onModalityChange(e.target.value)}
                className="text-xs h-8 w-full bg-background"
              >
                <option value="">Cualquier modalidad</option>
                <option value="teletrabajo">Teletrabajo (100% Remoto)</option>
                <option value="hibrido">Híbrido (Remoto + Oficina)</option>
                <option value="presencial">Presencial en oficina</option>
              </Select>
            </div>

            {/* Portal de Empleo */}
            <div className="space-y-1">
              <label className="text-[11px] font-medium text-muted-foreground">Portal:</label>
              <Select
                value={selectedSource}
                onChange={(e) => onSourceChange(e.target.value)}
                className="text-xs h-8 w-full bg-background"
              >
                <option value="">Todos los portales</option>
                <option value="tecnoempleo">Tecnoempleo</option>
                <option value="infojobs">InfoJobs</option>
                <option value="linkedin">LinkedIn</option>
                <option value="indeed">Indeed</option>
                <option value="glassdoor">Glassdoor</option>
                <option value="google">Google Jobs</option>
                <option value="jobspy">JobSpy (Multi-portal)</option>
              </Select>
            </div>

            {/* Estado de Candidatura */}
            <div className="space-y-1">
              <label className="text-[11px] font-medium text-muted-foreground">Estado:</label>
              <Select
                value={selectedStatus}
                onChange={(e) => onStatusChange(e.target.value)}
                className="text-xs h-8 w-full bg-background"
              >
                <option value="">Todos los estados</option>
                {Object.entries(APPLICATION_STATUSES).map(([key, meta]) => (
                  <option key={key} value={key}>
                    {meta.label}
                  </option>
                ))}
              </Select>
            </div>
          </div>

          {/* Deslizante (Slider) Continuo de Afinidad Mínima (0 a 100%) */}
          <div className="pt-2 border-t border-border/40 space-y-1.5 overflow-visible">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground font-medium">
                <SlidersHorizontal className="h-3 w-3 text-primary" />
                <span>Afinidad IA mínima:</span>
              </div>
              <span
                className={`text-xs font-mono font-bold px-2 py-0.5 rounded-full border transition-colors ${getScoreBadgeColor(
                  minScore
                )}`}
              >
                {getScoreLabel(minScore)}
              </span>
            </div>

            {/* Contenedor del Slider con padding lateral seguro */}
            <div className="px-1 py-1 w-full overflow-visible">
              <input
                type="range"
                min="0"
                max="100"
                step="1"
                value={minScore}
                onChange={(e) => onMinScoreChange(parseInt(e.target.value, 10))}
                aria-label="Puntuación mínima de afinidad"
                className="w-full h-2 rounded-lg cursor-pointer accent-primary bg-muted hover:bg-muted/80 transition-all focus:outline-none"
              />
              {/* Botones de guía rápida de la escala */}
              <div className="flex justify-between text-[9px] text-muted-foreground/70 font-mono pt-1.5 select-none gap-0.5">
                <button
                  type="button"
                  onClick={() => onMinScoreChange(0)}
                  className={`transition-colors hover:text-foreground ${minScore === 0 ? "font-bold text-foreground" : ""}`}
                >
                  0%
                </button>
                <button
                  type="button"
                  onClick={() => onMinScoreChange(25)}
                  className={`transition-colors hover:text-foreground ${minScore === 25 ? "font-bold text-foreground" : ""}`}
                >
                  25%
                </button>
                <button
                  type="button"
                  onClick={() => onMinScoreChange(50)}
                  className={`transition-colors hover:text-foreground ${minScore === 50 ? "font-bold text-foreground" : ""}`}
                >
                  50%
                </button>
                <button
                  type="button"
                  onClick={() => onMinScoreChange(75)}
                  className={`transition-colors hover:text-foreground ${minScore === 75 ? "font-bold text-foreground" : ""}`}
                >
                  75%
                </button>
                <button
                  type="button"
                  onClick={() => onMinScoreChange(100)}
                  className={`transition-colors hover:text-foreground ${minScore === 100 ? "font-bold text-foreground" : ""}`}
                >
                  100%
                </button>
              </div>
            </div>
          </div>

          {/* Botones de Acción */}
          <div className="flex items-center gap-2 pt-1">
            <Button type="submit" size="sm" className="flex-1 h-8 text-xs font-medium shadow-sm">
              Aplicar Filtros
            </Button>
            {onSaveCriteria && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={onSaveCriteria}
                className="h-8 px-2.5 text-xs font-medium flex items-center gap-1 border-primary/40 hover:bg-primary/10 text-primary shrink-0"
                title="Guardar como criterios base en la configuración del conector"
              >
                <Save className="h-3.5 w-3.5" />
                <span>Guardar</span>
              </Button>
            )}
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
