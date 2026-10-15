"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, Search, Briefcase, Settings, ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";

const navigationItems = [
  {
    name: "Control Docker",
    href: "/",
    icon: Activity,
    description: "Servicios y logs en tiempo real",
  },
  {
    name: "Búsqueda y CV",
    href: "/search",
    icon: Search,
    description: "Gestión de CV y escaneo manual",
  },
  {
    name: "Candidaturas",
    href: "/applications",
    icon: Briefcase,
    description: "Ofertas detectadas y documentos",
  },
  {
    name: "Configuración",
    href: "/settings",
    icon: Settings,
    description: "Canales y mantenimiento",
  },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-full md:w-60 shrink-0 border-b md:border-b-0 md:border-r bg-card flex flex-col justify-between p-4">
      <div className="space-y-6">
        {/* Marca y encabezado */}
        <div className="flex items-center space-x-2.5 px-2">
          <div className="h-8 w-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center font-bold text-sm">
            LJ
          </div>
          <div>
            <h1 className="text-sm font-semibold tracking-tight text-foreground leading-none">
              lazyJobFinder
            </h1>
            <p className="text-[11px] text-muted-foreground mt-1">Panel de Administración</p>
          </div>
        </div>

        {/* Enlaces de navegación */}
        <nav className="flex flex-row md:flex-col gap-1 overflow-x-auto md:overflow-visible">
          {navigationItems.map((item) => {
            const isActive =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);
            const Icon = item.icon;

            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center space-x-3 rounded-lg px-3 py-2 text-xs font-medium transition-colors whitespace-nowrap",
                  isActive
                    ? "bg-primary text-primary-foreground shadow-sm font-semibold"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                )}
              >
                <Icon className={cn("h-4 w-4 shrink-0", isActive ? "text-primary-foreground" : "text-muted-foreground")} />
                <span>{item.name}</span>
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Pie de navegación con estado de privacidad */}
      <div className="pt-4 border-t hidden md:block">
        <div className="flex items-center space-x-2 px-2 py-1.5 rounded-md bg-muted/50 text-[11px] text-muted-foreground">
          <ShieldCheck className="h-3.5 w-3.5 text-emerald-500 shrink-0" />
          <span>Local 100% · 0 €/mes</span>
        </div>
      </div>
    </aside>
  );
}
