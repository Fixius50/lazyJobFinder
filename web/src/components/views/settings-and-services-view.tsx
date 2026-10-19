"use client";

import React from "react";
import { DockerControlView } from "@/components/views/docker-control-view";

export function SettingsAndServicesView() {
  return (
    <div className="w-full max-w-6xl mx-auto space-y-6">
      <DockerControlView />
    </div>
  );
}

