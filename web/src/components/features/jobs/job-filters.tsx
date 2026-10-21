"use client";

import React, { useState, useMemo } from "react";
import dynamic from "next/dynamic";
import {
  Search,
  SlidersHorizontal,
  MapPin,
  RotateCcw,
  Ban,
  Save,
  ChevronDown,
  ChevronUp,
  Maximize2,
  Building2,
  Briefcase,
  GraduationCap,
  Clock,
  FileText,
  DollarSign,
  Sparkles,
  Globe,
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { InfoTooltip } from "@/components/ui/info-tooltip";
import { APPLICATION_STATUSES } from "@/lib/constants";
import type { FilterFacetsResponse, FacetItem } from "@/lib/api";

// Importación dinámica de Leaflet para evitar fallos de SSR en Next.js
const LocationMap = dynamic(
  () => import("./location-map").then((mod) => mod.LocationMap),
  { ssr: false, loading: () => <div className="h-44 w-full bg-muted/40 animate-pulse rounded-lg flex items-center justify-center text-xs text-muted-foreground">Cargando mapa interactivo...</div> }
);

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
  { step: 7, value: 60000, label: "≥ 60.000 / año" },
  { step: 8, value: 80000, label: "≥ 80.000+ / año" },
];

export interface JobFiltersProps {
  // Facetas dinámicas recibidas desde la base de datos según lo encontrado en los portales
  facets?: FilterFacetsResponse | null;

  // Búsqueda general
  searchTerm: string;
  onSearchTermChange: (term: string) => void;
  exclusionTerm?: string;
  onExclusionTermChange?: (term: string) => void;

  // Mapa y Geolocation (Lugar)
  geoLat: number;
  geoLon: number;
  geoRadiusKm: number;
  locationName: string;
  isAllLocations: boolean;
  onGeoLocationChange: (lat: number, lon: number, name: string) => void;
  onGeoRadiusChange: (radiusKm: number) => void;
  onToggleAllLocations: (all: boolean) => void;

  // Modalidad (Checkboxes dinámicos)
  selectedModalities: string[];
  onModalitiesChange: (modalities: string[]) => void;

  // Categorías profesionales (Checkboxes dinámicos)
  selectedCategories: string[];
  onCategoriesChange: (categories: string[]) => void;

  // Formación mínima (Checkboxes dinámicos)
  selectedEducations: string[];
  onEducationsChange: (educations: string[]) => void;

  // Experiencia (Slider con 'Sin especificar' a la izquierda)
  minExperienceStep: number;
  onMinExperienceStepChange: (step: number) => void;

  // Salario (Slider con 'Sin especificar' a la izquierda)
  minSalaryStep: number;
  onMinSalaryStepChange: (step: number) => void;

  // Jornada laboral (Checkboxes dinámicos)
  selectedSchedules: string[];
  onSchedulesChange: (schedules: string[]) => void;

  // Tipo de contrato (Checkboxes dinámicos)
  selectedContractTypes: string[];
  onContractTypesChange: (contractTypes: string[]) => void;

  // Filtros adicionales (Portal, Estado, Score IA)
  selectedSource: string;
  onSourceChange: (source: string) => void;
  selectedStatus: string;
  onStatusChange: (status: string) => void;
  minScore: number;
  onMinScoreChange: (score: number) => void;

  // Acciones
  onSubmitSearch: (e: React.FormEvent) => void;
  onResetFilters?: () => void;
  onSaveCriteria?: () => void;
}

export function JobFilters({
  facets,
  searchTerm,
  onSearchTermChange,
  exclusionTerm = "",
  onExclusionTermChange,
  geoLat,
  geoLon,
  geoRadiusKm,
  locationName,
  isAllLocations,
  onGeoLocationChange,
  onGeoRadiusChange,
  onToggleAllLocations,
  selectedModalities,
  onModalitiesChange,
  selectedCategories,
  onCategoriesChange,
  selectedEducations,
  onEducationsChange,
  minExperienceStep,
  onMinExperienceStepChange,
  minSalaryStep,
  onMinSalaryStepChange,
  selectedSchedules,
  onSchedulesChange,
  selectedContractTypes,
  onContractTypesChange,
  selectedSource,
  onSourceChange,
  selectedStatus,
  onStatusChange,
  minScore,
  onMinScoreChange,
  onSubmitSearch,
  onResetFilters,
  onSaveCriteria,
}: JobFiltersProps) {
  // Buscador global rápido de los filtros
  const [filterSearchQuery, setFilterSearchQuery] = useState<string>("");

  // Control de expansión de acordeones
  const [openSections, setOpenSections] = useState<Record<string, boolean>>({
    lugar: true,
    modalidad: true,
    categoria: false,
    formacion: false,
    experiencia: true,
    salario: true,
    jornada: false,
    contrato: false,
    avanzados: false,
  });

  const [mapModalOpen, setMapModalOpen] = useState<boolean>(false);

  const toggleSection = (section: string) => {
    setOpenSections((prev) => ({ ...prev, [section]: !prev[section] }));
  };

  const toggleArrayItem = (list: string[], item: string, setter: (val: string[]) => void) => {
    if (list.includes(item)) {
      setter(list.filter((x) => x !== item));
    } else {
      setter([...list, item]);
    }
  };

  // Opciones dinámicas tomadas del backend según las ofertas encontradas en los portales
  const dynamicSources = facets?.sources || [];
  const dynamicModalities = facets?.modalities || [];
  const dynamicCategories = facets?.categories || [];
  const dynamicEducations = facets?.educations || [];
  const dynamicSchedules = facets?.schedules || [];
  const dynamicContracts = facets?.contract_types || [];

  // Filtrado reactivo de opciones según el texto introducido en el buscador global de filtros
  const normQuery = filterSearchQuery.trim().toLowerCase();

  const filteredModalities = useMemo(() => {
    if (!normQuery) return dynamicModalities;
    return dynamicModalities.filter((opt) => opt.label.toLowerCase().includes(normQuery));
  }, [normQuery, dynamicModalities]);

  const filteredCategories = useMemo(() => {
    if (!normQuery) return dynamicCategories;
    return dynamicCategories.filter((opt) => opt.label.toLowerCase().includes(normQuery));
  }, [normQuery, dynamicCategories]);

  const filteredEducations = useMemo(() => {
    if (!normQuery) return dynamicEducations;
    return dynamicEducations.filter((opt) => opt.label.toLowerCase().includes(normQuery));
  }, [normQuery, dynamicEducations]);

  const filteredSchedules = useMemo(() => {
    if (!normQuery) return dynamicSchedules;
    return dynamicSchedules.filter((opt) => opt.label.toLowerCase().includes(normQuery));
  }, [normQuery, dynamicSchedules]);

  const filteredContracts = useMemo(() => {
    if (!normQuery) return dynamicContracts;
    return dynamicContracts.filter((opt) => opt.label.toLowerCase().includes(normQuery));
  }, [normQuery, dynamicContracts]);

  // Indicador de filtros activos
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
  const currentSalaryLabel = SALARY_STEPS[minSalaryStep]?.label || "Sin especificar";

  return (
    <Card className="border bg-card/75 backdrop-blur-md shadow-sm overflow-visible transition-all">
      <CardHeader className="pb-2.5 pt-3 px-3 sm:px-4 border-b border-border/40">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <SlidersHorizontal className="h-4 w-4 text-primary" />
            <CardTitle className="text-xs sm:text-sm font-semibold tracking-tight">
              Filtros Dinámicos
            </CardTitle>
            <InfoTooltip content="Filtros generados dinámicamente según las ofertas y datos reales extraídos de los portales de empleo." />
          </div>
          {hasActiveFilters && onResetFilters && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={onResetFilters}
              className="h-6 px-1.5 text-[11px] text-muted-foreground hover:text-foreground flex items-center gap-1 transition-colors"
              title="Restablecer todos los filtros a sus valores predeterminados"
            >
              <RotateCcw className="h-3 w-3" />
              Limpiar
            </Button>
          )}
        </div>
      </CardHeader>

      <CardContent className="p-3 sm:p-4 space-y-3.5 overflow-visible">
        {/* BUSCADOR GLOBAL DE FILTROS (Al inicio de la zona de filtros) */}
        <div className="space-y-1">
          <label className="text-[11px] font-semibold text-foreground flex items-center gap-1.5">
            <Search className="h-3.5 w-3.5 text-primary" />
            Buscador global de filtros:
          </label>
          <div className="relative w-full">
            <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              type="text"
              placeholder="Buscar en opciones (remoto, software, grado, full-time...)"
              value={filterSearchQuery}
              onChange={(e) => setFilterSearchQuery(e.target.value)}
              className="pl-8 text-xs h-8 w-full bg-background/90 border-primary/20 focus:border-primary shadow-inner"
            />
            {filterSearchQuery && (
              <button
                type="button"
                onClick={() => setFilterSearchQuery("")}
                className="absolute right-2.5 top-2 text-xs text-muted-foreground hover:text-foreground"
              >
                ×
              </button>
            )}
          </div>
        </div>

        <form onSubmit={onSubmitSearch} className="space-y-3">
          {/* Términos de búsqueda principales */}
          <div className="space-y-1">
            <label className="text-[11px] font-medium text-muted-foreground">Palabras clave / Puesto:</label>
            <div className="relative w-full">
              <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
              <Input
                type="text"
                placeholder="ej: Full Stack, Python, DevOps, React..."
                value={searchTerm}
                onChange={(e) => onSearchTermChange(e.target.value)}
                className="pl-8 text-xs h-8 w-full bg-background"
              />
            </div>
          </div>

          {/* 1. LUGAR: Mapa interactivo global y radio de cobertura */}
          <div className="rounded-lg border border-border/50 bg-background/50 overflow-hidden">
            <div
              onClick={() => toggleSection("lugar")}
              className="flex items-center justify-between p-2.5 cursor-pointer hover:bg-muted/30 transition-colors select-none"
            >
              <div className="flex items-center gap-1.5 text-xs font-semibold">
                <MapPin className="h-3.5 w-3.5 text-primary" />
                <span>Lugar y Área Geográfica</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                  {isAllLocations ? "Todos los sitios (Por defecto)" : `${locationName} (${geoRadiusKm > 0 ? `+${geoRadiusKm}km` : "exacto"})`}
                </span>
                {openSections.lugar ? <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" /> : <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />}
              </div>
            </div>

            {openSections.lugar && (
              <div className="p-2.5 pt-0 space-y-2 border-t border-border/30">
                <div className="flex items-center justify-between gap-1 pt-2">
                  <button
                    type="button"
                    onClick={() => onToggleAllLocations(true)}
                    className={`flex-1 text-[11px] py-1 px-2 rounded border flex items-center justify-center gap-1 transition-all ${
                      isAllLocations
                        ? "bg-primary/15 border-primary/40 text-primary font-medium"
                        : "bg-muted/30 border-border/40 text-muted-foreground hover:bg-muted/60"
                    }`}
                  >
                    <Globe className="h-3 w-3" />
                    Todos los sitios (Por defecto)
                  </button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setMapModalOpen(true)}
                    className="h-7 px-2 text-[11px] flex items-center gap-1 text-muted-foreground hover:text-foreground shrink-0"
                    title="Maximizar mapa interactivo en pantalla completa"
                  >
                    <Maximize2 className="h-3 w-3" />
                    Expandir
                  </Button>
                </div>

                {!isAllLocations && (
                  <div className="text-[10px] text-muted-foreground flex items-center justify-between">
                    <span>
                      Área: <strong className="text-foreground">{locationName}</strong>
                    </span>
                    <span>
                      Radio: <strong className="text-foreground">{geoRadiusKm > 0 ? `${geoRadiusKm} km` : "Sin límite"}</strong>
                    </span>
                  </div>
                )}

                {/* Mapa dinámico global con OpenStreetMap */}
                <div className="rounded-md overflow-hidden border border-border/40">
                  <LocationMap
                    lat={geoLat}
                    lon={geoLon}
                    radiusKm={geoRadiusKm}
                    locationName={locationName}
                    isAllLocations={isAllLocations}
                    onLocationChange={onGeoLocationChange}
                    onRadiusChange={onGeoRadiusChange}
                    onToggleAllLocations={onToggleAllLocations}
                    height="h-44"
                  />
                </div>
              </div>
            )}
          </div>

          {/* 2. MODALIDAD: Extraída dinámicamente de los portales */}
          <div className="rounded-lg border border-border/50 bg-background/50 overflow-hidden">
            <div
              onClick={() => toggleSection("modalidad")}
              className="flex items-center justify-between p-2.5 cursor-pointer hover:bg-muted/30 transition-colors select-none"
            >
              <div className="flex items-center gap-1.5 text-xs font-semibold">
                <Building2 className="h-3.5 w-3.5 text-primary" />
                <span>Modalidad</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                  {selectedModalities.length === 0 ? "Sin especificar (Todas)" : `${selectedModalities.length} sel.`}
                </span>
                {openSections.modalidad ? <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" /> : <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />}
              </div>
            </div>

            {openSections.modalidad && (
              <div className="p-2.5 pt-1.5 space-y-1.5 border-t border-border/30">
                <label className="flex items-center gap-2 text-xs cursor-pointer select-none py-0.5 text-muted-foreground hover:text-foreground">
                  <input
                    type="checkbox"
                    checked={selectedModalities.length === 0}
                    onChange={() => onModalitiesChange([])}
                    className="accent-primary h-3.5 w-3.5 rounded"
                  />
                  <span className={selectedModalities.length === 0 ? "font-semibold text-primary" : ""}>
                    Sin especificar (Todas)
                  </span>
                </label>

                {filteredModalities.map((item) => {
                  const isChecked = selectedModalities.includes(item.id);
                  return (
                    <label
                      key={item.id}
                      className="flex items-center justify-between text-xs cursor-pointer select-none py-0.5 text-muted-foreground hover:text-foreground transition-colors"
                    >
                      <div className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => toggleArrayItem(selectedModalities, item.id, onModalitiesChange)}
                          className="accent-primary h-3.5 w-3.5 rounded"
                        />
                        <span className={isChecked ? "font-medium text-foreground" : ""}>{item.label}</span>
                      </div>
                      <span className="text-[10px] font-mono text-muted-foreground/80 px-1 rounded bg-muted/60">
                        {item.count}
                      </span>
                    </label>
                  );
                })}
              </div>
            )}
          </div>

          {/* 3. FUNCIONES PROFESIONALES / CATEGORÍA: Extraídas dinámicamente de los portales */}
          <div className="rounded-lg border border-border/50 bg-background/50 overflow-hidden">
            <div
              onClick={() => toggleSection("categoria")}
              className="flex items-center justify-between p-2.5 cursor-pointer hover:bg-muted/30 transition-colors select-none"
            >
              <div className="flex items-center gap-1.5 text-xs font-semibold">
                <Briefcase className="h-3.5 w-3.5 text-primary" />
                <span>Funciones / Categoría</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                  {selectedCategories.length === 0 ? "Sin especificar (Todas)" : `${selectedCategories.length} sel.`}
                </span>
                {openSections.categoria ? <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" /> : <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />}
              </div>
            </div>

            {openSections.categoria && (
              <div className="p-2.5 pt-1.5 space-y-1.5 border-t border-border/30 max-h-52 overflow-y-auto pr-1">
                <label className="flex items-center gap-2 text-xs cursor-pointer select-none py-0.5 text-muted-foreground hover:text-foreground">
                  <input
                    type="checkbox"
                    checked={selectedCategories.length === 0}
                    onChange={() => onCategoriesChange([])}
                    className="accent-primary h-3.5 w-3.5 rounded"
                  />
                  <span className={selectedCategories.length === 0 ? "font-semibold text-primary" : ""}>
                    Sin especificar (Todas)
                  </span>
                </label>

                {filteredCategories.map((item) => {
                  const isChecked = selectedCategories.includes(item.id);
                  return (
                    <label
                      key={item.id}
                      className="flex items-center justify-between text-xs cursor-pointer select-none py-0.5 text-muted-foreground hover:text-foreground transition-colors"
                    >
                      <div className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => toggleArrayItem(selectedCategories, item.id, onCategoriesChange)}
                          className="accent-primary h-3.5 w-3.5 rounded"
                        />
                        <span className={isChecked ? "font-medium text-foreground" : ""}>{item.label}</span>
                      </div>
                      <span className="text-[10px] font-mono text-muted-foreground/80 px-1 rounded bg-muted/60">
                        {item.count}
                      </span>
                    </label>
                  );
                })}
              </div>
            )}
          </div>

          {/* 4. FORMACIÓN MÍNIMA: Extraída dinámicamente de los portales */}
          <div className="rounded-lg border border-border/50 bg-background/50 overflow-hidden">
            <div
              onClick={() => toggleSection("formacion")}
              className="flex items-center justify-between p-2.5 cursor-pointer hover:bg-muted/30 transition-colors select-none"
            >
              <div className="flex items-center gap-1.5 text-xs font-semibold">
                <GraduationCap className="h-3.5 w-3.5 text-primary" />
                <span>Formación Mínima</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                  {selectedEducations.length === 0 ? "Sin especificar (Todas)" : `${selectedEducations.length} sel.`}
                </span>
                {openSections.formacion ? <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" /> : <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />}
              </div>
            </div>

            {openSections.formacion && (
              <div className="p-2.5 pt-1.5 space-y-1.5 border-t border-border/30 max-h-52 overflow-y-auto pr-1">
                <label className="flex items-center gap-2 text-xs cursor-pointer select-none py-0.5 text-muted-foreground hover:text-foreground">
                  <input
                    type="checkbox"
                    checked={selectedEducations.length === 0}
                    onChange={() => onEducationsChange([])}
                    className="accent-primary h-3.5 w-3.5 rounded"
                  />
                  <span className={selectedEducations.length === 0 ? "font-semibold text-primary" : ""}>
                    Sin especificar (Todas)
                  </span>
                </label>

                {filteredEducations.map((item) => {
                  const isChecked = selectedEducations.includes(item.id);
                  return (
                    <label
                      key={item.id}
                      className="flex items-center justify-between text-xs cursor-pointer select-none py-0.5 text-muted-foreground hover:text-foreground transition-colors"
                    >
                      <div className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => toggleArrayItem(selectedEducations, item.id, onEducationsChange)}
                          className="accent-primary h-3.5 w-3.5 rounded"
                        />
                        <span className={isChecked ? "font-medium text-foreground" : ""}>{item.label}</span>
                      </div>
                      <span className="text-[10px] font-mono text-muted-foreground/80 px-1 rounded bg-muted/60">
                        {item.count}
                      </span>
                    </label>
                  );
                })}
              </div>
            )}
          </div>

          {/* 5. EXPERIENCIA: Slider con 'Sin especificar' a la izquierda */}
          <div className="rounded-lg border border-border/50 bg-background/50 p-2.5 space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5 text-xs font-semibold">
                <Clock className="h-3.5 w-3.5 text-primary" />
                <span>Experiencia Requerida:</span>
              </div>
              <span
                className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded border transition-colors ${
                  minExperienceStep === 0
                    ? "text-muted-foreground bg-muted border-border/50"
                    : "text-primary bg-primary/10 border-primary/30"
                }`}
              >
                {currentExpLabel}
              </span>
            </div>

            <div className="px-1 py-1 w-full">
              <input
                type="range"
                min="0"
                max={EXPERIENCE_STEPS.length - 1}
                step="1"
                value={minExperienceStep}
                onChange={(e) => onMinExperienceStepChange(parseInt(e.target.value, 10))}
                className="w-full h-2 rounded-lg cursor-pointer accent-primary bg-muted hover:bg-muted/80 transition-all focus:outline-none"
              />
              <div className="flex justify-between text-[9px] text-muted-foreground/70 font-mono pt-1 select-none">
                <button
                  type="button"
                  onClick={() => onMinExperienceStepChange(0)}
                  className={`hover:text-foreground ${minExperienceStep === 0 ? "font-bold text-foreground" : ""}`}
                >
                  Sin esp.
                </button>
                <button
                  type="button"
                  onClick={() => onMinExperienceStepChange(2)}
                  className={`hover:text-foreground ${minExperienceStep === 2 ? "font-bold text-foreground" : ""}`}
                >
                  1 año
                </button>
                <button
                  type="button"
                  onClick={() => onMinExperienceStepChange(3)}
                  className={`hover:text-foreground ${minExperienceStep === 3 ? "font-bold text-foreground" : ""}`}
                >
                  2 años
                </button>
                <button
                  type="button"
                  onClick={() => onMinExperienceStepChange(5)}
                  className={`hover:text-foreground ${minExperienceStep === 5 ? "font-bold text-foreground" : ""}`}
                >
                  5+ años
                </button>
              </div>
            </div>
          </div>

          {/* 6. SALARIO: Slider con 'Sin especificar' a la izquierda */}
          <div className="rounded-lg border border-border/50 bg-background/50 p-2.5 space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5 text-xs font-semibold">
                <DollarSign className="h-3.5 w-3.5 text-primary" />
                <span>Salario Mínimo:</span>
              </div>
              <span
                className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded border transition-colors ${
                  minSalaryStep === 0
                    ? "text-muted-foreground bg-muted border-border/50"
                    : "text-emerald-400 bg-emerald-500/10 border-emerald-500/20"
                }`}
              >
                {currentSalaryLabel}
              </span>
            </div>

            <div className="px-1 py-1 w-full">
              <input
                type="range"
                min="0"
                max={SALARY_STEPS.length - 1}
                step="1"
                value={minSalaryStep}
                onChange={(e) => onMinSalaryStepChange(parseInt(e.target.value, 10))}
                className="w-full h-2 rounded-lg cursor-pointer accent-emerald-500 bg-muted hover:bg-muted/80 transition-all focus:outline-none"
              />
              <div className="flex justify-between text-[9px] text-muted-foreground/70 font-mono pt-1 select-none">
                <button
                  type="button"
                  onClick={() => onMinSalaryStepChange(0)}
                  className={`hover:text-foreground ${minSalaryStep === 0 ? "font-bold text-foreground" : ""}`}
                >
                  Sin esp.
                </button>
                <button
                  type="button"
                  onClick={() => onMinSalaryStepChange(2)}
                  className={`hover:text-foreground ${minSalaryStep === 2 ? "font-bold text-foreground" : ""}`}
                >
                  20k
                </button>
                <button
                  type="button"
                  onClick={() => onMinSalaryStepChange(4)}
                  className={`hover:text-foreground ${minSalaryStep === 4 ? "font-bold text-foreground" : ""}`}
                >
                  30k
                </button>
                <button
                  type="button"
                  onClick={() => onMinSalaryStepChange(6)}
                  className={`hover:text-foreground ${minSalaryStep === 6 ? "font-bold text-foreground" : ""}`}
                >
                  50k
                </button>
                <button
                  type="button"
                  onClick={() => onMinSalaryStepChange(8)}
                  className={`hover:text-foreground ${minSalaryStep === 8 ? "font-bold text-foreground" : ""}`}
                >
                  80k+
                </button>
              </div>
            </div>
          </div>

          {/* 7. JORNADA LABORAL: Extraída dinámicamente de los portales */}
          <div className="rounded-lg border border-border/50 bg-background/50 overflow-hidden">
            <div
              onClick={() => toggleSection("jornada")}
              className="flex items-center justify-between p-2.5 cursor-pointer hover:bg-muted/30 transition-colors select-none"
            >
              <div className="flex items-center gap-1.5 text-xs font-semibold">
                <Clock className="h-3.5 w-3.5 text-primary" />
                <span>Jornada Laboral</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                  {selectedSchedules.length === 0 ? "Sin especificar (Todas)" : `${selectedSchedules.length} sel.`}
                </span>
                {openSections.jornada ? <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" /> : <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />}
              </div>
            </div>

            {openSections.jornada && (
              <div className="p-2.5 pt-1.5 space-y-1.5 border-t border-border/30">
                <label className="flex items-center gap-2 text-xs cursor-pointer select-none py-0.5 text-muted-foreground hover:text-foreground">
                  <input
                    type="checkbox"
                    checked={selectedSchedules.length === 0}
                    onChange={() => onSchedulesChange([])}
                    className="accent-primary h-3.5 w-3.5 rounded"
                  />
                  <span className={selectedSchedules.length === 0 ? "font-semibold text-primary" : ""}>
                    Sin especificar (Todas)
                  </span>
                </label>

                {filteredSchedules.map((item) => {
                  const isChecked = selectedSchedules.includes(item.id);
                  return (
                    <label
                      key={item.id}
                      className="flex items-center justify-between text-xs cursor-pointer select-none py-0.5 text-muted-foreground hover:text-foreground transition-colors"
                    >
                      <div className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => toggleArrayItem(selectedSchedules, item.id, onSchedulesChange)}
                          className="accent-primary h-3.5 w-3.5 rounded"
                        />
                        <span className={isChecked ? "font-medium text-foreground" : ""}>{item.label}</span>
                      </div>
                      <span className="text-[10px] font-mono text-muted-foreground/80 px-1 rounded bg-muted/60">
                        {item.count}
                      </span>
                    </label>
                  );
                })}
              </div>
            )}
          </div>

          {/* 8. TIPO DE CONTRATO: Extraído dinámicamente de los portales */}
          <div className="rounded-lg border border-border/50 bg-background/50 overflow-hidden">
            <div
              onClick={() => toggleSection("contrato")}
              className="flex items-center justify-between p-2.5 cursor-pointer hover:bg-muted/30 transition-colors select-none"
            >
              <div className="flex items-center gap-1.5 text-xs font-semibold">
                <FileText className="h-3.5 w-3.5 text-primary" />
                <span>Tipo de Contrato</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                  {selectedContractTypes.length === 0 ? "Sin especificar (Todas)" : `${selectedContractTypes.length} sel.`}
                </span>
                {openSections.contrato ? <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" /> : <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />}
              </div>
            </div>

            {openSections.contrato && (
              <div className="p-2.5 pt-1.5 space-y-1.5 border-t border-border/30">
                <label className="flex items-center gap-2 text-xs cursor-pointer select-none py-0.5 text-muted-foreground hover:text-foreground">
                  <input
                    type="checkbox"
                    checked={selectedContractTypes.length === 0}
                    onChange={() => onContractTypesChange([])}
                    className="accent-primary h-3.5 w-3.5 rounded"
                  />
                  <span className={selectedContractTypes.length === 0 ? "font-semibold text-primary" : ""}>
                    Sin especificar (Todas)
                  </span>
                </label>

                {filteredContracts.map((item) => {
                  const isChecked = selectedContractTypes.includes(item.id);
                  return (
                    <label
                      key={item.id}
                      className="flex items-center justify-between text-xs cursor-pointer select-none py-0.5 text-muted-foreground hover:text-foreground transition-colors"
                    >
                      <div className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => toggleArrayItem(selectedContractTypes, item.id, onContractTypesChange)}
                          className="accent-primary h-3.5 w-3.5 rounded"
                        />
                        <span className={isChecked ? "font-medium text-foreground" : ""}>{item.label}</span>
                      </div>
                      <span className="text-[10px] font-mono text-muted-foreground/80 px-1 rounded bg-muted/60">
                        {item.count}
                      </span>
                    </label>
                  );
                })}
              </div>
            )}
          </div>

          {/* 9. PORTAL, ESTADO Y AFINIDAD IA */}
          <div className="rounded-lg border border-border/50 bg-background/50 overflow-hidden">
            <div
              onClick={() => toggleSection("avanzados")}
              className="flex items-center justify-between p-2.5 cursor-pointer hover:bg-muted/30 transition-colors select-none"
            >
              <div className="flex items-center gap-1.5 text-xs font-semibold">
                <Sparkles className="h-3.5 w-3.5 text-primary" />
                <span>Portal, Estado y Afinidad IA</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                  {minScore > 0 ? `≥${minScore}% IA` : "Predeterminado"}
                </span>
                {openSections.avanzados ? <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" /> : <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />}
              </div>
            </div>

            {openSections.avanzados && (
              <div className="p-2.5 pt-2 space-y-3 border-t border-border/30">
                {/* Descarte por exclusión */}
                <div className="space-y-1">
                  <label className="text-[11px] font-medium text-muted-foreground flex items-center gap-1">
                    <Ban className="h-3 w-3 text-destructive" />
                    Filtros de exclusión (descartar si contiene):
                  </label>
                  <Input
                    type="text"
                    placeholder="ej: Senior, Lead, Architect..."
                    value={exclusionTerm}
                    onChange={(e) => onExclusionTermChange?.(e.target.value)}
                    className="text-xs h-8 w-full bg-background"
                  />
                </div>

                {/* Portal y Estado */}
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="space-y-1">
                    <label className="text-[11px] font-medium text-muted-foreground">Portal:</label>
                    <Select
                      value={selectedSource}
                      onChange={(e) => onSourceChange(e.target.value)}
                      className="text-xs h-8 w-full bg-background"
                    >
                      <option value="">Todos los portales</option>
                      {dynamicSources.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.label} ({s.count})
                        </option>
                      ))}
                    </Select>
                  </div>

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

                {/* Afinidad IA */}
                <div className="space-y-1.5 pt-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-muted-foreground font-medium">Afinidad IA mínima:</span>
                    <span className="font-mono font-bold text-primary">≥ {minScore}%</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    step="5"
                    value={minScore}
                    onChange={(e) => onMinScoreChange(parseInt(e.target.value, 10))}
                    className="w-full h-2 rounded-lg cursor-pointer accent-primary bg-muted"
                  />
                </div>
              </div>
            )}
          </div>

          {/* Botones de Acción */}
          <div className="flex items-center gap-2 pt-1">
            <Button type="submit" size="sm" className="flex-1 h-8 text-xs font-semibold shadow-sm">
              Aplicar Filtros
            </Button>
            {onSaveCriteria && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={onSaveCriteria}
                className="h-8 px-2.5 text-xs font-medium flex items-center gap-1 border-primary/40 hover:bg-primary/10 text-primary shrink-0"
                title="Guardar criterios en la configuración base de búsqueda"
              >
                <Save className="h-3.5 w-3.5" />
                <span>Guardar</span>
              </Button>
            )}
          </div>
        </form>
      </CardContent>

      {/* Modal Maximizada del Mapa */}
      {mapModalOpen && (
        <div className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm flex items-center justify-center p-3 sm:p-6 animate-in fade-in duration-200">
          <div className="bg-card border shadow-2xl rounded-xl w-full max-w-4xl h-[85vh] flex flex-col overflow-hidden">
            <div className="flex items-center justify-between p-3 sm:p-4 border-b">
              <div className="flex items-center gap-2">
                <MapPin className="h-5 w-5 text-primary" />
                <div>
                  <h3 className="text-sm sm:text-base font-bold">Mapa Geográfico Global</h3>
                  <p className="text-xs text-muted-foreground">
                    Selecciona cualquier ciudad o país del mundo en el mapa y define el radio de cobertura.
                  </p>
                </div>
              </div>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setMapModalOpen(false)}
                className="h-8 px-3 text-xs"
              >
                Cerrar
              </Button>
            </div>
            <div className="flex-1 p-3">
              <LocationMap
                lat={geoLat}
                lon={geoLon}
                radiusKm={geoRadiusKm}
                locationName={locationName}
                isAllLocations={isAllLocations}
                onLocationChange={onGeoLocationChange}
                onRadiusChange={onGeoRadiusChange}
                onToggleAllLocations={onToggleAllLocations}
                height="h-full"
                isModal={true}
                onCloseModal={() => setMapModalOpen(false)}
              />
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}
