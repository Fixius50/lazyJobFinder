"use client";

import React, { useState } from "react";
import { HelpCircle } from "lucide-react";

interface InfoTooltipProps {
  content: React.ReactNode;
  className?: string;
}

export function InfoTooltip({ content, className = "" }: InfoTooltipProps) {
  const [open, setOpen] = useState(false);

  return (
    <span
      className={`relative inline-flex items-center align-middle group cursor-pointer ${className}`}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onClick={(e) => {
        e.stopPropagation();
        setOpen(!open);
      }}
    >
      <HelpCircle className="h-3.5 w-3.5 text-muted-foreground/70 hover:text-primary transition-colors select-none" />
      
      {/* Tooltip flotante con fondo completamente solido y no transparente */}
      {open && (
        <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 z-50 w-64 max-w-[85vw] p-2.5 rounded-lg bg-zinc-900 border border-zinc-700 text-[11px] font-normal leading-relaxed text-zinc-100 shadow-2xl pointer-events-none animate-in fade-in zoom-in-95 duration-150">
          {content}
          <span className="absolute top-full left-1/2 -translate-x-1/2 -mt-[1px] border-4 border-transparent border-t-zinc-900" />
        </span>
      )}
    </span>
  );
}
