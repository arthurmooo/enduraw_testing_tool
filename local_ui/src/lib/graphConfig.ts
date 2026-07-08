import type { MetaSoftGraphId, MetaSoftMetricKey, MetaSoftMarkerName } from "../types/metasoft";

export interface MetaSoftSeriesConfig {
  key: MetaSoftMetricKey | "value_j_kg_m";
  label: string;
  unit?: string;
  color: string;
  axis?: "y" | "y2";
  smoothable: boolean;
}

export interface MetaSoftGraphConfig {
  id: MetaSoftGraphId;
  title: string;
  source: "points" | "running_economy";
  xAxis: { key: "t_seconds" | "stage_index"; label: string; unit?: string };
  series: MetaSoftSeriesConfig[];
}

function series(
  key: MetaSoftSeriesConfig["key"],
  label: string,
  unit: string,
  color: string,
  axis: "y" | "y2" = "y",
  smoothable = true,
): MetaSoftSeriesConfig {
  return { key, label, unit, color, axis, smoothable: smoothable && key !== "speed_kmh" };
}

export const GRAPH_CONFIGS: MetaSoftGraphConfig[] = [
  {
    id: "fc_vo2",
    title: "FC + V'O2",
    source: "points",
    xAxis: { key: "t_seconds", label: "Temps", unit: "s" },
    series: [
      series("fc_bpm", "FC (bpm)", "bpm", "#ff5b22"),
      series("vo2_l_min", "V'O2 (L/min)", "L/min", "#10a8ff", "y2"),
    ],
  },
  {
    id: "vo2kg_speed",
    title: "V'O2/kg + vitesse",
    source: "points",
    xAxis: { key: "t_seconds", label: "Temps", unit: "s" },
    series: [
      series("vo2_ml_kg_min", "V'O2/kg", "ml/min/kg", "#10a8ff"),
      series("speed_kmh", "Vitesse (km/h)", "km/h", "#10d38f", "y2", false),
    ],
  },
  {
    id: "ve_bf",
    title: "V'E + BF",
    source: "points",
    xAxis: { key: "t_seconds", label: "Temps", unit: "s" },
    series: [
      series("ve_l_min", "V'E (L/min)", "L/min", "#10a8ff"),
      series("bf_per_min", "BF (br/min)", "/min", "#ff5b22", "y2"),
    ],
  },
  {
    id: "rer",
    title: "RER",
    source: "points",
    xAxis: { key: "t_seconds", label: "Temps", unit: "s" },
    series: [series("rer", "RER", "sans unite", "#16e0c2")],
  },
  {
    id: "ve_ratios",
    title: "V'E/V'O2 + V'E/V'CO2",
    source: "points",
    xAxis: { key: "t_seconds", label: "Temps", unit: "s" },
    series: [
      series("ve_vo2", "V'E/V'O2", "sans unite", "#10a8ff"),
      series("ve_vco2", "V'E/V'CO2", "sans unite", "#ff6b00"),
    ],
  },
  {
    id: "pet",
    title: "PetO2 + PetCO2",
    source: "points",
    xAxis: { key: "t_seconds", label: "Temps", unit: "s" },
    series: [
      series("peto2_mmhg", "PetO2", "mmHg", "#10a8ff"),
      series("petco2_mmhg", "PetCO2", "mmHg", "#ff6b00"),
    ],
  },
  {
    id: "de",
    title: "DE / DECHO / DEFAT / DEPRO",
    source: "points",
    xAxis: { key: "t_seconds", label: "Temps", unit: "s" },
    series: [
      series("de_kcal_h", "DE", "kcal/h", "#0f8fff"),
      series("decho_kcal_h", "DECHO", "kcal/h", "#ff5b22"),
      series("defat_kcal_h", "DEFAT", "kcal/h", "#16d18d"),
      series("depro_kcal_h", "DEPRO", "kcal/h", "#a855f7"),
    ],
  },
  {
    id: "running_economy",
    title: "Economie de course",
    source: "running_economy",
    xAxis: { key: "stage_index", label: "Palier" },
    series: [series("value_j_kg_m", "EC (J/kg/m)", "J/kg/m", "#16e0c2", "y", false)],
  },
  {
    id: "thresholds",
    title: "Synthese seuils",
    source: "points",
    xAxis: { key: "t_seconds", label: "Temps", unit: "s" },
    series: [
      series("fc_bpm", "FC (bpm)", "bpm", "#ff5b22"),
      series("vo2_l_min", "V'O2 (L/min)", "L/min", "#10a8ff", "y2"),
    ],
  },
];

export const MARKER_COLORS: Record<MetaSoftMarkerName, string> = {
  SV1: "#00d48a",
  SV2: "#ff8a00",
  VO2_max: "#ff405d",
  VMA: "#18b8ff",
};
