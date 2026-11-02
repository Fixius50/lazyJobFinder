"use client";

import React from "react";
import { RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { APPLICATION_STATUSES, ApplicationStatusKey } from "@/lib/constants";
import { cn } from "@/lib/utils";

interface JobScoreBadgeProps {
  score?: number | null;
  isEvaluating?: boolean;
  className?: string;
  size?: "sm" | "md";
}

export function JobScoreBadge({
  score,
  isEvaluating = false,
  className,
  size = "sm",
}: JobScoreBadgeProps) {
  const sizeClasses = size === "sm" ? "text-3xs py-0 px-1.5" : "text-2xs py-0.5 px-2";

  if (isEvaluating) {
    return (
      <Badge
        variant="warning"
        className={cn(sizeClasses, "font-mono animate-pulse flex items-center gap-1", className)}
      >
        <RefreshCw className={cn(size === "sm" ? "h-2.5 w-2.5" : "h-3 w-3", "animate-spin")} />
        Evaluando...
      </Badge>
    );
  }

  if (score === null || score === undefined) {
    return (
      <Badge variant="secondary" className={cn(sizeClasses, "font-mono", className)}>
        Sin evaluar
      </Badge>
    );
  }

  if (score >= 80) {
    return (
      <Badge variant="success" className={cn(sizeClasses, "font-mono font-bold", className)}>
        {score} / 100
      </Badge>
    );
  }

  if (score >= 65) {
    return (
      <Badge variant="warning" className={cn(sizeClasses, "font-mono font-bold", className)}>
        {score} / 100
      </Badge>
    );
  }

  return (
    <Badge variant="destructive" className={cn(sizeClasses, "font-mono font-bold", className)}>
      {score} / 100
    </Badge>
  );
}

interface JobStatusBadgeProps {
  status: string;
  className?: string;
  size?: "sm" | "md";
}

export function JobStatusBadge({
  status,
  className,
  size = "sm",
}: JobStatusBadgeProps) {
  const sizeClasses = size === "sm" ? "text-3xs py-0 px-1.5" : "text-2xs py-0.5 px-2";
  const meta = APPLICATION_STATUSES[status as ApplicationStatusKey];
  const isAnimated = status === "evaluating" || status === "generating_docs";

  return (
    <Badge
      variant={meta ? meta.badge : "secondary"}
      className={cn(
        sizeClasses,
        isAnimated && "animate-pulse flex items-center gap-1",
        className
      )}
    >
      {isAnimated && (
        <RefreshCw className={cn(size === "sm" ? "h-2.5 w-2.5" : "h-3 w-3", "animate-spin")} />
      )}
      {meta ? meta.label : status}
    </Badge>
  );
}

export type JobModality = "Remoto" | "Híbrido" | "Presencial";

export function getJobModality(job: {
  is_remote?: number | boolean | null;
  modality?: string | null;
  location?: string | null;
  title?: string | null;
  description?: string | null;
}): JobModality {
  // 1. Si la modalidad ya viene estructurada desde la base de datos
  if (job.modality) {
    const m = job.modality.trim().toLowerCase();
    if (m === "híbrido" || m === "hibrido" || m === "hybrid") return "Híbrido";
    if (m === "remoto" || m === "remote" || m === "teletrabajo") return "Remoto";
    if (m === "presencial" || m === "onsite" || m === "on-site") return "Presencial";
  }

  const loc = (job.location || "").toLowerCase();
  const tit = (job.title || "").toLowerCase();
  const desc = (job.description || "").toLowerCase();
  const combined = `${tit} ${loc} ${desc}`;

  // 2. Patrones estrictos de 100% presencial o 100% remoto
  const isStrictlyOnsite = /\b(100%\s*presencial|totalmente\s+presencial|exclusivamente\s+presencial|sin\s+teletrabajo|no\s+(?:se\s+)?permite\s+teletrabajo)\b/i.test(combined);
  const isStrictlyRemote = /\b(100%\s*remoto|100%\s*teletrabajo|totalmente\s+remoto|totalmente\s+en\s+remoto|full\s+remote|exclusivamente\s+remoto)\b/i.test(combined);

  if (isStrictlyOnsite) return "Presencial";
  if (isStrictlyRemote) return "Remoto";

  // 3. Híbrido: mención explícita o días repartidos (oficina y casa/online)
  const hasHybridWords = /\b(h[ií]brid[oa]?|hybrid|semipresencial|semi-presencial|modalidad\s+mixta|trabajo\s+mixto|smart\s+working)\b/i.test(combined);
  const hasSplitDays = /\b\d+\s*d[ií]as?\s+(?:de\s+)?(?:teletrabajo|remoto|en\s+casa|online|home\s*office)\b/i.test(combined) ||
                       /\b\d+\s*d[ií]as?\s+(?:de\s+)?(?:presencial|en\s+oficina|en\s+sede)\b/i.test(combined) ||
                       /\b(?:teletrabajo|remoto|casa|oficina)\s+\d+\s*d[ií]as?\b/i.test(combined) ||
                       /\b(?:teletrabajo|remoto)\s+parcial\b/i.test(combined);

  // 4. Coexistencia de Presencial y Online/Remoto ("dando igual cuánto, días presenciales y online")
  const hasOnsiteClues = /\b(presencial|presencialidad|en\s+oficina|en\s+instalaciones|en\s+sede|on-site|onsite)\b/i.test(combined);
  const hasRemoteClues = /\b(teletrabajo|remoto|remote|desde\s+casa|home\s*office|online|trabajo\s+a\s+distancia)\b/i.test(combined);

  if (hasHybridWords || hasSplitDays || (hasOnsiteClues && hasRemoteClues)) {
    return "Híbrido";
  }

  // 5. Remoto: si is_remote es 1 o el texto menciona remoto / teletrabajo
  if (
    job.is_remote === 1 ||
    job.is_remote === true ||
    hasRemoteClues ||
    loc.includes("remot") ||
    loc.includes("teletrabaj")
  ) {
    return "Remoto";
  }

  // 6. Por defecto: Presencial
  return "Presencial";
}

interface JobModalityBadgeProps {
  job: {
    is_remote?: number | boolean | null;
    modality?: string | null;
    location?: string | null;
    title?: string | null;
    description?: string | null;
  };
  className?: string;
  size?: "sm" | "md";
}

export function JobModalityBadge({ job, className, size = "sm" }: JobModalityBadgeProps) {
  const sizeClasses = size === "sm" ? "text-3xs py-0 px-1.5" : "text-2xs py-0.5 px-2";

  const { label, colorClasses } = React.useMemo(() => {
    const modality = getJobModality(job);
    switch (modality) {
      case "Remoto":
        return {
          label: "Remoto",
          colorClasses: "font-semibold bg-sky-500/10 text-sky-400 border-sky-500/20",
        };
      case "Híbrido":
        return {
          label: "Híbrido",
          colorClasses: "font-semibold bg-purple-500/10 text-purple-400 border-purple-500/20",
        };
      case "Presencial":
      default:
        return {
          label: "Presencial",
          colorClasses: "font-medium bg-zinc-800/80 text-zinc-300 border-zinc-700/50",
        };
    }
  }, [job]);

  return (
    <span
      className={cn(
        "rounded border shrink-0",
        colorClasses,
        sizeClasses,
        className
      )}
    >
      {label}
    </span>
  );
}

