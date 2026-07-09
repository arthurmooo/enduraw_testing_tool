import type {
  ManualRunningEconomyExclusion,
  ManualRunningEconomyRow,
  MetaSoftAnalysis,
  MetaSoftMetricKey,
  MetaSoftPoint,
  MetaSoftWarmupStage,
} from "../types/metasoft";

export interface ManualEconomyDraft {
  stageIndex: number;
  enabled: boolean;
  startSeconds: number;
  endSeconds: number;
  exclusions: ManualRunningEconomyExclusion[];
}

export interface ManualRunningEconomySelection {
  stage_index: number;
  start_seconds: number;
  end_seconds: number;
  exclusions: ManualRunningEconomyExclusion[];
}

export interface ManualRunningEconomyStageSelection {
  stage_index: number;
  enabled: boolean;
}

export function initialEconomyDraft(stage: MetaSoftWarmupStage): ManualEconomyDraft {
  const start = numberOr(stage.start_seconds, 0);
  const end = numberOr(stage.end_seconds, start);
  return {
    stageIndex: stage.stage_index,
    enabled: true,
    startSeconds: round3(Math.max(start, end - 30)),
    endSeconds: round3(end),
    exclusions: [],
  };
}

export function clampDraftToStage(draft: ManualEconomyDraft, stage: MetaSoftWarmupStage): ManualEconomyDraft {
  const min = numberOr(stage.start_seconds, draft.startSeconds);
  const max = numberOr(stage.end_seconds, draft.endSeconds);
  const start = clamp(Math.min(draft.startSeconds, draft.endSeconds), min, max);
  const end = clamp(Math.max(draft.startSeconds, draft.endSeconds), start, max);
  return {
    ...draft,
    stageIndex: stage.stage_index,
    startSeconds: round3(start),
    endSeconds: round3(end),
    exclusions: normalizeExclusions(draft.exclusions, start, end),
  };
}

export function normalizeExclusions(
  exclusions: ManualRunningEconomyExclusion[],
  startSeconds: number,
  endSeconds: number,
): ManualRunningEconomyExclusion[] {
  const sorted = exclusions
    .map((item) => ({
      start_seconds: clamp(Math.min(item.start_seconds, item.end_seconds), startSeconds, endSeconds),
      end_seconds: clamp(Math.max(item.start_seconds, item.end_seconds), startSeconds, endSeconds),
    }))
    .filter((item) => item.end_seconds > item.start_seconds)
    .sort((left, right) => left.start_seconds - right.start_seconds);
  const merged: ManualRunningEconomyExclusion[] = [];
  for (const item of sorted) {
    const last = merged[merged.length - 1];
    if (last && item.start_seconds <= last.end_seconds) {
      last.end_seconds = Math.max(last.end_seconds, item.end_seconds);
    } else {
      merged.push({ ...item });
    }
  }
  return merged.map((item) => ({
    start_seconds: round3(item.start_seconds),
    end_seconds: round3(item.end_seconds),
  }));
}

export function buildManualEconomyPreviewRow(
  analysis: MetaSoftAnalysis,
  stage: MetaSoftWarmupStage,
  draft: ManualEconomyDraft,
  profileVo2maxMlKgMin: number | null,
): ManualRunningEconomyRow {
  const bounded = clampDraftToStage(draft, stage);
  const selectedPoints = pointsInRange(analysis.points, bounded.startSeconds, bounded.endSeconds);
  const includedPoints = selectedPoints.filter((point) => !isExcluded(point.t_seconds, bounded.exclusions));
  const usablePoints = includedPoints.filter((point) => (
    numeric(point.values.vo2_l_min) !== null && numeric(point.values.vco2_l_min) !== null
  ));
  const noUsablePoints = selectedPoints.length > 0 && usablePoints.length === 0;
  const rest = analysis.computed.rest_baseline;
  const mass = analysis.athlete.weight_kg;
  const speedMMin = stage.speed_kmh * 1000 / 60;
  const vo2 = average(usablePoints, "vo2_l_min");
  const vo2MlKg = average(usablePoints, "vo2_ml_kg_min");
  const vco2 = average(usablePoints, "vco2_l_min");
  const percentVo2 = vo2MlKg ?? (
    vo2 !== null && typeof mass === "number" && mass > 0 ? vo2 * 1000 / mass : null
  );
  const canCompute = usablePoints.length > 0
    && typeof mass === "number"
    && mass > 0
    && speedMMin > 0
    && rest
    && vo2 !== null
    && vco2 !== null;
  const ec = canCompute
    ? (((0.00055 * (vco2 * 1000 - rest.vco2_ml_min))
      + (0.004471 * (vo2 * 1000 - rest.vo2_ml_min))) * 4184 / (mass * speedMMin))
    : null;

  return {
    stage_index: stage.stage_index,
    speed_kmh: stage.speed_kmh,
    start_seconds: bounded.startSeconds,
    end_seconds: bounded.endSeconds,
    exclusions: bounded.exclusions,
    point_count: usablePoints.length,
    vo2_l_min: roundOrNull(vo2, 3),
    vco2_l_min: roundOrNull(vco2, 3),
    ec_j_kg_m: roundOrNull(ec, 3),
    percent_vo2max: percentVo2 !== null && profileVo2maxMlKgMin
      ? roundOrNull((percentVo2 / profileVo2maxMlKgMin) * 100, 3)
      : null,
    de_kcal_h: roundOrNull(average(usablePoints, "de_kcal_h"), 3),
    decho_kcal_h: roundOrNull(average(usablePoints, "decho_kcal_h"), 3),
    defat_kcal_h: roundOrNull(average(usablePoints, "defat_kcal_h"), 3),
    depro_kcal_h: roundOrNull(average(usablePoints, "depro_kcal_h"), 3),
    sources: { selection: "preview_manual_stable_stage", artefacts: "excluded_raw_points" },
    warning: noUsablePoints ? "Aucun point VO2/VCO2 utilisable." : null,
  };
}

export function manualEconomySelection(
  stage: MetaSoftWarmupStage,
  draft: ManualEconomyDraft,
): ManualRunningEconomySelection {
  const bounded = clampDraftToStage(draft, stage);
  return {
    stage_index: bounded.stageIndex,
    start_seconds: bounded.startSeconds,
    end_seconds: bounded.endSeconds,
    exclusions: bounded.exclusions,
  };
}

export function manualEconomyStageSelection(
  stage: MetaSoftWarmupStage,
  draft: ManualEconomyDraft,
): ManualRunningEconomyStageSelection {
  return {
    stage_index: stage.stage_index,
    enabled: clampDraftToStage(draft, stage).enabled,
  };
}

export function correctedSeries(
  points: MetaSoftPoint[],
  exclusions: ManualRunningEconomyExclusion[],
  key: MetaSoftMetricKey,
): Array<number | null> {
  return points.map((point) => isExcluded(point.t_seconds, exclusions) ? null : numeric(point.values[key]));
}

function pointsInRange(points: MetaSoftPoint[], start: number, end: number): MetaSoftPoint[] {
  return points.filter((point) => (
    typeof point.t_seconds === "number"
    && point.t_seconds >= start
    && point.t_seconds <= end
  ));
}

function average(points: MetaSoftPoint[], key: MetaSoftMetricKey): number | null {
  const values = points.map((point) => numeric(point.values[key])).filter((value): value is number => value !== null);
  if (!values.length) return null;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function isExcluded(tSeconds: number | null, exclusions: ManualRunningEconomyExclusion[]): boolean {
  return typeof tSeconds === "number"
    && exclusions.some((item) => tSeconds >= item.start_seconds && tSeconds <= item.end_seconds);
}

function numeric(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function numberOr(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function roundOrNull(value: number | null, digits: number): number | null {
  return value === null || !Number.isFinite(value) ? null : Number(value.toFixed(digits));
}

function round3(value: number): number {
  return Number(value.toFixed(3));
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}
