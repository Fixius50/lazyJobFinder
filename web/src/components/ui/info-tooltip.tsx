"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import { HelpCircle } from "lucide-react";

interface InfoTooltipProps {
  content: React.ReactNode;
  className?: string;
}

export function InfoTooltip({ content, className = "" }: InfoTooltipProps) {
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const triggerRef = useRef<HTMLSpanElement>(null);

  const [coords, setCoords] = useState<{
    top?: number;
    bottom?: number;
    left: number;
    placement: "top" | "bottom";
    arrowLeft: number;
    maxWidth: number;
  }>({
    left: 0,
    placement: "bottom",
    arrowLeft: 12,
    maxWidth: 280,
  });

  useEffect(() => {
    setMounted(true);
  }, []);

  const updatePosition = useCallback(() => {
    if (!triggerRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;

    const width = Math.min(280, viewportWidth - 24);
    const triggerCenter = rect.left + rect.width / 2;

    // Ajuste horizontal automatico: se mantiene siempre visible dentro de los margenes del viewport
    let left = triggerCenter - width / 2;
    if (left < 12) left = 12;
    if (left + width > viewportWidth - 12) {
      left = viewportWidth - 12 - width;
    }

    // La flecha siempre apunta al centro del icono
    const arrowLeft = Math.max(12, Math.min(triggerCenter - left, width - 12));

    // Deteccion vertical inteligente:
    // Si esta cerca del borde superior o debajo del header sticky (< 110px), forzar apertura hacia abajo
    const spaceAbove = rect.top;
    const spaceBelow = viewportHeight - rect.bottom;
    const placeBelow = spaceAbove < 110 || spaceBelow >= 120;

    if (placeBelow) {
      setCoords({
        top: rect.bottom + 7,
        left,
        placement: "bottom",
        arrowLeft,
        maxWidth: width,
      });
    } else {
      setCoords({
        bottom: viewportHeight - rect.top + 7,
        left,
        placement: "top",
        arrowLeft,
        maxWidth: width,
      });
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    updatePosition();

    const handleScrollOrResize = () => {
      updatePosition();
    };

    window.addEventListener("scroll", handleScrollOrResize, true);
    window.addEventListener("resize", handleScrollOrResize);

    return () => {
      window.removeEventListener("scroll", handleScrollOrResize, true);
      window.removeEventListener("resize", handleScrollOrResize);
    };
  }, [open, updatePosition]);

  return (
    <>
      <span
        ref={triggerRef}
        className={`inline-flex items-center align-middle group cursor-pointer ${className}`}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onClick={(e) => {
          e.stopPropagation();
          setOpen((prev) => !prev);
        }}
      >
        <HelpCircle className="h-3.5 w-3.5 text-muted-foreground/70 hover:text-primary transition-colors select-none" />
      </span>

      {mounted &&
        open &&
        createPortal(
          <div
            style={{
              position: "fixed",
              top: coords.top !== undefined ? `${coords.top}px` : "auto",
              bottom: coords.bottom !== undefined ? `${coords.bottom}px` : "auto",
              left: `${coords.left}px`,
              width: `${coords.maxWidth}px`,
              zIndex: 99999,
            }}
            className="pointer-events-none rounded-lg bg-zinc-900 border border-zinc-700 p-2.5 text-2xs font-normal leading-relaxed text-zinc-100 shadow-2xl animate-in fade-in zoom-in-95 duration-150"
          >
            {content}
            <span
              style={{ left: `${coords.arrowLeft}px` }}
              className={`absolute -translate-x-1/2 border-4 border-transparent ${
                coords.placement === "bottom"
                  ? "bottom-full -mb-px border-b-zinc-900"
                  : "top-full -mt-px border-t-zinc-900"
              }`}
            />
          </div>,
          document.body
        )}
    </>
  );
}
