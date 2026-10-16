"use client";

import React from "react";
import { RefreshCw } from "lucide-react";

interface CvProgressBarProps {
  stage: string;
  progress: number;
}

export function CvProgressBar({ stage, progress }: CvProgressBarProps) {
  return (
    <div className="space-y-1.5 p-3 rounded-lg bg-card border shadow-inner">
      <div className="flex items-center justify-between text-xs">
        <span className="font-medium text-primary flex items-center gap-1.5">
          <RefreshCw className="h-3 w-3 animate-spin" />
          {stage}
        </span>
        <span className="font-mono text-muted-foreground font-semibold">{progress}%</span>
      </div>
      <div className="w-full bg-muted/70 rounded-full h-2 overflow-hidden border">
        <div
          className="bg-primary h-full rounded-full transition-all duration-300 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}
