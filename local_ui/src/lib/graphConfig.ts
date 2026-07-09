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
  kind: "time" | "scatter" | "bar";
  source: "points" | "running_economy";
  xAxis: { key: "t_seconds" | "stage_index" | MetaSoftMetricKey; label: string; unit?: string };
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
    id: "ve_vo2_peto2_time",
    title: "V'E, V'E/V'O2, PETO2",
    kind: "time",
    source: "points",
    xAxis: { key: "t_seconds", label: "Temps", unit: "s" },
    series: [
      series("ve_l_min", "V'E", "L/min", "#10a8ff"),
      series("ve_vo2", "V'E/V'O2", "sans unite", "#16e0c2", "y2"),
      series("peto2_mmhg", "PETO2", "mmHg", "#ff8a00", "y2"),
    ],
  },
  {
    id: "ve_vco2_petco2_time",
    title: "V'E, V'E/V'CO2, PETCO2",
    kind: "time",
    source: "points",
    xAxis: { key: "t_seconds", label: "Temps", unit: "s" },
    series: [
      series("ve_l_min", "V'E", "L/min", "#10a8ff"),
      series("ve_vco2", "V'E/V'CO2", "sans unite", "#16e0c2", "y2"),
      series("petco2_mmhg", "PETCO2", "mmHg", "#ff6b00", "y2"),
    ],
  },
  {
    id: "ve_time",
    title: "V'E",
    kind: "time",
    source: "points",
    xAxis: { key: "t_seconds", label: "Temps", unit: "s" },
    series: [series("ve_l_min", "V'E", "L/min", "#10a8ff")],
  },
  {
    id: "hr_vo2_fc_time",
    title: "HR, V'O2/HR",
    kind: "time",
    source: "points",
    xAxis: { key: "t_seconds", label: "Temps", unit: "s" },
    series: [
      series("fc_bpm", "HR", "bpm", "#ff5b22"),
      series("vo2_fc_ml", "V'O2/HR", "ml", "#10a8ff", "y2"),
    ],
  },
  {
    id: "vo2_vco2_time",
    title: "V'O2, V'CO2",
    kind: "time",
    source: "points",
    xAxis: { key: "t_seconds", label: "Temps", unit: "s" },
    series: [
      series("vo2_l_min", "V'O2", "L/min", "#10a8ff"),
      series("vco2_l_min", "V'CO2", "L/min", "#16d18d"),
    ],
  },
  {
    id: "de_time",
    title: "DE / CHOx / FATOx / PROx",
    kind: "time",
    source: "points",
    xAxis: { key: "t_seconds", label: "Temps", unit: "s" },
    series: [
      series("de_kcal_h", "DE", "kcal/h", "#f8fafc"),
      series("decho_kcal_h", "CHOx", "kcal/h", "#ff8a00"),
      series("defat_kcal_h", "FATOx", "kcal/h", "#16d18d"),
      series("depro_kcal_h", "PROx", "kcal/h", "#a855f7"),
    ],
  },
  {
    id: "ve_vco2_scatter",
    title: "V'E(V'CO2)",
    kind: "scatter",
    source: "points",
    xAxis: { key: "vco2_l_min", label: "V'CO2", unit: "L/min" },
    series: [series("ve_l_min", "V'E", "L/min", "#10a8ff", "y", false)],
  },
  {
    id: "vco2_hr_scatter",
    title: "V'CO2, HR",
    kind: "scatter",
    source: "points",
    xAxis: { key: "vo2_l_min", label: "V'O2", unit: "L/min" },
    series: [
      series("vco2_l_min", "V'CO2", "L/min", "#16d18d", "y", false),
      series("fc_bpm", "HR", "bpm", "#ff5b22", "y2", false),
    ],
  },
  {
    id: "ve_ratios_time",
    title: "V'E/V'O2, V'E/V'CO2",
    kind: "time",
    source: "points",
    xAxis: { key: "t_seconds", label: "Temps", unit: "s" },
    series: [
      series("ve_vo2", "V'E/V'O2", "sans unite", "#10a8ff"),
      series("ve_vco2", "V'E/V'CO2", "sans unite", "#ff6b00"),
    ],
  },
  {
    id: "vt_ve_scatter",
    title: "VT(V'E)",
    kind: "scatter",
    source: "points",
    xAxis: { key: "ve_l_min", label: "V'E", unit: "L/min" },
    series: [series("vt_l", "VT", "L", "#a855f7", "y", false)],
  },
  {
    id: "rer_time",
    title: "RER",
    kind: "time",
    source: "points",
    xAxis: { key: "t_seconds", label: "Temps", unit: "s" },
    series: [series("rer", "RER", "sans unite", "#16e0c2")],
  },
  {
    id: "pet_time",
    title: "PETO2, PETCO2",
    kind: "time",
    source: "points",
    xAxis: { key: "t_seconds", label: "Temps", unit: "s" },
    series: [
      series("peto2_mmhg", "PETO2", "mmHg", "#10a8ff"),
      series("petco2_mmhg", "PETCO2", "mmHg", "#ff6b00"),
    ],
  },
  {
    id: "running_economy",
    title: "Economie de course",
    kind: "bar",
    source: "running_economy",
    xAxis: { key: "stage_index", label: "Palier" },
    series: [series("value_j_kg_m", "EC (J/kg/m)", "J/kg/m", "#16e0c2", "y", false)],
  },
];

export const MARKER_COLORS: Record<MetaSoftMarkerName, string> = {
  SV1: "#00d48a",
  SV2: "#ff8a00",
  VO2_max: "#ff405d",
  VMA: "#18b8ff",
};
