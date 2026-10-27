"use client";

import React, { useState, useMemo } from "react";
import {
  SlidersHorizontal,
  MapPin,
  RotateCcw,
  ChevronDown,
  ChevronUp,
  Building2,
  Briefcase,
  GraduationCap,
  Clock,
  FileText,
  DollarSign,
  Globe,
  Sparkles,
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import type { FilterFacetsResponse, FacetItem, FilterState } from "@/lib/api";

export const EXPERIENCE_STEPS = [
  { step: 0, years: 0, label: "Sin especificar" },
  { step: 1, years: 0.5, label: "Junior / Prácticas (< 1 año)" },
  { step: 2, years: 1, label: "Al menos 1 año" },
  { step: 3, years: 2, label: "Al menos 2 años" },
  { step: 4, years: 3, label: "Al menos 3 años" },
  { step: 5, years: 5, label: "5+ años (Senior / Lead)" },
];

export const SALARY_STEPS = [
  { step: 0, value: 0, label: "Sin especificar" },
  { step: 1, value: 15000, label: "≥ 15.000 / año" },
  { step: 2, value: 20000, label: "≥ 20.000 / año" },
  { step: 3, value: 25000, label: "≥ 25.000 / año" },
  { step: 4, value: 30000, label: "≥ 30.000 / año" },
  { step: 5, value: 40000, label: "≥ 40.000 / año" },
  { step: 6, value: 50000, label: "≥ 50.000 / año" },
  { step: 7, value: 65000, label: "≥ 65.000 / año" },
  { step: 8, value: 80000, label: "≥ 80.000+ / año" },
];

export interface JobFiltersProps {
  facets?: FilterFacetsResponse | null;
  filters: FilterState;
  onFilterChange: <K extends keyof FilterState>(key: K, value: FilterState[K]) => void;
  onSubmitSearch: (e: React.FormEvent) => void;
  onResetFilters?: () => void;
  onSaveCriteria?: () => void;
}

/** Componente compacto para cada grupo de facetas dinámicas (menos código, cero redundancias) */
function FacetSection({
  title,
  icon,
  items,
  selected,
  onToggleItem,
  onClear,
  isOpen,
  onToggleOpen,
}: {
  title: string;
  icon: React.ReactNode;
  items: FacetItem[];
  selected: string[];
  onToggleItem: (id: string) => void;
  onClear: () => void;
  isOpen: boolean;
  onToggleOpen: () => void;
}) {
  return (
    <div className="space-y-1.5 pt-2 border-t border-border/30">
      <div
        onClick={onToggleOpen}
        className="flex items-center justify-between cursor-pointer py-1 select-none hover:text-foreground text-muted-foreground transition-colors"
      >
        <div className="flex items-center gap-1.5 text-xs font-semibold text-foreground">
          {icon}
          <span>{title}</span>
        </div>
        <div className="flex items-center gap-1.5">
          {selected.length > 0 && (
            <div className="flex items-center gap-1">
              <span className="text-3xs font-mono px-1.5 py-0.5 rounded-full bg-primary/20 text-primary font-bold">
                {selected.length}
              </span>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onClear();
                }}
                className="text-3xs text-muted-foreground hover:text-foreground px-1"
                title={`Limpiar filtro de ${title}`}
              >
                ×
              </button>
            </div>
          )}
          {isOpen ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
        </div>
      </div>

      {isOpen && (
        <div className="space-y-1 pl-1 max-h-44 overflow-y-auto pr-1">
          {items.length === 0 ? (
            <div className="text-2xs text-muted-foreground/60 py-1 pl-1 italic">
              Sin opciones registradas aún
            </div>
          ) : (
            items.map((item) => {
              const isChecked = selected.includes(item.id);
              return (
                <label
                  key={item.id}
                  className="flex items-center justify-between text-xs cursor-pointer select-none py-0.5 text-muted-foreground hover:text-foreground transition-colors group"
                >
                  <div className="flex items-center gap-2 min-w-0 pr-1">
                    <input
                      type="checkbox"
                      checked={isChecked}
                      onChange={() => onToggleItem(item.id)}
                      className="accent-primary h-3.5 w-3.5 rounded shrink-0 cursor-pointer"
                    />
                    <span className={`truncate ${isChecked ? "font-semibold text-foreground" : ""}`}>
                      {item.label}
                    </span>
                  </div>
                  {item.count !== undefined && (
                    <span className="text-3xs font-mono text-muted-foreground/70 shrink-0 px-1 rounded bg-muted/40 group-hover:bg-muted/80">
                      {item.count}
                    </span>
                  )}
                </label>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}

export function JobFilters({
  facets,
  filters,
  onFilterChange,
  onSubmitSearch,
  onResetFilters,
  onSaveCriteria,
}: JobFiltersProps) {
  const {
    searchTerm,
    exclusionTerm,
    locationName,
    isAllLocations,
    selectedModalities,
    selectedCategories,
    selectedEducations,
    minExperienceStep,
    minSalaryStep,
    selectedSchedules,
    selectedContractTypes,
    selectedSource,
    selectedStatus,
    minScore,
    timeRange = "all",
  } = filters;

  const [openSections, setOpenSections] = useState<Record<string, boolean>>({
    modalidad: true,
    categoria: false,
    formacion: false,
    jornada: false,
    contrato: false,
    avanzados: false,
  });

  const toggleSection = (section: string) => {
    setOpenSections((prev) => ({ ...prev, [section]: !prev[section] }));
  };

  const toggleArrayItem = <K extends "selectedModalities" | "selectedCategories" | "selectedEducations" | "selectedSchedules" | "selectedContractTypes">(
    key: K,
    item: string
  ) => {
    const list = filters[key];
    if (list.includes(item)) {
      onFilterChange(key, list.filter((x) => x !== item) as FilterState[K]);
    } else {
      onFilterChange(key, [...list, item] as FilterState[K]);
    }
  };

  // Opciones adaptadas dinámicamente según las ofertas reales en SQLite
  const dynamicSources = facets?.sources && facets.sources.length > 0 ? facets.sources : [];
  const dynamicModalities = facets?.modalities && facets.modalities.length > 0 ? facets.modalities : [];
  const dynamicCategories = facets?.categories && facets.categories.length > 0 ? facets.categories : [];
  const dynamicEducations = facets?.educations && facets.educations.length > 0 ? facets.educations : [];
  const dynamicSchedules = facets?.schedules && facets.schedules.length > 0 ? facets.schedules : [];
  const dynamicContracts = facets?.contract_types && facets.contract_types.length > 0 ? facets.contract_types : [];
  const dynamicLocations = facets?.top_locations || [];

  const hasActiveFilters =
    Boolean(searchTerm) ||
    Boolean(exclusionTerm) ||
    !isAllLocations ||
    selectedModalities.length > 0 ||
    selectedCategories.length > 0 ||
    selectedEducations.length > 0 ||
    minExperienceStep > 0 ||
    minSalaryStep > 0 ||
    selectedSchedules.length > 0 ||
    selectedContractTypes.length > 0 ||
    Boolean(selectedSource) ||
    Boolean(selectedStatus) ||
    minScore > 0;

  const currentExpLabel = EXPERIENCE_STEPS[minExperienceStep]?.label || "Sin especificar";
  const salaryCurrency = facets?.salary_stats?.currency || "€";
  const currentSalaryLabel = useMemo(() => {
    if (minSalaryStep === 0) return "Sin especificar";
    const step = SALARY_STEPS[minSalaryStep];
    if (!step) return "Sin especificar";
    return `≥ ${step.value.toLocaleString("es-ES")} ${salaryCurrency}/año`;
  }, [minSalaryStep, salaryCurrency]);

  return (
    <Card className="border bg-card/80 backdrop-blur-sm shadow-sm overflow-hidden">
      <CardHeader className="pb-2 pt-3 px-3 sm:px-4 border-b border-border/40">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <SlidersHorizontal className="h-4 w-4 text-primary" />
            <CardTitle className="text-xs sm:text-sm font-semibold">Filtros Dinámicos</CardTitle>
            {facets?.total_jobs !== undefined && (
              <span className="text-3xs font-mono text-muted-foreground">({facets.total_jobs} ofertas)</span>
            )}
          </div>

          {hasActiveFilters && onResetFilters && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={onResetFilters}
              className="h-6 px-1.5 text-2xs text-muted-foreground hover:text-foreground flex items-center gap-1"
              title="Restablecer todos los filtros"
            >
              <RotateCcw className="h-3 w-3" />
              <span>Limpiar</span>
            </Button>
          )}
        </div>
      </CardHeader>

      <CardContent className="p-3 sm:p-4 space-y-3">
        <form onSubmit={onSubmitSearch} className="space-y-3">
          {/* LUGAR Y UBICACIÓN INTEGRADA DESDE SQLITE */}
          <div className="space-y-1.5 pt-0.5">
            <div className="flex items-center justify-between">
              <label className="text-2xs font-semibold text-foreground flex items-center gap-1.5">
                <MapPin className="h-3.5 w-3.5 text-primary" />
                <span>Ubicación</span>
              </label>

              <button
                type="button"
                onClick={() => {
                  onFilterChange("isAllLocations", true);
                  onFilterChange("locationName", "");
                }}
                className={`text-3xs px-2 py-0.5 rounded border transition-colors flex items-center gap-1 ${
                  isAllLocations
                    ? "bg-primary/15 border-primary/40 text-primary font-medium"
                    : "text-muted-foreground hover:text-foreground border-transparent hover:bg-muted/50"
                }`}
              >
                <Globe className="h-3 w-3" />
                <span>Todas</span>
              </button>
            </div>

            {/* Chips de ubicaciones reales extraídas de la base de datos */}
            {dynamicLocations.length > 0 ? (
              <div className="flex flex-wrap gap-1 pt-0.5 max-h-32 overflow-y-auto pr-0.5">
                {dynamicLocations.map((loc) => {
                  const isSelected = !isAllLocations && locationName.toLowerCase() === loc.name.toLowerCase();
                  return (
                    <button
                      key={loc.name}
                      type="button"
                      onClick={() => {
                        if (isSelected) {
                          onFilterChange("isAllLocations", true);
                          onFilterChange("locationName", "");
                        } else {
                          onFilterChange("locationName", loc.name);
                          onFilterChange("isAllLocations", false);
                        }
                      }}
                      className={`text-3xs px-2 py-0.5 rounded-full border transition-all flex items-center gap-1 ${
                        isSelected
                          ? "bg-primary text-primary-foreground border-primary font-medium shadow-xs"
                          : "bg-muted/40 hover:bg-muted border-border/40 text-muted-foreground hover:text-foreground"
                      }`}
                    >
                      <span>{loc.name}</span>
                      <span className="text-3xs opacity-70">({loc.count})</span>
                    </button>
                  );
                })}
              </div>
            ) : (
              <div className="text-2xs text-muted-foreground/60 py-1 pl-1 italic">
                Sin ubicaciones registradas aún
              </div>
            )}
          </div>

          {/* FILTRO DE ANTIGÜEDAD DE LA OFERTA */}
          <div className="space-y-1.5 pt-2 border-t border-border/30">
            <div className="flex items-center justify-between text-xs font-semibold text-foreground">
              <div className="flex items-center gap-1.5">
                <Clock className="h-3.5 w-3.5 text-primary" />
                <span>Antigüedad de la oferta:</span>
              </div>
              <span
                className={`text-3xs font-mono font-bold px-1.5 py-0.5 rounded border ${
                  timeRange === "all"
                    ? "text-muted-foreground bg-muted border-border/50"
                    : "text-primary bg-primary/10 border-primary/30"
                }`}
              >
                {timeRange === "24h"
                  ? "24 horas"
                  : timeRange === "7d"
                  ? "1 semana"
                  : timeRange === "30d"
                  ? "1 mes"
                  : "Todas"}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-1 pt-0.5">
              {[
                { id: "all", label: "Todas en el tiempo" },
                { id: "24h", label: "Últimas 24h" },
                { id: "7d", label: "Última semana" },
                { id: "30d", label: "Último mes" },
              ].map((opt) => {
                const isSelected = (timeRange || "all") === opt.id;
                return (
                  <button
                    key={opt.id}
                    type="button"
                    onClick={() => onFilterChange("timeRange", opt.id)}
                    className={`text-2xs py-1 px-1.5 rounded-md border text-center transition-all font-medium ${
                      isSelected
                        ? "bg-primary text-primary-foreground border-primary shadow-xs"
                        : "bg-muted/30 hover:bg-muted border-border/40 text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {opt.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* DESLIZANTE DE EXPERIENCIA INTEGRADO */}
          <div className="space-y-1 pt-2 border-t border-border/30">
            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-1.5 font-semibold text-foreground">
                <Clock className="h-3.5 w-3.5 text-primary" />
                <span>Experiencia:</span>
              </div>
              <span
                className={`text-3xs font-mono font-bold px-1.5 py-0.5 rounded border ${
                  minExperienceStep === 0
                    ? "text-muted-foreground bg-muted border-border/50"
                    : "text-primary bg-primary/10 border-primary/30"
                }`}
              >
                {currentExpLabel}
              </span>
            </div>
            <input
              type="range"
              min="0"
              max={EXPERIENCE_STEPS.length - 1}
              step="1"
              value={minExperienceStep}
              onChange={(e) => onFilterChange("minExperienceStep", parseInt(e.target.value, 10))}
              className="w-full h-1.5 rounded-lg cursor-pointer accent-primary bg-muted hover:bg-muted/80 transition-all focus:outline-none"
            />
          </div>

          {/* DESLIZANTE DE SALARIO INTEGRADO */}
          <div className="space-y-1 pt-2 border-t border-border/30">
            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-1.5 font-semibold text-foreground">
                <DollarSign className="h-3.5 w-3.5 text-emerald-400" />
                <span>Salario mínimo:</span>
              </div>
              <span
                className={`text-3xs font-mono font-bold px-1.5 py-0.5 rounded border ${
                  minSalaryStep === 0
                    ? "text-muted-foreground bg-muted border-border/50"
                    : "text-emerald-400 bg-emerald-500/10 border-emerald-500/20"
                }`}
              >
                {currentSalaryLabel}
              </span>
            </div>
            {Boolean(facets?.salary_stats && facets.salary_stats.max > 0) && (
              <div className="flex items-center justify-between text-3xs text-muted-foreground/80 font-mono px-0.5">
                <span>Min: {facets!.salary_stats.min.toLocaleString("es-ES")} {salaryCurrency}</span>
                <span>Max: {facets!.salary_stats.max.toLocaleString("es-ES")} {salaryCurrency}</span>
              </div>
            )}
            <input
              type="range"
              min="0"
              max={SALARY_STEPS.length - 1}
              step="1"
              value={minSalaryStep}
              onChange={(e) => onFilterChange("minSalaryStep", parseInt(e.target.value, 10))}
              className="w-full h-1.5 rounded-lg cursor-pointer accent-emerald-500 bg-muted hover:bg-muted/80 transition-all focus:outline-none"
            />
          </div>

          {/* DIMENSIONES DINÁMICAS BASADAS EN OFERTAS REALES */}
          <FacetSection
            title="Modalidad"
            icon={<Building2 className="h-3.5 w-3.5 text-primary" />}
            items={dynamicModalities}
            selected={selectedModalities}
            onToggleItem={(id) => toggleArrayItem("selectedModalities", id)}
            onClear={() => onFilterChange("selectedModalities", [])}
            isOpen={openSections.modalidad}
            onToggleOpen={() => toggleSection("modalidad")}
          />

          <FacetSection
            title="Categoría / Funciones"
            icon={<Briefcase className="h-3.5 w-3.5 text-primary" />}
            items={dynamicCategories}
            selected={selectedCategories}
            onToggleItem={(id) => toggleArrayItem("selectedCategories", id)}
            onClear={() => onFilterChange("selectedCategories", [])}
            isOpen={openSections.categoria}
            onToggleOpen={() => toggleSection("categoria")}
          />

          <FacetSection
            title="Formación Mínima"
            icon={<GraduationCap className="h-3.5 w-3.5 text-primary" />}
            items={dynamicEducations}
            selected={selectedEducations}
            onToggleItem={(id) => toggleArrayItem("selectedEducations", id)}
            onClear={() => onFilterChange("selectedEducations", [])}
            isOpen={openSections.formacion}
            onToggleOpen={() => toggleSection("formacion")}
          />

          <FacetSection
            title="Jornada Laboral"
            icon={<Clock className="h-3.5 w-3.5 text-primary" />}
            items={dynamicSchedules}
            selected={selectedSchedules}
            onToggleItem={(id) => toggleArrayItem("selectedSchedules", id)}
            onClear={() => onFilterChange("selectedSchedules", [])}
            isOpen={openSections.jornada}
            onToggleOpen={() => toggleSection("jornada")}
          />

          <FacetSection
            title="Tipo de Contrato"
            icon={<FileText className="h-3.5 w-3.5 text-primary" />}
            items={dynamicContracts}
            selected={selectedContractTypes}
            onToggleItem={(id) => toggleArrayItem("selectedContractTypes", id)}
            onClear={() => onFilterChange("selectedContractTypes", [])}
            isOpen={openSections.contrato}
            onToggleOpen={() => toggleSection("contrato")}
          />

          {/* EVALUACIÓN Y AFINIDAD IA */}
          <div className="pt-2 border-t border-border/30">
            <div
              onClick={() => toggleSection("avanzados")}
              className="flex items-center justify-between cursor-pointer py-1 select-none hover:text-foreground text-muted-foreground transition-colors"
            >
              <div className="flex items-center gap-1.5 text-xs font-semibold text-foreground">
                <Sparkles className="h-3.5 w-3.5 text-primary" />
                <span>Evaluación y Afinidad</span>
              </div>
              <div className="flex items-center gap-1">
                {minScore > 0 && (
                  <span className="text-3xs font-mono px-1.5 py-0.5 rounded-full bg-primary/20 text-primary font-bold">
                    activo
                  </span>
                )}
                {openSections.avanzados ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
              </div>
            </div>

            {openSections.avanzados && (
              <div className="space-y-2.5 pt-2 pl-1 pr-1">
                {/* Distribución por Afinidad evaluada por la IA */}
                {Boolean(facets?.fit_levels && facets.fit_levels.length > 0) && (
                  <div className="space-y-1">
                    <label className="text-2xs font-medium text-muted-foreground">Evaluación IA:</label>
                    <div className="flex flex-wrap gap-1">
                      {facets!.fit_levels!.map((lvl) => (
                        <span
                          key={lvl.id}
                          className="text-3xs font-mono font-medium px-1.5 py-0.5 rounded bg-secondary/80 border border-border/50 text-foreground flex items-center gap-1"
                        >
                          <span>{lvl.label}</span>
                          <span className="text-primary font-bold">({lvl.count})</span>
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Score Mínimo ATS */}
                <div className="space-y-1">
                  <div className="flex justify-between text-2xs font-medium text-muted-foreground">
                    <span>Afinidad ATS mínima:</span>
                    <span className="font-mono text-primary font-semibold">{minScore > 0 ? `≥ ${minScore}%` : "Cualquiera"}</span>
                  </div>
                  {Boolean(facets?.score_stats && facets.score_stats.max > 0) && (
                    <div className="text-3xs text-muted-foreground font-mono">
                      IA: mín {facets!.score_stats?.min}% · media {facets!.score_stats?.avg}% · máx {facets!.score_stats?.max}%
                    </div>
                  )}
                  <input
                    type="range"
                    min="0"
                    max="90"
                    step="5"
                    value={minScore}
                    onChange={(e) => onFilterChange("minScore", parseInt(e.target.value, 10))}
                    className="w-full h-1.5 rounded-lg cursor-pointer accent-primary bg-muted"
                  />
                </div>
              </div>
            )}
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
