export interface MapUrlState {
  lat: number;
  lng: number;
  z: number;
  rol: string | null;
}

const DEFAULT_STATE: MapUrlState = {
  lat: -29.904,
  lng: -71.255,
  z: 14,
  rol: null,
};

export function readMapUrlState(): MapUrlState {
  const params = new URLSearchParams(window.location.search);
  const lat = Number(params.get("lat"));
  const lng = Number(params.get("lng"));
  const z = Number(params.get("z"));
  const rol = params.get("rol");

  return {
    lat: Number.isFinite(lat) && lat >= -90 && lat <= 90 ? lat : DEFAULT_STATE.lat,
    lng: Number.isFinite(lng) && lng >= -180 && lng <= 180 ? lng : DEFAULT_STATE.lng,
    z: Number.isFinite(z) && z >= 2 && z <= 22 ? z : DEFAULT_STATE.z,
    rol: rol && rol.trim() ? rol.trim() : null,
  };
}

export function writeMapUrlState(next: MapUrlState): void {
  const params = new URLSearchParams(window.location.search);
  params.set("lat", next.lat.toFixed(5));
  params.set("lng", next.lng.toFixed(5));
  params.set("z", next.z.toFixed(2));
  if (next.rol) {
    params.set("rol", next.rol);
  } else {
    params.delete("rol");
  }
  const url = `${window.location.pathname}?${params.toString()}`;
  window.history.replaceState(null, "", url);
}
