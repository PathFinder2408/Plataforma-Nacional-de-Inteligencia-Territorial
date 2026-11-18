import type { ParcelaFicha } from "../../types/parcela";

interface ParcelaFichaPanelProps {
  ficha: ParcelaFicha | null;
  loading: boolean;
  error: string | null;
}

export function ParcelaFichaPanel({ ficha, loading, error }: ParcelaFichaPanelProps) {
  return (
    <aside className="ficha-panel" aria-label="Ficha territorial">
      <header className="ficha-header">
        <h1>Inteligencia Territorial</h1>
        <p className="subtitle">Haz clic en una parcela para consultar su ficha</p>
      </header>

      {loading && <p className="status-msg">Consultando parcela...</p>}
      {error && <p className="error-msg">{error}</p>}

      {!loading && !error && !ficha && (
        <p className="status-msg">Sin parcela seleccionada.</p>
      )}

      {ficha && (
        <div className="ficha-body">
          <div className="ficha-title-row">
            <h2>Rol {ficha.rol}</h2>
            <span className={`badge badge-${ficha.procedencia.confianza}`}>
              Confianza: {ficha.procedencia.confianza}
            </span>
          </div>

          <dl className="ficha-grid">
            <dt>Comuna</dt>
            <dd>
              {ficha.comuna.nombre} ({ficha.comuna.codigo_ine})
            </dd>
            <dt>Superficie calculada</dt>
            <dd>
              {ficha.superficie_m2 !== null
                ? `${ficha.superficie_m2.toLocaleString("es-CL")} m²`
                : "—"}
            </dd>
            <dt>Superficie declarada</dt>
            <dd>
              {ficha.superficie_declarada !== null
                ? `${ficha.superficie_declarada.toLocaleString("es-CL")} m²`
                : "—"}
            </dd>
            <dt>Destino / Serie</dt>
            <dd>
              {ficha.destino || "—"} ({ficha.serie})
            </dd>
            <dt>Avalúo fiscal</dt>
            <dd>
              {ficha.avaluo_fiscal !== null
                ? `$${ficha.avaluo_fiscal.toLocaleString("es-CL")}`
                : "—"}
            </dd>
            <dt>Vigencia</dt>
            <dd>
              {ficha.vigente_desde ?? "—"} → {ficha.vigente_hasta ?? "Vigente"}
            </dd>
          </dl>

          <section className="procedencia-box">
            <h3>Procedencia del dato</h3>
            <p>
              <strong>Fuente:</strong> {ficha.procedencia.fuente}
            </p>
            <p>
              <strong>Fecha de corte:</strong> {ficha.procedencia.fecha_corte ?? "—"}
            </p>
            <p>
              <strong>Licencia:</strong> {ficha.procedencia.licencia}
            </p>
            <p className="disclaimer">
              Cartografía referencial: no acredita deslindes ni reemplaza certificados oficiales.
            </p>
          </section>
        </div>
      )}
    </aside>
  );
}
