// Data interface. Mirrors docs/CONTRACT.md "Web export" plus the keys documented in web/README.md.

export interface LayerMeta {
  scale: number;
  offset: number;
  unit: string;
  title: string;
  source?: string; // human-readable source line, e.g. "CPOM CS2, Petty et al. fusion, AWI CS2SMOS"
  date?: string; // may contain {W} (winter start year) and {W1} (W + 1)
  unc?: string; // free-text uncertainty note
  unc_layer?: string; // name of another layer that holds a per-cell uncertainty (same unit)
  flags?: Record<string, string>; // for bitmask layers: bit value -> label
}

export interface Winter {
  w: number;
  ice_km2?: number; // area of ice-capable cells modelled this winter (used for the 5% line)
  label: string;
  partial?: boolean;
  layers?: string[]; // optional: layers that carry data this winter (others treated as absent)
  note?: string;
}

export interface Source {
  id: string;
  name: string;
  short?: string;
  authors?: string;
  citation?: string;
  doi?: string;
  url?: string;
  licence?: string;
  accessed?: string;
}

export interface Manifest {
  fixture?: boolean;
  built: string;
  grid: { name?: string; epsg?: number; res?: number; res_m?: number; crop?: number; half?: number; half_m?: number; cell_area_km2?: number };
  n_cells: number;
  winters: Winter[];
  default_winter?: number;
  static_layers: string[];
  winter_layers: string[];
  layers: Record<string, LayerMeta>;
  sources?: Source[];
}

export interface Card {
  meaning: string;
  why: string;
  not_proof: string;
  example: string;
}

export interface HindcastRow { label: string; value: number; model?: boolean }
export interface HindcastMetric { key: string; label: string; rows: HindcastRow[]; higher_is_better?: boolean }

export interface Summary {
  fixture?: boolean;
  built?: string;
  ensemble_n?: number;
  thresholds?: { survives?: number; hopeless?: number; uplift?: number; guard_m?: number; blocked_frac?: number };
  scale?: {
    target_km2?: number;
    target_source?: string;
    mwh_per_km2?: number;
    energy_source?: string;
    ice_safe_days?: number;
    ice_safe_note?: string;
    arctic_ice_area_km2?: number;
    arctic_ice_area_source?: string;
    throughput_default?: number;
    throughput_min?: number;
    throughput_max?: number;
    share_of_ice_area?: number;
  };
  calibration?: {
    site?: string;
    winter?: number;
    winter_label?: string;
    modelled_cm: number;
    uncalibrated_cm?: number;
    paper_cm: number;
    modelled_range_cm?: [number, number];
    alpha?: number;
    source?: string;
    date?: string;
    note?: string;
  };
  hindcast?: { period?: string; source?: string; date?: string; metrics: HindcastMetric[]; verdict?: string; beats_both?: boolean; beats_label?: string };
  sensitivity?: {
    target?: string;
    unit?: string;
    method?: string;
    winter?: number;
    base?: number;
    rows: { key?: string; label: string; value?: number; low?: number; high?: number; detail?: string }[];
  };
  cards?: Record<string, Card>;
  limits?: { title: string; body: string }[];
}

declare global {
  interface Window {
    __ATLAS_DATA__?: Record<string, unknown>;
  }
}
