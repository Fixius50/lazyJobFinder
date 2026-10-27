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
  location?: string | null;
  title?: string | null;
  description?: string | null;
}): JobModality {
  const loc = (job.location || "").toLowerCase();
  const tit = (job.title || "").toLowerCase();
  const desc = (job.description || "").toLowerCase();
  const combined = `${loc} ${tit} ${desc}`;

  // 1. Híbrido: si menciona híbrido o hybrid en ubicación, título o descripción
  if (/h[ií]brid/i.test(combined)) {
    return "Híbrido";
  }

  // 2. Remoto: si is_remote es 1 o el texto menciona remoto o teletrabajo
  if (
    job.is_remote === 1 ||
    job.is_remote === true ||
    /remot|teletrabaj|work from home/i.test(`${loc} ${tit}`)
  ) {
    return "Remoto";
  }

  // 3. Por defecto: Presencial
  return "Presencial";
}

interface JobModalityBadgeProps {
  job: {
    is_remote?: number | boolean | null;
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

