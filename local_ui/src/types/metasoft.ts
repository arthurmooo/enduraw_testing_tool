export type MetaSoftMetricKey =
  | "vo2_l_min"
  | "vo2_ml_kg_min"
  | "vo2_fc_ml"
  | "vco2_l_min"
  | "fc_bpm"
  | "ve_l_min"
  | "vt_l"
  | "bf_per_min"
  | "rer"
  | "grade_percent"
  | "speed_kmh"
  | "peto2_mmhg"
  | "petco2_mmhg"
  | "de_kcal_h"
  | "decho_kcal_h"
  | "defat_kcal_h"
  | "depro_kcal_h"
  | "ve_vo2"
  | "ve_vco2";

export type MetaSoftGraphId =
  | "ve_vo2_peto2_time"
  | "ve_vco2_petco2_time"
  | "de_time"
  | "ve_time"
  | "hr_vo2_fc_time"
  | "vo2_vco2_time"
  | "ve_vco2_scatter"
  | "vco2_hr_scatter"
  | "ve_ratios_time"
  | "vt_ve_scatter"
  | "rer_time"
  | "pet_time"
  | "running_economy";

export type MetaSoftMarkerName = "SV1" | "SV2" | "VO2_max" | "VMA" | "Cross-over";
export type MarkerMode = "point" | "range" | "previous";
export type ChartProcessingMode = "raw" | "blocks" | "smooth";

export interface MetaSoftMetricSpec {
  key: MetaSoftMetricKey;
  source_label: string;
  unit?: string | null;
  source: string;
  transform: string;
}

export interface MetaSoftPoint {
  index: number;
  t: string;
  t_seconds: number | null;
  phase?: string | null;
  marker?: string | null;
  values: Partial<Record<MetaSoftMetricKey, number | string | null>>;
  value_sources?: Partial<Record<MetaSoftMetricKey, string>>;
  raw?: Record<string, number | string | null>;
}

export interface MetaSoftPhaseSegment {
  phase: string;
  start_seconds: number | null;
  end_seconds: number | null;
  point_count: number;
}

export interface MetaSoftWarmupStage {
  stage_index: number;
  speed_kmh: number;
  start_seconds: number | null;
  end_seconds: number | null;
  point_count: number;
  native_de?: Record<string, { value: number; unit: string; source: string }>;
  source?: "detected" | "manual";
  phase?: string | null;
}

export interface MetaSoftRunningEconomy {
  stage_index: number;
  speed_kmh: number;
  speed_m_min?: number;
  value_j_kg_m: number | null;
  unit?: string;
  point_count: number;
  vco2_source?: string | null;
  vo2_ml_min?: number;
  vco2_ml_min?: number;
  mass_kg?: number;
  warning?: MetaSoftWarning;
}

export interface ManualRunningEconomyExclusion {
  start_seconds: number;
  end_seconds: number;
}

export interface ManualRunningEconomyRow {
  stage_index: number;
  speed_kmh: number;
  start_seconds: number;
  end_seconds: number;
  exclusions: ManualRunningEconomyExclusion[];
  point_count: number;
  vo2_l_min: number | null;
  vco2_l_min: number | null;
  ec_j_kg_m: number | null;
  percent_vo2max: number | null;
  de_kcal_h?: number | null;
  decho_kcal_h?: number | null;
  defat_kcal_h?: number | null;
  depro_kcal_h?: number | null;
  sources?: Record<string, string>;
  warning?: string | null;
  warnings?: MetaSoftWarning[];
}

export interface ManualRunningEconomyPayload {
  source: string;
  match_id: string;
  rows: ManualRunningEconomyRow[];
  stage_selections?: Array<{ stage_index: number; enabled: boolean }>;
  rest_baseline?: ManualRunningEconomyRestBaseline | null;
  warnings?: MetaSoftWarning[];
}

export interface ManualRunningEconomyRestSelection {
  start_seconds: number;
  end_seconds: number;
  exclusions: ManualRunningEconomyExclusion[];
}

export interface ManualRunningEconomyRestBaseline extends ManualRunningEconomyRestSelection {
  vo2_ml_min: number;
  vco2_ml_min: number;
  point_count: number;
  source: string;
}

export interface LactateMeasurementDraft {
  type: "rest_before" | "post_warmup" | "stage" | "recovery" | "rest_after";
  speed: number | null;
  lactate_mmol_l: number | null;
  enabled?: boolean;
  inclusion_touched?: boolean;
  source?: "detected" | "manual";
  label?: string | null;
  stage_index?: number | null;
  phase?: string | null;
  time_seconds?: number | null;
  delay_minutes?: number | null;
}

export interface LactateThresholdDraft {
  mode: "point" | "range";
  speed_kmh: number;
  speed_start_kmh?: number | null;
  speed_end_kmh?: number | null;
  time_seconds?: number | null;
  window_start_seconds?: number | null;
  window_end_seconds?: number | null;
}

export interface LactateTestDraft {
  active: boolean;
  measurements: LactateMeasurementDraft[];
  thresholds: { sl1?: LactateThresholdDraft | null; sl2?: LactateThresholdDraft | null };
}

export interface MetaSoftWarning {
  code?: string;
  message: string;
  field?: string;
  blocking?: boolean;
  stage_index?: number;
  [key: string]: unknown;
}

export interface MetaSoftAnalysis {
  file: { filename: string; size_bytes?: number };
  athlete: {
    first_name?: string;
    last_name?: string;
    athlete_name?: string;
    weight_kg?: number;
  };
  test: { date?: string; time?: string; datetime?: string; type?: string };
  metrics: Partial<Record<MetaSoftMetricKey, MetaSoftMetricSpec>>;
  points: MetaSoftPoint[];
  phases: MetaSoftPhaseSegment[];
  warmup_stages: MetaSoftWarmupStage[];
  computed: {
    rest_baseline?: {
      vo2_ml_min: number;
      vco2_ml_min: number;
      vco2_source?: string | null;
      point_count: number;
      source: string;
    } | null;
    running_economy?: MetaSoftRunningEconomy[];
    ventilatory_consistency?: MetaSoftWarning[];
  };
  warnings: MetaSoftWarning[];
}

export interface MetaSoftMarker {
  name: MetaSoftMarkerName;
  action?: "upsert";
  status?: "ok";
  mode: MarkerMode;
  t_seconds: number | null;
  window_start_seconds: number | null;
  window_end_seconds: number | null;
  window_end_exclusive?: boolean;
  phase_filter?: string | null;
  phase?: string | null;
  point_count: number;
  values: {
    fc_bpm?: number | null;
    vo2_l_min?: number | null;
    vo2_ml_kg_min?: number | null;
    speed_kmh?: number | null;
    rer?: number | null;
    de_kcal_h?: number | null;
    decho_kcal_h?: number | null;
    defat_kcal_h?: number | null;
    fat_percent?: number | null;
    cho_percent?: number | null;
    vma?: number | null;
  };
  warnings?: MetaSoftWarning[];
}

export interface DraftMarker extends MetaSoftMarker {
  mode: MarkerMode;
}

export type DraftMarkers = Record<MetaSoftMarkerName, DraftMarker>;
export type ConfirmedMarkers = Partial<Record<MetaSoftMarkerName, MetaSoftMarker>>;

export interface DeletedMarkerResult {
  name: MetaSoftMarkerName;
  action: "delete";
  status: "deleted";
  mode: "point";
  t_seconds: null;
  window_start_seconds: null;
  window_end_seconds: null;
  point_count: 0;
  values: MetaSoftMarker["values"];
}

export type MarkerOperationResult = MetaSoftMarker | DeletedMarkerResult;
export type MarkerOperationResults = Partial<Record<MetaSoftMarkerName, MarkerOperationResult>>;

export interface MarkerSelectionPayload {
  name: MetaSoftMarkerName;
  action: "upsert" | "delete";
  mode?: MarkerMode;
  t_seconds?: number | null;
  window_start_seconds?: number | null;
  window_end_seconds?: number | null;
  window_end_exclusive?: boolean;
  phase_filter?: string | null;
}

export interface MetaSoftDraftPayload {
  marker_selections?: MarkerSelectionPayload[];
  manual_running_economy_selections?: Array<{
    stage_index: number;
    source?: "detected" | "manual";
    start_seconds: number;
    end_seconds: number;
    exclusions: ManualRunningEconomyExclusion[];
  }>;
  manual_running_economy_stage_selections?: Array<{ stage_index: number; enabled: boolean }>;
  manual_running_economy_rest_selection?: ManualRunningEconomyRestSelection;
  lactate_test?: LactateTestDraft;
}

export interface LocalAnalysisPayload {
  ok: true;
  match: {
    match_id: string;
    profile_name: string;
    xml_filename: string;
  };
  profile: Record<string, unknown>;
  analysis: MetaSoftAnalysis;
  manual_running_economy?: ManualRunningEconomyPayload | null;
  metasoft_draft?: MetaSoftDraftPayload | null;
  lactate_profile_provenance_valid: boolean;
  confirmed_markers?: ConfirmedMarkers;
  deleted_markers?: MetaSoftMarkerName[];
  warnings: MetaSoftWarning[];
  source_of_truth: Record<string, string>;
}

export interface ProfileConflict {
  path: string;
  current: unknown;
  incoming: unknown;
}

export interface OfficializeResponse {
  ok: true;
  markers: MarkerOperationResults;
  source?: string;
  warnings: MetaSoftWarning[];
}

export interface ReportPreviewResponse {
  ok: true;
  status: "ready" | "conflict";
  patch: Record<string, unknown>;
  conflicts: ProfileConflict[];
  confirmed_markers: MarkerOperationResults;
  warnings: MetaSoftWarning[];
}

export interface ReportResponse {
  ok: true;
  profile_name: string;
  updated_paths: string[];
  confirmed_markers: MarkerOperationResults;
  manual_running_economy?: ManualRunningEconomyPayload | null;
  warnings: MetaSoftWarning[];
}
