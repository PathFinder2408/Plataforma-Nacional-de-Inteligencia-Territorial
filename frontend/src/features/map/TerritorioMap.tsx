import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";

import type { MapUrlState } from "./urlState";

interface TerritorioMapProps {
  initialView: MapUrlState;
  selectedRol: string | null;
  flyToTarget: { lng: number; lat: number; zoom?: number } | null;
  onMoveEnd: (view: { lat: number; lng: number; z: number }) => void;
  onSelectPoint: (lat: number, lng: number) => void;
}

const TILES_BASE = (import.meta.env.VITE_TILES_BASE as string | undefined) ?? "/tiles";

export function TerritorioMap({
  initialView,
  selectedRol,
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
        },
        layers: [
          {
            id: "osm-base",
            type: "raster",
            source: "osm",
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
    if (!map || !flyToTarget) return;
    map.flyTo({
      center: [flyToTarget.lng, flyToTarget.lat],
      zoom: flyToTarget.zoom ?? 16,
      essential: true,
    });
  }, [flyToTarget]);

  return <div ref={containerRef} className="map-canvas" />;
}
