import { useState } from "react";

import type { ParcelaFicha, ParcelaFichaCompleta } from "../../types/parcela";

interface ComparadorYFiltrosPanelProps {
  apiBase: string;
  comparador: ParcelaFichaCompleta[];
  guardadas: ParcelaFicha[];
  onRemoveComparador: (id: number) => void;
  onSelectParcela: (parcela: ParcelaFicha) => void;
}

export function ComparadorYFiltrosPanel({
  apiBase,
  comparador,
  guardadas,
  onRemoveComparador,
  onSelectParcela,
}: ComparadorYFiltrosPanelProps) {
  const [tab, setTab] = useState<"cerrado" | "filtros" | "comparador" | "guardadas">("cerrado");
  const [minSup, setMinSup] = useState("");
  const [maxPendiente, setMaxPendiente] = useState("");
  const [excluirRiesgos, setExcluirRiesgos] = useState(false);
  const [soloFiscales, setSoloFiscales] = useState(false);
  const [filtradas, setFiltradas] = useState<ParcelaFicha[]>([]);
  const [loading, setLoading] = useState(false);

  const runFilter = async (ev: React.FormEvent) => {
    ev.preventDefault();
    setLoading(true);
    try {
      const qs = new URLSearchParams();
      if (minSup) qs.set("min_sup", minSup);
      if (maxPendiente) qs.set("max_pendiente", maxPendiente);
      if (excluirRiesgos) qs.set("excluir_riesgos", "true");
      if (soloFiscales) qs.set("solo_fiscales", "true");
      const resp = await fetch(`${apiBase}/parcelas/filtrar/?${qs.toString()}`);
      if (resp.ok) {
        const data = (await resp.json()) as { resultados: ParcelaFicha[] };
        setFiltradas(data.resultados);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="intel-dock">
      <div className="intel-tabs">
        <button
          type="button"
          className={tab === "filtros" ? "active" : ""}
          onClick={() => setTab(tab === "filtros" ? "cerrado" : "filtros")}
        >
          Filtros
        </button>
        <button
          type="button"
          className={tab === "comparador" ? "active" : ""}
          onClick={() => setTab(tab === "comparador" ? "cerrado" : "comparador")}
        >
          Comparar ({comparador.length})
        </button>
        <button
          type="button"
          className={tab === "guardadas" ? "active" : ""}
          onClick={() => setTab(tab === "guardadas" ? "cerrado" : "guardadas")}
        >
          Guardadas ({guardadas.length})
        </button>
      </div>

      {tab === "filtros" && (
        <div className="intel-body">
          <form onSubmit={(e) => void runFilter(e)} className="filter-form">
            <input
              type="number"
              placeholder="Sup. mín (m²)"
              value={minSup}
              onChange={(e) => setMinSup(e.target.value)}
            />
            <input
              type="number"
              step="0.5"
              placeholder="Pendiente máx (%)"
              value={maxPendiente}
              onChange={(e) => setMaxPendiente(e.target.value)}
            />
            <label>
              <input
                type="checkbox"
                checked={excluirRiesgos}
                onChange={(e) => setExcluirRiesgos(e.target.checked)}
              />{" "}
              Sin amenazas
            </label>
            <label>
              <input
                type="checkbox"
                checked={soloFiscales}
                onChange={(e) => setSoloFiscales(e.target.checked)}
              />{" "}
              Solo fiscales
            </label>
            <button type="submit" disabled={loading}>
              {loading ? "Filtrando..." : "Aplicar filtros"}
            </button>
          </form>
          {filtradas.length > 0 && (
            <ul className="compact-list">
              {filtradas.map((p) => (
                <li key={p.id}>
                  <button type="button" onClick={() => onSelectParcela(p)}>
                    <strong>{p.rol}</strong> · {p.superficie_m2?.toLocaleString("es-CL")} m² ·{" "}
                    {p.destino || "—"}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {tab === "comparador" && (
        <div className="intel-body">
          {comparador.length === 0 ? (
            <p className="status-msg">Agrega hasta 3 parcelas desde su ficha para comparar.</p>
          ) : (
            <table className="compare-table">
              <thead>
                <tr>
                  <th>Métrica</th>
                  {comparador.map((c) => (
                    <th key={c.identificacion.id}>
                      {c.identificacion.rol}{" "}
                      <button
                        type="button"
                        className="tiny-x"
                        onClick={() => onRemoveComparador(c.identificacion.id)}
                      >
                        ×
                      </button>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Puntaje</td>
                  {comparador.map((c) => (
                    <td key={c.identificacion.id}>
                      <strong>{c.puntaje_oportunidad.puntaje_total}</strong>/100
                    </td>
                  ))}
                </tr>
                <tr>
                  <td>Sup. (m²)</td>
                  {comparador.map((c) => (
                    <td key={c.identificacion.id}>
                      {c.identificacion.superficie_m2?.toLocaleString("es-CL") ?? "—"}
                    </td>
                  ))}
                </tr>
                <tr>
                  <td>Fiscal</td>
                  {comparador.map((c) => (
                    <td key={c.identificacion.id}>
                      {c.estatus_fiscal.es_fiscal ? "Sí" : "No"}
                    </td>
                  ))}
                </tr>
                <tr>
                  <td>Zona</td>
                  {comparador.map((c) => (
                    <td key={c.identificacion.id}>
                      {c.normativa[0]?.codigo_zona ?? "—"}
                    </td>
                  ))}
                </tr>
                <tr>
                  <td>Riesgos</td>
                  {comparador.map((c) => (
                    <td key={c.identificacion.id}>{c.riesgos.length}</td>
                  ))}
                </tr>
              </tbody>
            </table>
          )}
        </div>
      )}

      {tab === "guardadas" && (
        <div className="intel-body">
          {guardadas.length === 0 ? (
            <p className="status-msg">No hay parcelas guardadas todavía.</p>
          ) : (
            <ul className="compact-list">
              {guardadas.map((g) => (
                <li key={g.id}>
                  <button type="button" onClick={() => onSelectParcela(g)}>
                    <strong>{g.rol}</strong> · {g.comuna.nombre}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
