import { secondsToClock } from "./markerUtils";
import type { MetaSoftGraphConfig, MetaSoftSeriesConfig } from "./graphConfig";
import type {
  DraftMarker,
  MarkerMode,
  MetaSoftAnalysis,
  MetaSoftMarkerName,
  MetaSoftPoint,
} from "../types/metasoft";

export type MarkerDragPart = "start" | "center" | "end";
export type MarkerDragTarget = { marker: MetaSoftMarkerName; part: MarkerDragPart };
export type MarkerDragPreview = MarkerDragTarget & { xSeconds: number };

export function averagePointsByTimeBlock(
  points: MetaSoftPoint[],
  blockSeconds: number,
): MetaSoftPoint[] {
  if (blockSeconds <= 0) return points;
  const buckets = new Map<number, MetaSoftPoint[]>();
  for (const point of points) {
    if (typeof point.t_seconds !== "number" || !Number.isFinite(point.t_seconds)) continue;
    const start = Math.floor(point.t_seconds / blockSeconds) * blockSeconds;
    const bucket = buckets.get(start);
    if (bucket) bucket.push(point);
    else buckets.set(start, [point]);
  }
  return Array.from(buckets.entries()).map(([start, bucket]) => {
    const values: MetaSoftPoint["values"] = {};
    const keys = new Set(bucket.flatMap((point) => Object.keys(point.values)));
    for (const key of keys) {
      const numericValues = bucket
        .map((point) => point.values[key as keyof MetaSoftPoint["values"]])
        .filter((value): value is number => typeof value === "number" && Number.isFinite(value));
      if (numericValues.length) {
        values[key as keyof MetaSoftPoint["values"]] = Number(
          (numericValues.reduce((sum, value) => sum + value, 0) / numericValues.length).toFixed(3),
        );
      }
    }
    const tSeconds = start + blockSeconds / 2;
    return {
      index: bucket[0].index,
      t: secondsToClock(tSeconds),
      t_seconds: tSeconds,
      phase: mostFrequent(bucket.map((point) => point.phase ?? null)),
      marker: null,
      values,
    };
  });
}

export function scaledAxisRange(
  values: Array<number | string | null | undefined>,
  scale = 1,
): [number, number] | undefined {
  const numericValues = values.filter(
    (value): value is number => typeof value === "number" && Number.isFinite(value),
  );
  if (!numericValues.length) return undefined;
  const min = Math.min(...numericValues);
  const max = Math.max(...numericValues);
  const center = (min + max) / 2;
  const dataHalfSpan = Math.max((max - min) / 2, Math.abs(center) * 0.01, 0.05);
  const halfSpan = dataHalfSpan * 1.16 * clamp(scale, 0.35, 4);
  return [center - halfSpan, center + halfSpan];
}

export function smoothSeries(
  x: Array<number | null>,
  y: Array<number | string | null | undefined>,
  windowSeconds: number,
): Array<number | string | null | undefined> {
  if (windowSeconds <= 0) return y;
  const radius = windowSeconds / 2;
  let left = 0;
  let right = 0;
  let sum = 0;
  let count = 0;
  return y.map((value, index) => {
    if (typeof value !== "number" || !Number.isFinite(value)) return value;
    const center = x[index];
    if (typeof center !== "number" || !Number.isFinite(center)) return value;
    while (right < y.length) {
      const rightX = x[right];
      if (typeof rightX !== "number" || rightX > center + radius) break;
      const candidate = y[right];
      if (typeof candidate === "number" && Number.isFinite(candidate)) {
        sum += candidate;
        count += 1;
      }
      right += 1;
    }
    while (left < y.length) {
      const leftX = x[left];
      if (typeof leftX !== "number" || leftX >= center - radius) break;
      const candidate = y[left];
      if (typeof candidate === "number" && Number.isFinite(candidate)) {
        sum -= candidate;
        count -= 1;
      }
      left += 1;
    }
    return count ? Number((sum / count).toFixed(3)) : value;
  });
}

export function buildCursorShapes(
  graph: MetaSoftGraphConfig,
  cursorPoint: MetaSoftPoint | null,
): Array<Record<string, unknown>> {
  const tSeconds = cursorPoint?.t_seconds;
  if (graph.kind !== "time" || typeof tSeconds !== "number" || !Number.isFinite(tSeconds)) return [];
  return [{
    type: "line",
    xref: "x",
    yref: "paper",
    x0: tSeconds,
    x1: tSeconds,
    y0: 0,
    y1: 1,
    line: { color: "rgba(248,250,252,0.62)", width: 1, dash: "dash" },
  }];
}

export function buildCursorAnnotations(
  graph: MetaSoftGraphConfig,
  series: MetaSoftSeriesConfig[],
  cursorPoint: MetaSoftPoint | null,
): Array<Record<string, unknown>> {
  const point = cursorPoint;
  const tSeconds = point?.t_seconds;
  if (!point || graph.kind !== "time" || typeof tSeconds !== "number" || !Number.isFinite(tSeconds)) return [];
  const rows = series
    .map((item) => {
      const value = point.values[item.key as keyof MetaSoftPoint["values"]];
      return typeof value === "number" && Number.isFinite(value)
        ? `${item.label} ${formatChartValue(value, item)}${item.unit ? ` ${item.unit}` : ""}`
        : null;
    })
    .filter((value): value is string => value !== null);
  const speed = point.values.speed_kmh;
  if (typeof speed === "number" && Number.isFinite(speed)) {
    rows.push(`Vitesse ${speed.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} km/h`);
  }
  const grade = point.values.grade_percent;
  if (typeof grade === "number" && Number.isFinite(grade)) {
    rows.push(`Pente ${grade.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} %`);
  }
  return [{
    x: tSeconds,
    y: 0.98,
    xref: "x",
    yref: "paper",
    text: [secondsToClock(tSeconds), ...rows].join("<br>"),
    showarrow: false,
    xanchor: "left",
    yanchor: "top",
    align: "left",
    font: { color: "#f8fafc", size: 10 },
    bgcolor: "rgba(6,20,36,0.86)",
    bordercolor: "rgba(248,250,252,0.20)",
    borderpad: 4,
  }];
}

export function isSeriesAvailable(
  analysis: MetaSoftAnalysis,
  graph: MetaSoftGraphConfig,
  series: MetaSoftSeriesConfig,
): boolean {
  if (graph.source === "running_economy") {
    return (analysis.computed.running_economy ?? []).some((row) => row.value_j_kg_m !== null);
  }
  return isXAxisAvailable(analysis, graph)
    && Boolean(analysis.metrics[series.key as keyof typeof analysis.metrics])
    && hasNumericPointValue(analysis, series.key);
}

export function xRangeFromRelayout(event: Readonly<Record<string, unknown>>): [number, number] | null | undefined {
  if (event["xaxis.autorange"] === true) return null;
  const eventRange = toRangeTuple(event["xaxis.range"]);
  if (eventRange) return eventRange;
  const start = toNumber(event["xaxis.range[0]"]);
  const end = toNumber(event["xaxis.range[1]"]);
  if (start === null || end === null || end <= start) return undefined;
  return [start, end];
}

export function previewDraggedMarker(marker: DraftMarker, drag: MarkerDragPreview, maxTime: number): DraftMarker {
  const { tSeconds, mode, windowStart, windowEnd } = draggedMarkerBounds(marker, drag.part, drag.xSeconds, maxTime);
  return {
    ...marker,
    mode,
    t_seconds: tSeconds,
    window_start_seconds: windowStart,
    window_end_seconds: windowEnd,
  };
}

export function draggedMarkerBounds(
  marker: DraftMarker,
  part: MarkerDragPart,
  xSeconds: number,
  maxTime: number,
): { tSeconds: number; mode: MarkerMode; windowStart: number | null; windowEnd: number | null } {
  if (marker.mode === "point" || marker.window_start_seconds === null || marker.window_end_seconds === null) {
    return { tSeconds: xSeconds, mode: "point", windowStart: null, windowEnd: null };
  }
  if (marker.mode === "previous") {
    const duration = Math.max(1, marker.window_end_seconds - marker.window_start_seconds);
    if (part === "start") {
      return {
        tSeconds: marker.t_seconds ?? marker.window_end_seconds,
        mode: "previous",
        windowStart: clamp(xSeconds, 0, marker.window_end_seconds - 1),
        windowEnd: marker.window_end_seconds,
      };
    }
    const tSeconds = clamp(xSeconds, 0, maxTime > 0 ? maxTime : Number.POSITIVE_INFINITY);
    const [windowStart, windowEnd] = previousWindowBounds(tSeconds, duration);
    return { tSeconds, mode: "previous", windowStart, windowEnd };
  }
  if (part === "center") {
    const [windowStart, windowEnd] = centeredWindowBounds(
      xSeconds,
      marker.window_end_seconds - marker.window_start_seconds,
      maxTime,
    );
    return { tSeconds: xSeconds, mode: "range", windowStart, windowEnd };
  }
  const upperBound = maxTime > 0 ? maxTime : Number.POSITIVE_INFINITY;
  const minDuration = 1;
  const maxStart = Math.max(0, marker.window_end_seconds - minDuration);
  const minEnd = marker.window_start_seconds + minDuration;
  const windowStart = part === "start"
    ? clamp(xSeconds, 0, maxStart)
    : marker.window_start_seconds;
  const windowEnd = part === "end"
    ? clamp(xSeconds, minEnd, Math.max(minEnd, upperBound))
    : marker.window_end_seconds;
  return { tSeconds: (windowStart + windowEnd) / 2, mode: "range", windowStart, windowEnd };
}

export function cursorForMarkerDrag(part: MarkerDragPart | null, dragging: boolean): string | undefined {
  if (part === "start" || part === "end") return "ew-resize";
  if (part === "center") return dragging ? "grabbing" : "grab";
  return undefined;
}

export function sameMarkerTarget(left: MarkerDragTarget | null, right: MarkerDragTarget | null): boolean {
  return (left?.marker ?? null) === (right?.marker ?? null)
    && (left?.part ?? null) === (right?.part ?? null);
}

export function sameDragPreview(left: MarkerDragPreview | null, right: MarkerDragPreview | null): boolean {
  return sameMarkerTarget(left, right) && (left?.xSeconds ?? null) === (right?.xSeconds ?? null);
}

export function timeFromClientX(
  clientX: number,
  wrapper: HTMLDivElement | null,
  range: [number, number],
  margin: { l: number; r: number },
): number | null {
  if (!wrapper) return null;
  const bounds = wrapper.getBoundingClientRect();
  const plotLeft = bounds.left + margin.l;
  const plotRight = bounds.right - margin.r;
  const plotWidth = plotRight - plotLeft;
  if (plotWidth <= 0 || clientX < plotLeft || clientX > plotRight) return null;
  return range[0] + ((clientX - plotLeft) / plotWidth) * (range[1] - range[0]);
}

export function centeredWindowBounds(tSeconds: number, durationSeconds: number, maxTime: number): [number, number] {
  const duration = Math.max(1, durationSeconds);
  if (maxTime > 0 && duration >= maxTime) return [0, maxTime];
  let start = tSeconds - duration / 2;
  let end = tSeconds + duration / 2;
  if (start < 0) {
    end -= start;
    start = 0;
  }
  if (maxTime > 0 && end > maxTime) {
    start = Math.max(0, start - (end - maxTime));
    end = maxTime;
  }
  return [start, end];
}

export function previousWindowBounds(tSeconds: number, durationSeconds: number): [number, number] {
  return [Math.max(0, tSeconds - Math.max(1, durationSeconds)), tSeconds];
}

export function markerModeLabel(mode: MarkerMode): string {
  if (mode === "point") return "Ligne";
  if (mode === "previous") return "Precedent";
  return "Range";
}

export function durationToSeconds(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  if (/^\d+([.,]\d+)?$/.test(trimmed)) {
    const parsed = Number(trimmed.replace(",", "."));
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
  }
  const parts = trimmed.split(":").map((part) => Number(part));
  if (parts.length < 2 || parts.length > 3 || parts.some((part) => !Number.isFinite(part) || part < 0)) {
    return null;
  }
  const [hours, minutes, seconds] = parts.length === 3 ? parts : [0, parts[0], parts[1]];
  const total = hours * 3600 + minutes * 60 + seconds;
  return total > 0 ? total : null;
}

export function secondsToDuration(seconds: number): string {
  const rounded = Math.max(1, Math.round(seconds));
  const h = Math.floor(rounded / 3600);
  const m = Math.floor((rounded % 3600) / 60);
  const s = rounded % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function nearestEventPoint(
  points: MetaSoftPoint[],
  event: Readonly<{ points?: Array<{ customdata?: unknown; x?: unknown }> }>,
  graph: MetaSoftGraphConfig,
): MetaSoftPoint | null {
  const pointIndex = event.points?.[0]?.customdata;
  if (typeof pointIndex === "number") {
    return points.find((point) => point.index === pointIndex) ?? null;
  }
  const x = event.points?.[0]?.x;
  if (typeof x !== "number") return null;
  return points.reduce<MetaSoftPoint | null>((best, point) => {
    const pointX = pointXValue(point, graph);
    if (pointX === null) return best;
    if (!best || best.t_seconds === null) return point;
    const bestX = pointXValue(best, graph);
    if (bestX === null) return point;
    return Math.abs(pointX - x) < Math.abs(bestX - x) ? point : best;
  }, null);
}

export function defaultRangeFromValues(values: Array<number | null>, fallbackMax: number): [number, number] {
  const numericValues = values
    .filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  if (!numericValues.length) return [0, fallbackMax];
  const start = Math.min(...numericValues);
  const end = Math.max(...numericValues);
  if (end > start) return [start, end];
  const pad = Math.max(Math.abs(start) * 0.05, 1);
  return [start - pad, end + pad];
}

export function buildTickVals(range: [number, number]): number[] {
  const span = range[1] - range[0];
  if (span <= 0) return [];
  const step = span > 5400 ? 1200 : span > 2400 ? 600 : 300;
  const vals = [];
  for (let value = Math.ceil(range[0] / step) * step; value <= range[1]; value += step) vals.push(value);
  return vals;
}

export function pointXValue(point: MetaSoftPoint, graph: MetaSoftGraphConfig): number | null {
  if (graph.xAxis.key === "t_seconds") return point.t_seconds;
  if (graph.xAxis.key === "stage_index") return null;
  const value = point.values[graph.xAxis.key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function axisTitle(axis: MetaSoftGraphConfig["xAxis"]): string {
  return axis.unit ? `${axis.label} (${axis.unit})` : axis.label;
}

export function axisLabel(series: MetaSoftSeriesConfig[], axis: "y" | "y2"): string {
  const units = series
    .filter((item) => item.axis === axis)
    .map((item) => item.unit)
    .filter((unit): unit is string => Boolean(unit));
  return Array.from(new Set(units)).join(" / ");
}

export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function formatChartValue(value: number, series: MetaSoftSeriesConfig): string {
  return value.toLocaleString("fr-FR", { maximumFractionDigits: series.unit === "bpm" ? 0 : 2 });
}

function isXAxisAvailable(
  analysis: MetaSoftAnalysis,
  graph: MetaSoftGraphConfig,
): boolean {
  if (graph.xAxis.key === "t_seconds" || graph.xAxis.key === "stage_index") return true;
  return Boolean(analysis.metrics[graph.xAxis.key]) && hasNumericPointValue(analysis, graph.xAxis.key);
}

function hasNumericPointValue(
  analysis: MetaSoftAnalysis,
  key: MetaSoftSeriesConfig["key"] | MetaSoftGraphConfig["xAxis"]["key"],
): boolean {
  if (key === "t_seconds" || key === "stage_index" || key === "value_j_kg_m") return true;
  return analysis.points.some((point) => {
    const value = point.values[key];
    return typeof value === "number" && Number.isFinite(value);
  });
}

function toRangeTuple(value: unknown): [number, number] | null {
  if (!Array.isArray(value) || value.length !== 2) return null;
  const start = toNumber(value[0]);
  const end = toNumber(value[1]);
  if (start === null || end === null || end <= start) return null;
  return [start, end];
}

function toNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function mostFrequent<T>(values: T[]): T | null {
  if (!values.length) return null;
  const counts = new Map<T, number>();
  for (const value of values) counts.set(value, (counts.get(value) ?? 0) + 1);
  return values.reduce((best, value) => (
    (counts.get(value) ?? 0) > (counts.get(best) ?? 0) ? value : best
  ));
}
