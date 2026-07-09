import { MARKER_COLORS } from "./graphConfig";
import type {
  DraftMarkers,
  MetaSoftAnalysis,
  MetaSoftPhaseSegment,
  MetaSoftPoint,
  MetaSoftWarmupStage,
} from "../types/metasoft";

type PlotShape = Record<string, unknown>;
const MIN_SPEED_LABEL_SECONDS = 60;

const PHASE_COLORS: Record<string, string> = {
  Repos: "rgba(0, 132, 255, 0.20)",
  Echauffement: "rgba(0, 132, 255, 0.14)",
  Exercice: "rgba(255, 92, 46, 0.18)",
  Recuperation: "rgba(0, 190, 145, 0.16)",
  Récupération: "rgba(0, 190, 145, 0.16)",
  Retablissement: "rgba(0, 190, 145, 0.16)",
  Rétablissement: "rgba(0, 190, 145, 0.16)",
};

export function buildTimeBandShapes(analysis: MetaSoftAnalysis, showSpeedBands = true): PlotShape[] {
  const phaseBands = analysis.phases.filter(hasBounds).map((phase) => ({
    type: "rect",
    xref: "x",
    yref: "paper",
    x0: phase.start_seconds,
    x1: phase.end_seconds,
    y0: 0,
    y1: 0.12,
    fillcolor: PHASE_COLORS[phase.phase] ?? "rgba(255,255,255,0.08)",
    line: { width: 0 },
    layer: "below",
    editable: false,
  }));

  const speedBands = showSpeedBands ? speedSegmentsForAnalysis(analysis).map((stage, index) => ({
    type: "rect",
    xref: "x",
    yref: "paper",
    x0: stage.start_seconds,
    x1: stage.end_seconds,
    y0: 0,
    y1: 1,
    fillcolor: index % 2 === 0 ? "rgba(0, 168, 255, 0.11)" : "rgba(0, 211, 143, 0.09)",
    line: { color: "rgba(255,255,255,0.07)", width: 1 },
    layer: "below",
    editable: false,
  })) : [];

  return [...speedBands, ...phaseBands];
}

export function buildMarkerShapes(markers: DraftMarkers): PlotShape[] {
  return Object.values(markers).flatMap((marker) => {
    if (marker.t_seconds === null) return [];
    const color = MARKER_COLORS[marker.name];
    const shapes: PlotShape[] = [{
      type: "line",
      xref: "x",
      yref: "paper",
      x0: marker.t_seconds,
      x1: marker.t_seconds,
      y0: 0,
      y1: 1,
      line: { color, width: 1, dash: "dot" },
    }];
    if (marker.mode !== "point" && marker.window_start_seconds !== null && marker.window_end_seconds !== null) {
      shapes.push({
        type: "rect",
        xref: "x",
        yref: "paper",
        x0: marker.window_start_seconds,
        x1: marker.window_end_seconds,
        y0: 0,
        y1: 1,
        fillcolor: `${color}22`,
        line: { color: `${color}70`, width: 1 },
        layer: "below",
        editable: false,
      });
    }
    return shapes;
  });
}

export function buildAnnotations(analysis: MetaSoftAnalysis, markers: DraftMarkers) {
  return [...buildStaticAnnotations(analysis), ...buildMarkerAnnotations(markers)];
}

export function buildStaticAnnotations(analysis: MetaSoftAnalysis, showSpeedBands = true) {
  const speedLabels = showSpeedBands ? speedSegmentsForAnalysis(analysis)
    .filter((stage) => (
      typeof stage.start_seconds === "number"
      && typeof stage.end_seconds === "number"
      && stage.end_seconds - stage.start_seconds >= MIN_SPEED_LABEL_SECONDS
    ))
    .map((stage) => ({
      x: ((stage.start_seconds ?? 0) + (stage.end_seconds ?? 0)) / 2,
      y: 0.96,
      xref: "x",
      yref: "paper",
      text: `${formatSpeed(stage.speed_kmh)} km/h`,
      showarrow: false,
      font: { color: "rgba(226,232,240,0.46)", size: 10 },
      bgcolor: "rgba(2, 12, 25, 0.30)",
      bordercolor: "rgba(255,255,255,0.05)",
      borderpad: 2,
    })) : [];
  const phaseLabels = analysis.phases.filter(hasBounds).map((phase) => ({
    x: ((phase.start_seconds ?? 0) + (phase.end_seconds ?? 0)) / 2,
    y: 0.04,
    xref: "x",
    yref: "paper",
    text: phase.phase,
    showarrow: false,
    font: { color: "#d8e6ff", size: 10 },
    bgcolor: "rgba(2, 12, 25, 0.45)",
    bordercolor: "rgba(255,255,255,0.06)",
    borderpad: 3,
  }));
  return [...speedLabels, ...phaseLabels];
}

export function buildMarkerAnnotations(markers: DraftMarkers) {
  const markerLabels = Object.values(markers)
    .filter((marker) => marker.t_seconds !== null)
    .map((marker) => ({
      x: marker.t_seconds,
      y: 1,
      xref: "x",
      yref: "paper",
      text: marker.name === "VO2_max" ? "VO2max" : marker.name,
      showarrow: false,
      yanchor: "bottom",
      font: { color: MARKER_COLORS[marker.name], size: 10 },
    }));
  return markerLabels;
}

function speedSegmentsForAnalysis(analysis: MetaSoftAnalysis): MetaSoftWarmupStage[] {
  const allSpeedSegments = speedSegmentsFromPoints(analysis.points);
  return allSpeedSegments.length ? allSpeedSegments : analysis.warmup_stages.filter(hasBounds);
}

function formatSpeed(value: number): string {
  return value.toLocaleString("fr-FR", { maximumFractionDigits: 1 });
}

function hasBounds(segment: MetaSoftPhaseSegment | MetaSoftWarmupStage): boolean {
  return typeof segment.start_seconds === "number"
    && typeof segment.end_seconds === "number"
    && segment.end_seconds > segment.start_seconds;
}

function speedSegmentsFromPoints(points: MetaSoftPoint[]): MetaSoftWarmupStage[] {
  const segments: MetaSoftWarmupStage[] = [];
  let current: MetaSoftWarmupStage | null = null;
  for (const point of points) {
    const speed = point.values.speed_kmh;
    if (typeof speed !== "number" || typeof point.t_seconds !== "number") continue;
    const rounded = Math.round(speed * 10) / 10;
    if (current && current.speed_kmh === rounded) {
      current.end_seconds = point.t_seconds;
      current.point_count += 1;
      continue;
    }
    if (current && hasBounds(current)) segments.push(current);
    current = {
      stage_index: segments.length + 1,
      speed_kmh: rounded,
      start_seconds: point.t_seconds,
      end_seconds: point.t_seconds,
      point_count: 1,
    };
  }
  if (current && hasBounds(current)) segments.push(current);
  return segments;
}
