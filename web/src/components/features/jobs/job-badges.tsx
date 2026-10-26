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

  if (status === "evaluating") {
    return (
      <Badge
        variant="warning"
        className={cn(sizeClasses, "animate-pulse flex items-center gap-1", className)}
      >
        <RefreshCw className={cn(size === "sm" ? "h-2.5 w-2.5" : "h-3 w-3", "animate-spin")} />
        Evaluando...
      </Badge>
    );
  }

  if (status === "generating_docs") {
    return (
      <Badge
        variant="warning"
        className={cn(sizeClasses, "animate-pulse flex items-center gap-1", className)}
      >
        <RefreshCw className={cn(size === "sm" ? "h-2.5 w-2.5" : "h-3 w-3", "animate-spin")} />
        Generando documentos...
      </Badge>
    );
  }

  const meta = APPLICATION_STATUSES[status as ApplicationStatusKey];
  if (meta) {
    return (
      <Badge variant={meta.badge} className={cn(sizeClasses, className)}>
        {meta.label}
      </Badge>
    );
  }

  return (
    <Badge variant="secondary" className={cn(sizeClasses, className)}>
      {status}
    </Badge>
  );
}
