// EASE-Grid 2.0 North (EPSG:6931): Lambert azimuthal equal-area, polar aspect, WGS84 ellipsoid.
// Exact ellipsoidal formulas (Snyder 1987, pp. 185-190), so cell corners are correct to < 1 m.
const A = 6378137.0;
const E2 = 0.0066943799901413165;
const E = Math.sqrt(E2);
const D2R = Math.PI / 180;

function q(phi: number): number {
  const s = Math.sin(phi);
  return (1 - E2) * (s / (1 - E2 * s * s) - (1 / (2 * E)) * Math.log((1 - E * s) / (1 + E * s)));
}
const QP = q(Math.PI / 2);

export const RES = 25000;
export const CROP = 360;
export const HALF = (CROP * RES) / 2; // 4,500 km

/** EASE2-N metres -> [lon, lat] degrees. */
export function inverse(x: number, y: number): [number, number] {
  const rho = Math.hypot(x, y);
  const lon = Math.atan2(x, -y) / D2R;
  if (rho < 1e-6) return [0, 90];
  const qq = QP - (rho / A) * (rho / A);
  let phi = Math.asin(Math.max(-1, Math.min(1, qq / 2)));
  for (let k = 0; k < 8; k++) {
    const s = Math.sin(phi);
    const c = Math.cos(phi);
    const one = 1 - E2 * s * s;
    const d =
      ((one * one) / (2 * c)) *
      (qq / (1 - E2) - s / one + (1 / (2 * E)) * Math.log((1 - E * s) / (1 + E * s)));
    phi += d;
    if (Math.abs(d) < 1e-12) break;
  }
  return [lon, phi / D2R];
}

/** [lon, lat] degrees -> EASE2-N metres. */
export function forward(lon: number, lat: number): [number, number] {
  const rho = A * Math.sqrt(Math.max(0, QP - q(lat * D2R)));
  const l = lon * D2R;
  return [rho * Math.sin(l), -rho * Math.cos(l)];
}

/** Fractional (i, j) of a lon/lat point; cell (i, j) covers [i, i+1) x [j, j+1). */
export function lonlatToIJ(lon: number, lat: number): [number, number] {
  const [x, y] = forward(lon, lat);
  return [(HALF - y) / RES, (x + HALF) / RES];
}

/** Corner (ci, cj), 0..CROP, in EASE2 metres. */
export function cornerXY(ci: number, cj: number): [number, number] {
  return [-HALF + RES * cj, HALF - RES * ci];
}
