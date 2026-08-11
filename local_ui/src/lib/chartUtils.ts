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
const MIN_GRADE_LABEL_SECONDS = 20;

interface GradeSegment {
  grade_percent: number;
  start_seconds: number;
  end_seconds: number;
}

const PHASE_COLORS: Record<string, string> = {
  Repos: "rgba(0, 132, 255, 0.20)",
  Echauffement: "rgba(0, 132, 255, 0.14)",
  Exercice: "rgba(255, 92, 46, 0.18)",
  Recuperation: "rgba(0, 190, 145, 0.16)",
  Récupération: "rgba(0, 190, 145, 0.16)",
  Retablissement: "rgba(0, 190, 145, 0.16)",
  Rétablissement: "rgba(0, 190, 145, 0.16)",
};

export function buildTimeBandShapes(analysis: MetaSoftAnalysis): PlotShape[] {
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

  const speedBands = speedSegmentsForAnalysis(analysis).map((stage, index) => ({
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
  }));

  const gradeBands = gradeSegmentsForAnalysis(analysis).map((segment, index) => ({
    type: "rect",
    xref: "x",
    yref: "paper",
    x0: segment.start_seconds,
    x1: segment.end_seconds,
    y0: 0.84,
    y1: 0.91,
    fillcolor: index % 2 === 0 ? "rgba(255, 184, 77, 0.30)" : "rgba(255, 128, 66, 0.30)",
    line: { color: "rgba(255, 211, 145, 0.55)", width: 1 },
    layer: "below",
    editable: false,
  }));

  return [...speedBands, ...phaseBands, ...gradeBands];
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
      line: { color, width: 2, dash: "dot" },
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

export function buildStaticAnnotations(analysis: MetaSoftAnalysis) {
  const speedLabels = speedSegmentsForAnalysis(analysis)
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
    }));
  const gradeLabels = gradeSegmentsForAnalysis(analysis)
    .filter((segment) => segment.end_seconds - segment.start_seconds >= MIN_GRADE_LABEL_SECONDS)
    .map((segment) => ({
      x: (segment.start_seconds + segment.end_seconds) / 2,
      y: 0.875,
      xref: "x",
      yref: "paper",
      text: `${formatGrade(segment.grade_percent)} %`,
      showarrow: false,
      font: { color: "#fff1d6", size: 10 },
      bgcolor: "rgba(52, 25, 5, 0.72)",
      bordercolor: "rgba(255, 211, 145, 0.30)",
      borderpad: 2,
    }));
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
  return [...speedLabels, ...gradeLabels, ...phaseLabels];
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
      font: { color: MARKER_COLORS[marker.name], size: 14 },
      bgcolor: "rgba(2, 12, 25, 0.82)",
      bordercolor: `${MARKER_COLORS[marker.name]}70`,
      borderpad: 4,
    }));
  return markerLabels;
}

export function speedSegmentsForAnalysis(analysis: MetaSoftAnalysis): MetaSoftWarmupStage[] {
  const allSpeedSegments = speedSegmentsFromPoints(analysis.points);
  return allSpeedSegments.length ? allSpeedSegments : analysis.warmup_stages.filter(hasBounds);
}

export function gradeSegmentsForAnalysis(analysis: MetaSoftAnalysis): GradeSegment[] {
  const segments: GradeSegment[] = [];
  let current = null as GradeSegment | null;
  for (const point of analysis.points) {
    const grade = point.values.grade_percent;
    const time = point.t_seconds;
    if (typeof grade !== "number" || !Number.isFinite(grade) || typeof time !== "number" || !Number.isFinite(time)) {
      if (current && current.end_seconds > current.start_seconds) segments.push(current);
      current = null;
      continue;
    }
    const rounded = Math.round(grade * 10) / 10;
    if (current?.grade_percent === rounded) {
      current.end_seconds = time;
      continue;
    }
    if (current) {
      current.end_seconds = time;
      if (current.end_seconds > current.start_seconds) segments.push(current);
    }
    current = { grade_percent: rounded, start_seconds: time, end_seconds: time };
  }
  if (current && current.end_seconds > current.start_seconds) segments.push(current);
  return segments;
}

export function buildSpeedStepLinePoints(analysis: MetaSoftAnalysis): { x: number[]; y: number[] } {
  const x: number[] = [];
  const y: number[] = [];
  for (const segment of speedSegmentsForAnalysis(analysis).filter(hasBounds)) {
    const start = segment.start_seconds as number;
    const end = segment.end_seconds as number;
    if (x.length > 0 && x[x.length - 1] !== start) {
      x.push(start);
      y.push(y[y.length - 1]);
    }
    x.push(start, end);
    y.push(segment.speed_kmh, segment.speed_kmh);
  }
  return { x, y };
}

export function buildSpeedStepLineShapes(analysis: MetaSoftAnalysis): PlotShape[] {
  const points = buildSpeedStepLinePoints(analysis);
  if (!points.x.length) return [];
  const min = Math.min(...points.y);
  const max = Math.max(...points.y);
  const yPaper = (speed: number) => {
    if (min === max) return 0.5;
    return 0.16 + ((speed - min) / (max - min)) * 0.68;
  };
  return [{
    type: "path",
    xref: "x",
    yref: "paper",
    path: points.x.map((x, index) => `${index === 0 ? "M" : "L"} ${x},${yPaper(points.y[index])}`).join(" "),
    line: { color: "rgba(255, 43, 214, 0.74)", width: 1.1 },
    layer: "below",
    editable: false,
  }];
}

function formatSpeed(value: number): string {
  return value.toLocaleString("fr-FR", { maximumFractionDigits: 1 });
}

function formatGrade(value: number): string {
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
    if (current && current.speed_kmh === rounded && current.phase === point.phase) {
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
      phase: point.phase ?? null,
    };
  }
  if (current && hasBounds(current)) segments.push(current);
  return segments;
}
