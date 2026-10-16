"use client";

import React from "react";
import { Search } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { APPLICATION_STATUSES, PORTAL_SOURCES } from "@/lib/constants";

interface JobFiltersProps {
  searchTerm: string;
  onSearchTermChange: (term: string) => void;
  selectedSource: string;
  onSourceChange: (source: string) => void;
  selectedStatus: string;
  onStatusChange: (status: string) => void;
  minScore: string;
  onMinScoreChange: (score: string) => void;
  isRemoteOnly: boolean;
  onRemoteOnlyChange: (remote: boolean) => void;
  onSubmitSearch: (e: React.FormEvent) => void;
}

export function JobFilters({
  searchTerm,
  onSearchTermChange,
  selectedSource,
  onSourceChange,
  selectedStatus,
  onStatusChange,
  minScore,
  onMinScoreChange,
  isRemoteOnly,
  onRemoteOnlyChange,
  onSubmitSearch,
}: JobFiltersProps) {
  return (
    <Card className="border bg-card/60 backdrop-blur-sm shadow-sm">
      <CardContent className="p-3 sm:p-4 space-y-3">
        <form onSubmit={onSubmitSearch} className="flex flex-col sm:flex-row items-center gap-2">
          <div className="relative flex-1 w-full">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              type="text"
              placeholder="Buscar por puesto, empresa o tecnología..."
              value={searchTerm}
              onChange={(e) => onSearchTermChange(e.target.value)}
              className="pl-9 text-xs w-full"
            />
          </div>

          <Button type="submit" size="sm" className="h-9 px-4 text-xs w-full sm:w-auto shrink-0">
            Buscar
          </Button>
        </form>

        {/* Filtros secundarios relativos */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t text-xs">
          <div>
            <Select
              value={selectedSource}
              onChange={(e) => onSourceChange(e.target.value)}
              className="text-xs h-8 w-full"
            >
              <option value="">Todos los portales</option>
              {Object.entries(PORTAL_SOURCES).map(([code, meta]) => (
                <option key={code} value={code}>
                  {meta.label}
                </option>
              ))}
            </Select>
          </div>

          <div>
            <Select
              value={selectedStatus}
              onChange={(e) => onStatusChange(e.target.value)}
              className="text-xs h-8 w-full"
            >
              <option value="">Todos los estados</option>
              {Object.entries(APPLICATION_STATUSES).map(([key, meta]) => (
                <option key={key} value={key}>
                  {meta.label}
                </option>
              ))}
            </Select>
          </div>

          <div>
            <Select
              value={minScore}
              onChange={(e) => onMinScoreChange(e.target.value)}
              className="text-xs h-8 w-full"
            >
              <option value="">Cualquier nota</option>
              <option value="65">Aptas (≥ 65 pts)</option>
              <option value="80">Sobresalientes (≥ 80 pts)</option>
              <option value="90">Excelentes (≥ 90 pts)</option>
            </Select>
          </div>

          <div className="flex items-center space-x-2 pl-1">
            <input
              type="checkbox"
              id="remoteOnly"
              checked={isRemoteOnly}
              onChange={(e) => onRemoteOnlyChange(e.target.checked)}
              className="h-3.5 w-3.5 rounded border-gray-300 text-primary focus:ring-primary cursor-pointer"
            />
            <label htmlFor="remoteOnly" className="text-xs text-muted-foreground select-none cursor-pointer">
              Solo remoto
            </label>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
