import type { LayerVisibility } from "../../types/parcela";

interface LayerTogglesProps {
  layers: LayerVisibility;
  onToggle: (key: keyof LayerVisibility) => void;
}

const LAYER_ITEMS: Array<{
  key: keyof LayerVisibility;
  label: string;
  colorClass: string;
}> = [
  { key: "fiscal", label: "Terrenos fiscales", colorClass: "swatch-fiscal" },
  { key: "normativa", label: "Normativa urbana", colorClass: "swatch-normativa" },
  { key: "riesgo", label: "Riesgos naturales", colorClass: "swatch-riesgo" },
];

export function LayerToggles({ layers, onToggle }: LayerTogglesProps) {
  return (
    <div className="layer-toggles" role="group" aria-label="Capas territoriales">
      <div className="layer-toggles-title">Capas MVT</div>
      {LAYER_ITEMS.map((item) => (
        <label key={item.key} className="layer-toggle-item">
          <input
            type="checkbox"
            checked={layers[item.key]}
            onChange={() => onToggle(item.key)}
          />
          <span className={`swatch ${item.colorClass}`} />
          <span>{item.label}</span>
        </label>
      ))}
    </div>
  );
}
