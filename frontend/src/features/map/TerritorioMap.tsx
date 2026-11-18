import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";

import type { LayerVisibility } from "../../types/parcela";
import type { MapUrlState } from "./urlState";

interface TerritorioMapProps {
  initialView: MapUrlState;
  selectedRol: string | null;
  visibleLayers: LayerVisibility;
  flyToTarget: { lng: number; lat: number; zoom?: number } | null;
  onMoveEnd: (view: { lat: number; lng: number; z: number }) => void;
  onSelectPoint: (lat: number, lng: number) => void;
}

const TILES_BASE = (import.meta.env.VITE_TILES_BASE as string | undefined) ?? "/tiles";

export function TerritorioMap({
  initialView,
  selectedRol,
  visibleLayers,
  flyToTarget,
  onMoveEnd,
  onSelectPoint,
}: TerritorioMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const onMoveEndRef = useRef(onMoveEnd);
  const onSelectPointRef = useRef(onSelectPoint);

  onMoveEndRef.current = onMoveEnd;
  onSelectPointRef.current = onSelectPoint;

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      center: [initialView.lng, initialView.lat],
      zoom: initialView.z,
      style: {
        version: 8,
        sources: {
          osm: {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution: "© OpenStreetMap contributors",
          },
          parcelas: {
            type: "vector",
            tiles: [`${window.location.origin}${TILES_BASE}/parcelas_mvt/{z}/{x}/{y}`],
            minzoom: 10,
            maxzoom: 20,
          },
          fiscal: {
            type: "vector",
            tiles: [`${window.location.origin}${TILES_BASE}/terreno_fiscal/{z}/{x}/{y}`],
            minzoom: 10,
            maxzoom: 20,
          },
          normativa: {
            type: "vector",
            tiles: [`${window.location.origin}${TILES_BASE}/capa_normativa/{z}/{x}/{y}`],
            minzoom: 10,
            maxzoom: 20,
          },
          riesgo: {
            type: "vector",
            tiles: [`${window.location.origin}${TILES_BASE}/capa_riesgo/{z}/{x}/{y}`],
            minzoom: 10,
            maxzoom: 20,
          },
          h3: {
            type: "vector",
            tiles: [`${window.location.origin}${TILES_BASE}/celda_h3/{z}/{x}/{y}`],
            minzoom: 8,
            maxzoom: 18,
          },
        },
        layers: [
          {
            id: "osm-base",
            type: "raster",
            source: "osm",
          },
          {
            id: "h3-fill",
            type: "fill",
            source: "h3",
            "source-layer": "celda_h3",
            layout: { visibility: visibleLayers.h3 ? "visible" : "none" },
            paint: {
              "fill-color": "#f59e0b",
              "fill-opacity": 0.14,
            },
          },
          {
            id: "h3-outline",
            type: "line",
            source: "h3",
            "source-layer": "celda_h3",
            layout: { visibility: visibleLayers.h3 ? "visible" : "none" },
            paint: {
              "line-color": "#d97706",
              "line-width": 1.2,
            },
          },
          {
            id: "normativa-fill",
            type: "fill",
            source: "normativa",
            "source-layer": "capa_normativa",
            layout: { visibility: visibleLayers.normativa ? "visible" : "none" },
            paint: {
              "fill-color": "#8b5cf6",
              "fill-opacity": 0.16,
            },
          },
          {
            id: "normativa-outline",
            type: "line",
            source: "normativa",
            "source-layer": "capa_normativa",
            layout: { visibility: visibleLayers.normativa ? "visible" : "none" },
            paint: {
              "line-color": "#6d28d9",
              "line-width": 1.2,
              "line-dasharray": [2, 2],
            },
          },
          {
            id: "fiscal-fill",
            type: "fill",
            source: "fiscal",
            "source-layer": "terreno_fiscal",
            layout: { visibility: visibleLayers.fiscal ? "visible" : "none" },
            paint: {
              "fill-color": "#10b981",
              "fill-opacity": 0.25,
            },
          },
          {
            id: "riesgo-fill",
            type: "fill",
            source: "riesgo",
            "source-layer": "capa_riesgo",
            layout: { visibility: visibleLayers.riesgo ? "visible" : "none" },
            paint: {
              "fill-color": "#ef4444",
              "fill-opacity": 0.26,
            },
          },
          {
            id: "parcelas-fill",
            type: "fill",
            source: "parcelas",
            "source-layer": "parcelas",
            paint: {
              "fill-color": "#0ea5e9",
              "fill-opacity": 0.28,
            },
          },
          {
            id: "parcelas-outline",
            type: "line",
            source: "parcelas",
            "source-layer": "parcelas",
            paint: {
              "line-color": "#0369a1",
              "line-width": 1.5,
            },
          },
          {
            id: "parcelas-selected",
            type: "line",
            source: "parcelas",
            "source-layer": "parcelas",
            filter: ["==", ["get", "rol"], selectedRol ?? ""],
            paint: {
              "line-color": "#dc2626",
              "line-width": 3,
            },
          },
        ],
      },
    });

    map.addControl(new maplibregl.NavigationControl(), "top-right");

    map.on("moveend", () => {
      const center = map.getCenter();
      onMoveEndRef.current({
        lat: center.lat,
        lng: center.lng,
        z: map.getZoom(),
      });
    });

    map.on("click", (ev) => {
      onSelectPointRef.current(ev.lngLat.lat, ev.lngLat.lng);
    });

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    if (map.getLayer("parcelas-selected")) {
      map.setFilter("parcelas-selected", ["==", ["get", "rol"], selectedRol ?? ""]);
    }
  }, [selectedRol]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    const mapping: Array<[string, boolean]> = [
      ["fiscal-fill", visibleLayers.fiscal],
      ["normativa-fill", visibleLayers.normativa],
      ["normativa-outline", visibleLayers.normativa],
      ["riesgo-fill", visibleLayers.riesgo],
      ["h3-fill", visibleLayers.h3],
      ["h3-outline", visibleLayers.h3],
    ];
    for (const [layerId, isVisible] of mapping) {
      if (map.getLayer(layerId)) {
        map.setLayoutProperty(layerId, "visibility", isVisible ? "visible" : "none");
      }
    }
  }, [visibleLayers]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !flyToTarget) return;
    map.flyTo({
      center: [flyToTarget.lng, flyToTarget.lat],
      zoom: flyToTarget.zoom ?? 16,
      essential: true,
    });
  }, [flyToTarget]);

  return <div ref={containerRef} className="map-canvas" />;
}
