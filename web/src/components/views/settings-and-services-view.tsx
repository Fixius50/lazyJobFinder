"use client";

import React from "react";
import { SettingsView } from "@/components/views/settings-view";
import { DockerControlView } from "@/components/views/docker-control-view";

export function SettingsAndServicesView() {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start w-full">
      {/* Columna Principal Izquierda (Más grande): Configuración de Canales, Scraping y Base de Datos */}
      <div className="lg:col-span-7 xl:col-span-7 2xl:col-span-8 space-y-6">
        <SettingsView />
      </div>

      {/* Columna Secundaria Derecha: Control de Contenedores Docker y Consola de Logs */}
      <div className="lg:col-span-5 xl:col-span-5 2xl:col-span-4 space-y-6">
        <DockerControlView />
      </div>
    </div>
  );
}
