import type { ParcelaFicha, ParcelaFichaCompleta, ProcedenciaDato } from "../../types/parcela";

interface ParcelaFichaPanelProps {
  ficha: ParcelaFicha | null;
  fichaCompleta: ParcelaFichaCompleta | null;
  loading: boolean;
  error: string | null;
}

function ProvenanceMeta({ data }: { data: ProcedenciaDato }) {
  return (
    <p className="meta-line">
      Fuente: {data.fuente} · Corte: {data.fecha_corte ?? "—"} · Confianza:{" "}
      <strong>{data.confianza}</strong>
    </p>
  );
}

export function ParcelaFichaPanel({
  ficha,
  fichaCompleta,
  loading,
  error,
}: ParcelaFichaPanelProps) {
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
            <h3>Procedencia identificación</h3>
            <ProvenanceMeta data={ficha.procedencia} />
            <p className="meta-line">Licencia: {ficha.procedencia.licencia}</p>
          </section>

          {fichaCompleta && (
            <>
              <section className="detail-section">
                <div className="section-head">
                  <h3>Estatus fiscal</h3>
                  <span
                    className={`badge ${
                      fichaCompleta.estatus_fiscal.es_fiscal
                        ? "badge-media"
                        : "badge-alta"
                    }`}
                  >
                    {fichaCompleta.estatus_fiscal.es_fiscal ? "Fiscal" : "Privado / No fiscal"}
                  </span>
                </div>
                {fichaCompleta.estatus_fiscal.coincidencias.map((item) => (
                  <div key={item.codigo_bn} className="subcard">
                    <p>
                      <strong>{item.codigo_bn}</strong> · {item.institucion} ({item.tipo})
                    </p>
                    <p className="meta-line">Traslape: {item.porcentaje_traslape ?? "—"} %</p>
                    <ProvenanceMeta data={item.procedencia} />
                  </div>
                ))}
              </section>

              <section className="detail-section">
                <h3>Normativa y cabida referencial</h3>
                {fichaCompleta.normativa.length === 0 && (
                  <p className="status-msg">Sin zonificación cargada para esta parcela.</p>
                )}
                {fichaCompleta.normativa.map((zona) => (
                  <div key={`${zona.instrumento}-${zona.codigo_zona}`} className="subcard">
                    <p>
                      <strong>
                        {zona.instrumento} · {zona.codigo_zona}
                      </strong>{" "}
                      {zona.nombre_zona}
                    </p>
                    <p className="meta-line">
                      Usos: {zona.usos_permitidos.join(", ") || "—"}
                    </p>
                    {zona.cabida_referencial && (
                      <div className="cabida-grid">
                        <span>
                          Ocupación máx:{" "}
                          <strong>
                            {zona.cabida_referencial.ocupacion_max_m2?.toLocaleString("es-CL") ??
                              "—"}{" "}
                            m²
                          </strong>
                        </span>
                        <span>
                          Edificabilidad máx:{" "}
                          <strong>
                            {zona.cabida_referencial.edificabilidad_max_m2?.toLocaleString(
                              "es-CL"
                            ) ?? "—"}{" "}
                            m²
                          </strong>
                        </span>
                        <span>
                          Altura máx:{" "}
                          <strong>{zona.cabida_referencial.altura_max_m ?? "—"} m</strong>
                        </span>
                      </div>
                    )}
                    <ProvenanceMeta data={zona.procedencia} />
                  </div>
                ))}
              </section>

              <section className="detail-section">
                <h3>Riesgos y amenazas</h3>
                {fichaCompleta.riesgos.length === 0 && (
                  <p className="status-msg">Sin amenazas registradas en capas cargadas.</p>
                )}
                {fichaCompleta.riesgos.map((r) => (
                  <div key={r.codigo_evento} className="subcard subcard-risk">
                    <p>
                      <strong>{r.tipo}</strong> · Nivel{" "}
                      <span className="risk-level">{r.nivel}</span> ({r.porcentaje_afectacion ?? "—"}
                      %)
                    </p>
                    {r.descripcion && <p className="meta-line">{r.descripcion}</p>}
                    <ProvenanceMeta data={r.procedencia} />
                  </div>
                ))}
              </section>

              <section className="detail-section">
                <h3>Relieve y entorno (DEM)</h3>
                {fichaCompleta.relieve ? (
                  <div className="subcard">
                    <p>
                      Elevación media: <strong>{fichaCompleta.relieve.elevacion_media_m} m</strong>{" "}
                      · Pendiente:{" "}
                      <strong>{fichaCompleta.relieve.pendiente_media_pct ?? "—"} %</strong> ·
                      Exposición: <strong>{fichaCompleta.relieve.exposicion_aspecto || "—"}</strong>
                    </p>
                    {fichaCompleta.relieve.procedencia && (
                      <ProvenanceMeta data={fichaCompleta.relieve.procedencia} />
                    )}
                  </div>
                ) : (
                  <p className="status-msg">Sin datos de relieve cargados.</p>
                )}
              </section>

              <p className="disclaimer">{fichaCompleta.descargo_general}</p>
            </>
          )}
        </div>
      )}
    </aside>
  );
}
