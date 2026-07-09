import type {
  DraftMarker,
  DraftMarkers,
  MarkerMode,
  MarkerSelectionPayload,
  MetaSoftAnalysis,
  MetaSoftMarkerName,
  MetaSoftMetricKey,
  MetaSoftPoint,
} from "../types/metasoft";

export const MARKER_NAMES: MetaSoftMarkerName[] = ["SV1", "SV2", "VO2_max", "VMA"];
const DEFAULT_WINDOW_SECONDS = 120;
const DEFAULT_PREVIOUS_SECONDS = 10;

export function createInitialMarkers(analysis: MetaSoftAnalysis): DraftMarkers {
  return Object.fromEntries(
    MARKER_NAMES.map((name) => {
      const point = analysis.points.find((item) => normaliseMarker(item.marker) === name);
      return [name, buildDraftMarker(name, analysis.points, point?.t_seconds ?? null, "point")];
    }),
  ) as DraftMarkers;
}

export function buildDraftMarker(
  name: MetaSoftMarkerName,
  points: MetaSoftPoint[],
  tSeconds: number | null,
  mode: MarkerMode = "range",
  windowStart = defaultWindowStart(mode, tSeconds),
  windowEnd = defaultWindowEnd(mode, tSeconds),
): DraftMarker {
  const boundedStart = windowStart === null ? null : Math.max(0, windowStart);
  const boundedEnd = windowEnd === null ? null : Math.max(boundedStart ?? 0, windowEnd);
  const nearest = nearestPoint(points, tSeconds);
  const windowPoints = mode === "point" || boundedStart === null || boundedEnd === null
    ? nearest ? [nearest] : []
    : points.filter((point) => (
      point.t_seconds !== null
      && point.t_seconds >= boundedStart
      && point.t_seconds <= boundedEnd
    ));
  const values = {
    fc_bpm: average(windowPoints, "fc_bpm"),
    vo2_l_min: average(windowPoints, "vo2_l_min"),
    vo2_ml_kg_min: average(windowPoints, "vo2_ml_kg_min"),
    speed_kmh: average(windowPoints, "speed_kmh"),
    rer: average(windowPoints, "rer"),
    de_kcal_h: average(windowPoints, "de_kcal_h"),
    vma: name === "VMA" ? average(windowPoints, "speed_kmh") : null,
  };
  return {
    name,
    mode,
    t_seconds: tSeconds,
    window_start_seconds: boundedStart,
    window_end_seconds: boundedEnd,
    phase: nearest?.phase ?? null,
    point_count: windowPoints.length,
    values,
  };
}

export function serializeMarkerSelections(markers: DraftMarkers): MarkerSelectionPayload[] {
  return MARKER_NAMES.flatMap<MarkerSelectionPayload>((name) => {
    const marker = markers[name];
    if (marker.mode === "point") {
      if (marker.t_seconds === null) return [];
      return [{ name, mode: "point", t_seconds: marker.t_seconds }];
    }
    if (marker.mode === "previous") {
      if (
        marker.t_seconds === null
        || marker.window_start_seconds === null
        || marker.window_end_seconds === null
      ) return [];
      return [{
        name,
        mode: "previous",
        t_seconds: marker.t_seconds,
        window_start_seconds: marker.window_start_seconds,
        window_end_seconds: marker.window_end_seconds,
      }];
    }
    if (marker.window_start_seconds === null || marker.window_end_seconds === null) return [];
    return [{
      name,
      mode: "range",
      ...(marker.t_seconds === null ? {} : { t_seconds: marker.t_seconds }),
      window_start_seconds: marker.window_start_seconds,
      window_end_seconds: marker.window_end_seconds,
    }];
  });
}

function defaultWindowStart(mode: MarkerMode, tSeconds: number | null): number | null {
  if (mode === "point" || tSeconds === null) return null;
  return tSeconds - (mode === "previous" ? DEFAULT_PREVIOUS_SECONDS : DEFAULT_WINDOW_SECONDS);
}

function defaultWindowEnd(mode: MarkerMode, tSeconds: number | null): number | null {
  if (mode === "point" || tSeconds === null) return null;
  return mode === "previous" ? tSeconds : tSeconds + DEFAULT_WINDOW_SECONDS;
}

export function nearestPoint(points: MetaSoftPoint[], tSeconds: number | null): MetaSoftPoint | null {
  if (tSeconds === null) return null;
  return points.reduce<MetaSoftPoint | null>((best, point) => {
    if (point.t_seconds === null) return best;
    if (!best || best.t_seconds === null) return point;
    return Math.abs(point.t_seconds - tSeconds) < Math.abs(best.t_seconds - tSeconds) ? point : best;
  }, null);
}

export function secondsToClock(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds)) return "-";
  const rounded = Math.max(0, Math.round(seconds));
  const h = Math.floor(rounded / 3600);
  const m = Math.floor((rounded % 3600) / 60);
  const s = rounded % 60;
  return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export function formatNumber(value: number | string | null | undefined, digits = 1): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "-";
  return value.toLocaleString("fr-FR", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
}

function average(points: MetaSoftPoint[], key: MetaSoftMetricKey): number | null {
  const values = points
    .map((point) => point.values[key])
    .filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  if (!values.length) return null;
  return Number((values.reduce((sum, value) => sum + value, 0) / values.length).toFixed(3));
}

function normaliseMarker(marker?: string | null): MetaSoftMarkerName | null {
  if (!marker) return null;
  const clean = marker.toUpperCase().replace(/\s+/g, "_");
  if (clean === "VO2MAX" || clean === "VO2_MAX") return "VO2_max";
  return MARKER_NAMES.find((name) => name.toUpperCase() === clean) ?? null;
}
