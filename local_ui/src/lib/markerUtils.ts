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

export const MARKER_NAMES: MetaSoftMarkerName[] = [
  "SV1",
  "SV2",
  "VO2_max",
  "FC_max",
  "VMA",
  "Cross-over",
];
const DEFAULT_WINDOW_SECONDS = 120;
const DEFAULT_PREVIOUS_SECONDS = 10;

export function createInitialMarkers(analysis: MetaSoftAnalysis): DraftMarkers {
  const markers = Object.fromEntries(
    MARKER_NAMES.map((name) => {
      const point = analysis.points.find((item) => normaliseMarker(item.marker) === name);
      return [name, buildDraftMarker(name, analysis.points, point?.t_seconds ?? null, "point")];
    }),
  ) as DraftMarkers;
  if (markers.FC_max.t_seconds === null) {
    const proposal = detectFcMaxProposal(analysis.points);
    if (proposal) {
      markers.FC_max = {
        ...buildDraftMarker("FC_max", analysis.points, proposal.t_seconds, "point"),
        proposal: {
          source: "auto_fc_max",
          raw_peak_bpm: proposal.raw_peak_bpm,
          average_5s_bpm: proposal.average_5s_bpm,
          isolated: proposal.isolated,
        },
      };
    }
  }
  return markers;
}

export function detectFcMaxProposal(points: MetaSoftPoint[]): {
  t_seconds: number;
  raw_peak_bpm: number;
  average_5s_bpm: number;
  isolated: boolean;
} | null {
  const numeric = points.filter((point) => (
    typeof point.t_seconds === "number"
    && Number.isFinite(point.t_seconds)
    && typeof point.values.fc_bpm === "number"
    && Number.isFinite(point.values.fc_bpm)
  ));
  const exercise = numeric.filter((point) => normalisePhase(point.phase) === "exercice");
  const candidates = exercise.length ? exercise : numeric;
  if (!candidates.length) return null;
  const peak = candidates.reduce((best, point) => (
    (point.values.fc_bpm as number) > (best.values.fc_bpm as number) ? point : best
  ));
  const peakTime = peak.t_seconds as number;
  const windowValues = candidates
    .filter((point) => Math.abs((point.t_seconds as number) - peakTime) <= 2.5)
    .map((point) => point.values.fc_bpm as number);
  const average5s = windowValues.reduce((sum, value) => sum + value, 0) / windowValues.length;
  const rawPeak = peak.values.fc_bpm as number;
  return {
    t_seconds: peakTime,
    raw_peak_bpm: Number(rawPeak.toFixed(1)),
    average_5s_bpm: Number(average5s.toFixed(1)),
    // ponytail: seuil visuel simple; passer a une qualification capteur si les coachs fournissent des artefacts etiquetes.
    isolated: rawPeak - average5s > 5,
  };
}

export function buildDraftMarker(
  name: MetaSoftMarkerName,
  points: MetaSoftPoint[],
  tSeconds: number | null,
  mode: MarkerMode = "range",
  windowStart = defaultWindowStart(mode, tSeconds),
  windowEnd = defaultWindowEnd(mode, tSeconds),
  windowEndExclusive = false,
  phaseFilter: string | null = null,
): DraftMarker {
  const boundedStart = windowStart === null ? null : Math.max(0, windowStart);
  const boundedEnd = windowEnd === null ? null : Math.max(boundedStart ?? 0, windowEnd);
  const eligiblePoints = phaseFilter
    ? points.filter((point) => point.phase === phaseFilter)
    : points;
  const nearest = nearestPoint(eligiblePoints, tSeconds);
  const windowPoints = mode === "point" || boundedStart === null || boundedEnd === null
    ? nearest ? [nearest] : []
    : eligiblePoints.filter((point) => (
      point.t_seconds !== null
      && point.t_seconds >= boundedStart
      && (windowEndExclusive ? point.t_seconds < boundedEnd : point.t_seconds <= boundedEnd)
    ));
  const dechoKcalH = average(windowPoints, "decho_kcal_h");
  const defatKcalH = average(windowPoints, "defat_kcal_h");
  const substratePercentages = oxidationPercentages(dechoKcalH, defatKcalH);
  const values = {
    fc_bpm: average(windowPoints, "fc_bpm"),
    vo2_l_min: average(windowPoints, "vo2_l_min"),
    vo2_ml_kg_min: average(windowPoints, "vo2_ml_kg_min"),
    speed_kmh: average(windowPoints, "speed_kmh"),
    rer: average(windowPoints, "rer"),
    de_kcal_h: average(windowPoints, "de_kcal_h"),
    decho_kcal_h: dechoKcalH,
    defat_kcal_h: defatKcalH,
    fat_percent: substratePercentages.fat,
    cho_percent: substratePercentages.cho,
    vma: name === "VMA" ? average(windowPoints, "speed_kmh") : null,
  };
  return {
    name,
    mode,
    t_seconds: tSeconds,
    window_start_seconds: boundedStart,
    window_end_seconds: boundedEnd,
    window_end_exclusive: mode === "range" && windowEndExclusive,
    phase_filter: phaseFilter,
    phase: nearest?.phase ?? null,
    point_count: windowPoints.length,
    values,
  };
}

export function serializeMarkerSelections(
  markers: DraftMarkers,
  dirtyMarkers: Set<MetaSoftMarkerName>,
): MarkerSelectionPayload[] {
  return MARKER_NAMES.flatMap<MarkerSelectionPayload>((name) => {
    if (!dirtyMarkers.has(name)) return [];
    const marker = markers[name];
    if (
      marker.t_seconds === null
      && marker.window_start_seconds === null
      && marker.window_end_seconds === null
    ) {
      return [{ name, action: "delete" }];
    }
    if (marker.mode === "point") {
      return [{
        name,
        action: "upsert",
        mode: "point",
        t_seconds: marker.t_seconds,
        ...(marker.phase_filter ? { phase_filter: marker.phase_filter } : {}),
      }];
    }
    if (marker.mode === "previous") {
      return [{
        name,
        action: "upsert",
        mode: "previous",
        t_seconds: marker.t_seconds,
        window_start_seconds: marker.window_start_seconds,
        window_end_seconds: marker.window_end_seconds,
        ...(marker.phase_filter ? { phase_filter: marker.phase_filter } : {}),
      }];
    }
    return [{
      name,
      action: "upsert",
      mode: "range",
      ...(marker.t_seconds === null ? {} : { t_seconds: marker.t_seconds }),
      window_start_seconds: marker.window_start_seconds,
      window_end_seconds: marker.window_end_seconds,
      ...(marker.window_end_exclusive ? { window_end_exclusive: true } : {}),
      ...(marker.phase_filter ? { phase_filter: marker.phase_filter } : {}),
    }];
  });
}

export function restoreDraftMarkerSelections(
  markers: DraftMarkers,
  points: MetaSoftPoint[],
  selections: MarkerSelectionPayload[],
): { markers: DraftMarkers; dirty: Set<MetaSoftMarkerName> } {
  const restored = { ...markers };
  const dirty = new Set<MetaSoftMarkerName>();
  for (const selection of selections) {
    if (!MARKER_NAMES.includes(selection.name)) continue;
    const name = selection.name;
    if (selection.action === "delete") {
      restored[name] = buildDraftMarker(name, points, null, "point");
      dirty.add(name);
      continue;
    }
    const mode = selection.mode ?? "point";
    restored[name] = buildDraftMarker(
      name,
      points,
      selection.t_seconds ?? null,
      mode,
      selection.window_start_seconds ?? null,
      selection.window_end_seconds ?? null,
      selection.window_end_exclusive === true,
      selection.phase_filter ?? null,
    );
    dirty.add(name);
  }
  return { markers: restored, dirty };
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

function oxidationPercentages(
  dechoKcalH: number | null,
  defatKcalH: number | null,
): { fat: number | null; cho: number | null } {
  if (dechoKcalH === null || defatKcalH === null) return { fat: null, cho: null };
  const total = dechoKcalH + defatKcalH;
  if (!Number.isFinite(total) || total <= 0) return { fat: null, cho: null };
  return {
    fat: Number(((defatKcalH / total) * 100).toFixed(3)),
    cho: Number(((dechoKcalH / total) * 100).toFixed(3)),
  };
}

function normaliseMarker(marker?: string | null): MetaSoftMarkerName | null {
  if (!marker) return null;
  const clean = marker.toUpperCase().replace(/\s+/g, "_");
  if (clean === "VO2MAX" || clean === "VO2_MAX") return "VO2_max";
  return MARKER_NAMES.find((name) => name.toUpperCase() === clean) ?? null;
}

function normalisePhase(phase?: string | null): string {
  return String(phase ?? "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim().toLowerCase();
}
