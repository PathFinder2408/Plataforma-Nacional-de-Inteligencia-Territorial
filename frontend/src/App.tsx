import { useCallback, useEffect, useState } from "react";

import { ParcelaFichaPanel } from "./features/ficha/ParcelaFichaPanel";
import { LayerToggles } from "./features/map/LayerToggles";
import { TerritorioMap } from "./features/map/TerritorioMap";
import { readMapUrlState, writeMapUrlState } from "./features/map/urlState";
import { SearchBar } from "./features/search/SearchBar";
import type { LayerVisibility, ParcelaFicha, ParcelaFichaCompleta } from "./types/parcela";

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "/api/v1";

export function App() {
  const [initialView] = useState(() => readMapUrlState());
  const [ficha, setFicha] = useState<ParcelaFicha | null>(null);
  const [fichaCompleta, setFichaCompleta] = useState<ParcelaFichaCompleta | null>(null);
  const [visibleLayers, setVisibleLayers] = useState<LayerVisibility>({
    fiscal: true,
    normativa: false,
    riesgo: true,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [flyToTarget, setFlyToTarget] = useState<{
    lng: number;
    lat: number;
    zoom?: number;
  } | null>(null);

  const loadFichaCompleta = useCallback(async (parcelaId: number) => {
    try {
      const resp = await fetch(`${API_BASE}/parcelas/${parcelaId}/ficha-completa/`);
      if (resp.ok) {
        const full = (await resp.json()) as ParcelaFichaCompleta;
        setFichaCompleta(full);
      } else {
        setFichaCompleta(null);
      }
    } catch {
      setFichaCompleta(null);
    }
  }, []);

  const fetchByPoint = useCallback(
    async (lat: number, lng: number) => {
      setLoading(true);
      setError(null);
      try {
        const resp = await fetch(
          `${API_BASE}/parcelas/por-punto/?lat=${encodeURIComponent(lat)}&lng=${encodeURIComponent(lng)}`
        );
        if (resp.status === 404) {
          setFicha(null);
          setFichaCompleta(null);
          setError("No hay parcela registrada en ese punto.");
          return;
        }
        if (!resp.ok) {
          throw new Error(`Error ${resp.status} al consultar parcela`);
        }
        const data = (await resp.json()) as ParcelaFicha;
        setFicha(data);
        void loadFichaCompleta(data.id);
        const current = readMapUrlState();
        writeMapUrlState({ ...current, rol: data.rol });
      } catch (err) {
        setError(err instanceof Error ? err.message : "Error inesperado");
      } finally {
        setLoading(false);
      }
    },
    [loadFichaCompleta]
  );

  useEffect(() => {
    if (initialView.rol) {
      void fetch(`${API_BASE}/parcelas/buscar/?q=${encodeURIComponent(initialView.rol)}&limit=1`)
        .then((r) => (r.ok ? r.json() : null))
        .then((data) => {
          if (data?.resultados?.length) {
            const first = data.resultados[0] as ParcelaFicha;
            setFicha(first);
            void loadFichaCompleta(first.id);
            setFlyToTarget({ lng: first.centroide.lng, lat: first.centroide.lat, zoom: 16 });
          }
        })
        .catch(() => {});
    }
  }, [initialView.rol, loadFichaCompleta]);

  const handleMoveEnd = useCallback(
    (view: { lat: number; lng: number; z: number }) => {
      writeMapUrlState({ ...view, rol: ficha?.rol ?? null });
    },
    [ficha?.rol]
  );

  const handleSelectSearch = useCallback(
    (item: ParcelaFicha) => {
      setError(null);
      setFicha(item);
      void loadFichaCompleta(item.id);
      setFlyToTarget({ lng: item.centroide.lng, lat: item.centroide.lat, zoom: 16 });
      const current = readMapUrlState();
      writeMapUrlState({
        ...current,
        lat: item.centroide.lat,
        lng: item.centroide.lng,
        z: 16,
        rol: item.rol,
      });
    },
    [loadFichaCompleta]
  );

  const handleToggleLayer = useCallback((key: keyof LayerVisibility) => {
    setVisibleLayers((prev) => ({ ...prev, [key]: !prev[key] }));
  }, []);

  return (
    <main className="app-layout">
      <ParcelaFichaPanel
        ficha={ficha}
        fichaCompleta={fichaCompleta}
        loading={loading}
        error={error}
      />
      <section className="map-wrapper">
        <SearchBar apiBase={API_BASE} onSelectResult={handleSelectSearch} />
        <LayerToggles layers={visibleLayers} onToggle={handleToggleLayer} />
        <TerritorioMap
          initialView={initialView}
          selectedRol={ficha?.rol ?? null}
          visibleLayers={visibleLayers}
          flyToTarget={flyToTarget}
          onMoveEnd={handleMoveEnd}
          onSelectPoint={(lat, lng) => {
            void fetchByPoint(lat, lng);
          }}
        />
      </section>
    </main>
  );
}
