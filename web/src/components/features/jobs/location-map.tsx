"use client";

import React, { useEffect, useRef, useState } from "react";
import {
  MapPin,
  Crosshair,
  Search,
  Globe,
  Sliders,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export interface LocationMapProps {
  lat: number;
  lon: number;
  radiusKm: number;
  locationName: string;
  isAllLocations: boolean;
  onLocationChange: (lat: number, lon: number, name: string) => void;
  onRadiusChange: (radiusKm: number) => void;
  onToggleAllLocations: (all: boolean) => void;
  height?: string;
  isModal?: boolean;
  onCloseModal?: () => void;
}

const RADIUS_STEPS = [
  { label: "Sin límite", value: 0 },
  { label: "15 km", value: 15 },
  { label: "30 km", value: 30 },
  { label: "50 km", value: 50 },
  { label: "100 km", value: 100 },
  { label: "200 km", value: 200 },
  { label: "500 km", value: 500 },
];

export function LocationMap({
  lat,
  lon,
  radiusKm,
  locationName,
  isAllLocations,
  onLocationChange,
  onRadiusChange,
  onToggleAllLocations,
  height = "h-56",
  isModal = false,
  onCloseModal,
}: LocationMapProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<any>(null);
  const markerRef = useRef<any>(null);
  const circleRef = useRef<any>(null);

  const [searchQuery, setSearchQuery] = useState<string>(locationName || "");
  const [isLocating, setIsLocating] = useState<boolean>(false);
  const [isSearching, setIsSearching] = useState<boolean>(false);

  // Reverse geocoding libre y abierto con OpenStreetMap Nominatim
  const reverseGeocode = async (rLat: number, rLon: number) => {
    try {
      const res = await fetch(
        `https://nominatim.openstreetmap.org/reverse?format=json&lat=${rLat}&lon=${rLon}&zoom=10`,
        { headers: { "User-Agent": "lazyJobFinder-LocalApp" } }
      );
      if (res.ok) {
        const data = await res.json();
        const address = data.address || {};
        const cityName =
          address.city ||
          address.town ||
          address.village ||
          address.state ||
          address.country ||
          "Punto seleccionado";
        const displayName = address.country ? `${cityName}, ${address.country}` : cityName;
        onLocationChange(rLat, rLon, displayName);
        setSearchQuery(displayName);
        return;
      }
    } catch {
      // Fallback si no hay conexión externa
    }
    onLocationChange(rLat, rLon, "Punto en el mapa");
  };

  // Inicializar Leaflet dinámicamente en el cliente
  useEffect(() => {
    if (typeof window === "undefined" || !mapContainerRef.current) return;

    let isMounted = true;

    async function initMap() {
      const L = (await import("leaflet")).default;
      if (!isMounted || !mapContainerRef.current) return;

      if (!mapInstanceRef.current) {
        // Crear mapa con centro global o en las coordenadas activas
        const map = L.map(mapContainerRef.current, {
          center: [lat, lon],
          zoom: isAllLocations ? 3 : radiusKm > 0 ? (radiusKm > 100 ? 7 : radiusKm > 30 ? 9 : 11) : 5,
          zoomControl: true,
        });

        // Capa base mundial OpenStreetMap
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
          maxZoom: 18,
        }).addTo(map);

        // Icono SVG para evitar fallos de assets estáticos
        const customPin = L.divIcon({
          className: "custom-leaflet-pin",
          html: `<div style="background-color:#3b82f6;width:24px;height:24px;border-radius:50%;display:flex;align-items:center;justify-content:center;border:2px solid white;box-shadow:0 2px 6px rgba(0,0,0,0.5);color:white;">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
          </div>`,
          iconSize: [24, 24],
          iconAnchor: [12, 24],
        });

        // Marcador arrastrable por todo el mundo
        const marker = L.marker([lat, lon], {
          draggable: true,
          icon: customPin,
        }).addTo(map);

        marker.on("dragend", async (e: any) => {
          const newPos = e.target.getLatLng();
          onToggleAllLocations(false);
          await reverseGeocode(newPos.lat, newPos.lng);
        });

        // Clic en cualquier punto del mundo para reubicar
        map.on("click", async (e: any) => {
          marker.setLatLng(e.latlng);
          onToggleAllLocations(false);
          await reverseGeocode(e.latlng.lat, e.latlng.lng);
        });

        // Círculo de cobertura geográfica
        const circle = L.circle([lat, lon], {
          radius: radiusKm * 1000,
          color: "#3b82f6",
          fillColor: "#3b82f6",
          fillOpacity: radiusKm > 0 && !isAllLocations ? 0.18 : 0,
          weight: radiusKm > 0 && !isAllLocations ? 2 : 0,
        }).addTo(map);

        mapInstanceRef.current = map;
        markerRef.current = marker;
        circleRef.current = circle;
      }
    }

    initMap();

    return () => {
      isMounted = false;
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, []);

  // Actualizar visualización del marcador y círculo al cambiar coords o radio
  useEffect(() => {
    if (!mapInstanceRef.current || !markerRef.current || !circleRef.current) return;

    markerRef.current.setLatLng([lat, lon]);
    circleRef.current.setLatLng([lat, lon]);
    circleRef.current.setRadius(radiusKm * 1000);

    if (isAllLocations) {
      circleRef.current.setStyle({ fillOpacity: 0, weight: 0 });
    } else {
      circleRef.current.setStyle({
        fillOpacity: radiusKm > 0 ? 0.18 : 0,
        weight: radiusKm > 0 ? 2 : 0,
      });
      mapInstanceRef.current.setView(
        [lat, lon],
        radiusKm > 0 ? (radiusKm > 200 ? 6 : radiusKm > 50 ? 8 : 10) : 10
      );
    }
  }, [lat, lon, radiusKm, isAllLocations]);

  // Búsqueda global de cualquier lugar, ciudad o país del mundo en OpenStreetMap
  const handleSearchLocation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;

    setIsSearching(true);
    try {
      const res = await fetch(
        `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(
          searchQuery.trim()
        )}&limit=1`,
        { headers: { "User-Agent": "lazyJobFinder-LocalApp" } }
      );
      const data = await res.json();
      if (data && data.length > 0) {
        const item = data[0];
        const newLat = parseFloat(item.lat);
        const newLon = parseFloat(item.lon);
        const displayName = item.display_name.split(",").slice(0, 2).join(",").trim();
        onLocationChange(newLat, newLon, displayName);
        onToggleAllLocations(false);
        setSearchQuery(displayName);
      } else {
        alert("No se encontró el lugar. Puedes probar con otra ciudad o hacer clic directamente en el mapa.");
      }
    } catch (err) {
      console.warn("Fallo en geocodificación:", err);
    } finally {
      setIsSearching(false);
    }
  };

  // Geolocalización GPS del usuario
  const handleUseCurrentLocation = () => {
    if (!navigator.geolocation) {
      alert("Tu navegador no soporta geolocalización.");
      return;
    }

    setIsLocating(true);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        setIsLocating(false);
        const newLat = pos.coords.latitude;
        const newLon = pos.coords.longitude;
        onToggleAllLocations(false);
        await reverseGeocode(newLat, newLon);
      },
      (err) => {
        setIsLocating(false);
        alert(`No se pudo obtener tu ubicación: ${err.message}. Puedes buscar cualquier ciudad en el mapa.`);
      },
      { timeout: 10000 }
    );
  };

  return (
    <div className="space-y-2 w-full">
      {/* Barra de control superior de ubicación y radio */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-1.5 text-xs">
        <form onSubmit={handleSearchLocation} className="relative flex-1 flex items-center gap-1">
          <div className="relative flex-1">
            <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              type="text"
              placeholder="Buscar cualquier ciudad o país (London, New York, Tokyo, Madrid...)"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8 text-xs h-8 bg-background"
            />
          </div>
          <Button type="submit" variant="secondary" size="sm" disabled={isSearching} className="h-8 px-2 text-xs">
            {isSearching ? "Buscando..." : "Buscar"}
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handleUseCurrentLocation}
            disabled={isLocating}
            className="h-8 px-2 text-xs flex items-center gap-1 shrink-0"
            title="Centrar en mi ubicación GPS"
          >
            <Crosshair className={`h-3.5 w-3.5 text-primary ${isLocating ? "animate-spin" : ""}`} />
            <span className="hidden sm:inline">Mi GPS</span>
          </Button>
        </form>

        <div className="flex items-center gap-1.5 shrink-0">
          <Button
            type="button"
            variant={isAllLocations ? "default" : "outline"}
            size="sm"
            onClick={() => onToggleAllLocations(!isAllLocations)}
            className="h-8 px-2 text-xs flex items-center gap-1"
          >
            <Globe className="h-3.5 w-3.5" />
            <span>{isAllLocations ? "Todos los sitios (Activo)" : "Todos los sitios"}</span>
          </Button>

          {isModal && onCloseModal && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={onCloseModal}
              className="h-8 px-2 text-xs"
            >
              Cerrar
            </Button>
          )}
        </div>
      </div>

      {/* Selector de radio de distancia */}
      <div className="flex items-center gap-1.5 overflow-x-auto py-0.5 text-xs">
        <span className="text-2xs text-muted-foreground flex items-center gap-1 shrink-0">
          <Sliders className="h-3 w-3" /> Radio:
        </span>
        <div className="flex items-center gap-1 flex-nowrap">
          {RADIUS_STEPS.map((step) => {
            const isSelected = radiusKm === step.value && !isAllLocations;
            return (
              <button
                key={step.value}
                type="button"
                onClick={() => {
                  onRadiusChange(step.value);
                  onToggleAllLocations(false);
                }}
                className={`px-2 py-0.5 rounded text-2xs font-medium transition-colors whitespace-nowrap border ${
                  isSelected
                    ? "bg-primary text-primary-foreground border-primary shadow-sm"
                    : "bg-muted/50 hover:bg-muted border-border/40 text-muted-foreground hover:text-foreground"
                }`}
              >
                {step.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Contenedor del Mapa interactivo */}
      <div
        ref={mapContainerRef}
        className={`w-full ${height} rounded-lg overflow-hidden border border-border/50 relative shadow-inner z-0`}
      />

      <div className="text-3xs text-muted-foreground flex items-center justify-between px-1">
        <span>Haz clic en cualquier punto del mundo o arrastra el marcador para definir el centro.</span>
        {!isAllLocations && radiusKm > 0 && (
          <span className="font-mono text-primary font-semibold">
            {radiusKm} km desde {locationName}
          </span>
        )}
      </div>
    </div>
  );
}
