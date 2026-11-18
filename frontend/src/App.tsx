import { useCallback, useEffect, useState } from "react";

import { ParcelaFichaPanel } from "./features/ficha/ParcelaFichaPanel";
import { ComparadorYFiltrosPanel } from "./features/inteligencia/ComparadorYFiltrosPanel";
import { LayerToggles } from "./features/map/LayerToggles";
import { TerritorioMap } from "./features/map/TerritorioMap";
import { readMapUrlState, writeMapUrlState } from "./features/map/urlState";
import { SearchBar } from "./features/search/SearchBar";
import type {
  LayerVisibility,
  ParcelaFicha,
  ParcelaFichaCompleta,
  PerfilInversion,
} from "./types/parcela";

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "/api/v1";
const SAVED_KEY = "territorio_guardadas_v1";

export function App() {
  const [initialView] = useState(() => readMapUrlState());
  const [ficha, setFicha] = useState<ParcelaFicha | null>(null);
  const [fichaCompleta, setFichaCompleta] = useState<ParcelaFichaCompleta | null>(null);
  const [perfil, setPerfil] = useState<PerfilInversion>("inversionista");
  const [comparador, setComparador] = useState<ParcelaFichaCompleta[]>([]);
  const [guardadas, setGuardadas] = useState<ParcelaFicha[]>(() => {
    try {
      const raw = localStorage.getItem(SAVED_KEY);
      return raw ? (JSON.parse(raw) as ParcelaFicha[]) : [];
    } catch {
      return [];
    }
  });
  const [visibleLayers, setVisibleLayers] = useState<LayerVisibility>({
    fiscal: true,
    normativa: false,
    riesgo: true,
    h3: false,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [flyToTarget, setFlyToTarget] = useState<{
    lng: number;
    lat: number;
    zoom?: number;
  } | null>(null);

  const loadFichaCompleta = useCallback(
    async (parcelaId: number, targetPerfil: PerfilInversion = perfil) => {
      try {
        const resp = await fetch(
          `${API_BASE}/parcelas/${parcelaId}/ficha-completa/?perfil=${encodeURIComponent(targetPerfil)}`
        );
        if (resp.ok) {
          const full = (await resp.json()) as ParcelaFichaCompleta;
          setFichaCompleta(full);
        } else {
          setFichaCompleta(null);
        }
      } catch {
        setFichaCompleta(null);
      }
    },
    [perfil]
  );

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

  const handleChangePerfil = useCallback(
    (nextPerfil: PerfilInversion) => {
      setPerfil(nextPerfil);
      if (ficha) {
        void loadFichaCompleta(ficha.id, nextPerfil);
      }
    },
    [ficha, loadFichaCompleta]
  );

  const handleAddComparador = useCallback((item: ParcelaFichaCompleta) => {
    setComparador((prev) => {
      if (prev.some((x) => x.identificacion.id === item.identificacion.id)) return prev;
      return [...prev.slice(-2), item];
    });
  }, []);

  const handleToggleGuardar = useCallback((parcela: ParcelaFicha) => {
    setGuardadas((prev) => {
      const exists = prev.some((x) => x.id === parcela.id);
      const next = exists ? prev.filter((x) => x.id !== parcela.id) : [...prev, parcela];
      try {
        localStorage.setItem(SAVED_KEY, JSON.stringify(next));
      } catch {
        // Ignora errores de cuota localStorage
      }
      return next;
    });
  }, []);

  return (
    <main className="app-layout">
      <ParcelaFichaPanel
        ficha={ficha}
        fichaCompleta={fichaCompleta}
        perfil={perfil}
        onChangePerfil={handleChangePerfil}
        onAddComparador={handleAddComparador}
        onToggleGuardar={handleToggleGuardar}
        isGuardada={Boolean(ficha && guardadas.some((g) => g.id === ficha.id))}
        loading={loading}
        error={error}
      />
      <section className="map-wrapper">
        <SearchBar apiBase={API_BASE} onSelectResult={handleSelectSearch} />
        <ComparadorYFiltrosPanel
          apiBase={API_BASE}
          comparador={comparador}
          guardadas={guardadas}
          onRemoveComparador={(id) =>
            setComparador((prev) => prev.filter((x) => x.identificacion.id !== id))
          }
          onSelectParcela={handleSelectSearch}
        />
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
