import { useState } from "react";

import type { BuscarResponse, ParcelaFicha } from "../../types/parcela";

interface SearchBarProps {
  apiBase: string;
  onSelectResult: (parcela: ParcelaFicha) => void;
}

export function SearchBar({ apiBase, onSelectResult }: SearchBarProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ParcelaFicha[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  const handleSubmit = async (ev: React.FormEvent) => {
    ev.preventDefault();
    const cleaned = query.trim();
    if (!cleaned) return;

    setSearching(true);
    setSearchError(null);
    try {
      const resp = await fetch(
        `${apiBase}/parcelas/buscar/?q=${encodeURIComponent(cleaned)}&limit=8`
      );
      if (!resp.ok) {
        throw new Error(`Error ${resp.status} en búsqueda`);
      }
      const data = (await resp.json()) as BuscarResponse;
      setResults(data.resultados);
      if (data.resultados.length === 1) {
        onSelectResult(data.resultados[0]);
      } else if (data.resultados.length === 0) {
        setSearchError("Sin coincidencias para esa búsqueda.");
      }
    } catch (err) {
      setSearchError(err instanceof Error ? err.message : "Error al buscar");
    } finally {
      setSearching(false);
    }
  };

  return (
    <div className="search-box">
      <form onSubmit={(e) => void handleSubmit(e)} className="search-form">
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Buscar rol (00101-00001) o lat, lng..."
          aria-label="Buscar parcela por rol o coordenadas"
        />
        <button type="submit" disabled={searching}>
          {searching ? "..." : "Buscar"}
        </button>
      </form>

      {searchError && <p className="search-error">{searchError}</p>}

      {results.length > 1 && (
        <ul className="search-results">
          {results.map((item) => (
            <li key={`${item.id}-${item.vigente_desde ?? ""}`}>
              <button
                type="button"
                className="search-result-btn"
                onClick={() => {
                  onSelectResult(item);
                  setResults([]);
                }}
              >
                <strong>{item.rol}</strong> · {item.comuna.nombre} ({item.procedencia.confianza})
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
