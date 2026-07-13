import { memo, useMemo, useState, type DragEvent } from "react";
import Plot from "react-plotly.js";
import { GripVertical, Plus, Trash2 } from "lucide-react";
import { speedSegmentsForAnalysis } from "../lib/chartUtils";
import type {
  LactateMeasurementDraft,
  LactateTestDraft,
  MetaSoftAnalysis,
} from "../types/metasoft";

export interface LactateReportSummary {
  active: boolean;
  includedCount: number;
  excludedCount: number;
  validCount: number;
  sl1: string;
  sl2: string;
}

export const LactateSection = memo(function LactateSection({
  analysis,
  draft,
  onChange,
}: {
  analysis: MetaSoftAnalysis;
  draft: LactateTestDraft;
  onChange: (draft: LactateTestDraft) => void;
}) {
  const [thresholdToPlace, setThresholdToPlace] = useState<"sl1" | "sl2" | null>(null);
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);

  const updateMeasurement = (index: number, patch: Partial<LactateMeasurementDraft>) => {
    const measurements = draft.measurements.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item);
    const thresholds = patch.enabled === false ? clearThresholdAt(draft.thresholds, index) : draft.thresholds;
    onChange({ ...draft, measurements, thresholds });
  };
  const addStage = () => {
    const measurements = [...draft.measurements];
    const insertAt = measurements.findIndex((item) => item.type === "recovery" || item.type === "rest_after");
    const stageCount = measurements.filter((item) => item.type === "stage").length;
    measurements.splice(insertAt < 0 ? measurements.length : insertAt, 0, {
      type: "stage",
      source: "manual",
      enabled: true,
      label: `Palier ${stageCount + 1}`,
      speed: null,
      lactate_mmol_l: null,
    });
    onChange({ ...draft, measurements });
  };
  const addRecovery = () => {
    const delays = draft.measurements
      .filter((item) => item.type === "recovery" || item.type === "rest_after")
      .map((item) => item.delay_minutes)
      .filter((value): value is number => typeof value === "number");
    onChange({
      ...draft,
      measurements: [...draft.measurements, {
        type: "recovery",
        source: "manual",
        enabled: true,
        speed: 0,
        lactate_mmol_l: null,
        delay_minutes: delays.length ? Math.max(...delays) + 5 : 3,
      }],
    });
  };
  const removeMeasurement = (index: number) => {
    const measurements = draft.measurements.filter((_item, itemIndex) => itemIndex !== index);
    onChange({
      ...draft,
      measurements,
      thresholds: remapThresholdsAfterRemoval(draft.thresholds, index),
    });
  };
  const moveStage = (from: number, to: number) => {
    if (from === to || draft.measurements[from]?.type !== "stage" || draft.measurements[to]?.type !== "stage") return;
    const moved = draft.measurements[from];
    const measurements = [...draft.measurements];
    measurements.splice(from, 1);
    measurements.splice(to, 0, moved);
    const remap = (value?: number | null) => {
      if (typeof value !== "number") return value;
      const original = draft.measurements[value];
      return original ? measurements.indexOf(original) : null;
    };
    onChange({
      ...draft,
      measurements,
      thresholds: { sl1: remap(draft.thresholds.sl1), sl2: remap(draft.thresholds.sl2) },
    });
  };
  const placeThreshold = (index: number) => {
    const item = draft.measurements[index];
    if (!thresholdToPlace || !isValidStage(item)) return;
    onChange({ ...draft, thresholds: { ...draft.thresholds, [thresholdToPlace]: index } });
    setThresholdToPlace(null);
  };

  const graphItems = useMemo(() => draft.measurements.flatMap((item, index) => (
    item.enabled !== false && numeric(item.lactate_mmol_l) !== null
      ? [{ item, index, label: `${index + 1}. ${measurementLabel(item, index)}` }]
      : []
  )), [draft.measurements]);
  const graphLabels = useMemo(() => Object.fromEntries(graphItems.map((entry) => [entry.index, entry.label])), [graphItems]);
  const validStages = graphItems.filter(({ item }) => item.type === "stage");

  return (
    <section id="metasoft-lactate" className="section-block">
      <div className="section-head section-head-with-control">
        <div>
          <h2>Lactate</h2>
          <p>Paliers detectes depuis le XML, mesures et seuils independants des seuils ventilatoires.</p>
        </div>
        <div className="view-mode-toggle" aria-label="Presence d'un test lactate">
          <button
            type="button"
            className={!draft.active ? "active" : ""}
            onClick={() => onChange({ ...draft, active: false })}
            aria-pressed={!draft.active}
          >
            Sans lactate
          </button>
          <button
            type="button"
            className={draft.active ? "active" : ""}
            onClick={() => onChange({ ...draft, active: true })}
            aria-pressed={draft.active}
          >
            Avec lactate
          </button>
        </div>
      </div>
      <section className="panel lactate-panel">
        {!draft.active ? (
          <div className="lactate-empty-state">
            <div>
              <strong>Aucun test lactate pour cette analyse</strong>
              <p>Activez le module pour pre-remplir les paliers du XML et saisir les prelevements.</p>
            </div>
            <button type="button" className="primary-button" onClick={() => onChange({ ...draft, active: true })}>
              Activer le module lactate
            </button>
          </div>
        ) : (
          <>
            <div className="panel-title-row lactate-toolbar">
              <div>
                <strong>Plan de prelevements</strong>
                <p className="panel-note">Glissez les paliers pour les reordonner. Les lignes ecartees restent sauvegardees mais sont masquees du graphe et du JSON officiel.</p>
              </div>
              <div className="ec-actions">
                <button type="button" className="secondary-button" onClick={addStage}>
                  <Plus size={15} /> Ajouter un palier
                </button>
                <button type="button" className="secondary-button" onClick={addRecovery}>
                  <Plus size={15} /> Ajouter une recuperation
                </button>
              </div>
            </div>
            <div className="lactate-workspace">
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr><th>Ordre</th><th>Statut</th><th>Repere</th><th>Vitesse</th><th>Delai</th><th>Lactate</th><th /></tr>
                  </thead>
                  <tbody>
                    {draft.measurements.map((item, index) => (
                      <tr
                        key={`${item.type}-${item.stage_index ?? "manual"}-${index}`}
                        className={item.enabled === false ? "muted-row" : ""}
                        onDragOver={(event) => {
                          if (item.type === "stage" && draggedIndex !== null) event.preventDefault();
                        }}
                        onDrop={(event) => {
                          event.preventDefault();
                          if (draggedIndex !== null) moveStage(draggedIndex, index);
                          setDraggedIndex(null);
                        }}
                      >
                        <td>
                          {item.type === "stage" ? (
                            <button
                              type="button"
                              className="drag-handle"
                              draggable
                              onDragStart={(event: DragEvent<HTMLButtonElement>) => {
                                event.dataTransfer.effectAllowed = "move";
                                setDraggedIndex(index);
                              }}
                              onDragEnd={() => setDraggedIndex(null)}
                              aria-label={`Deplacer ${measurementLabel(item, index)}`}
                              title="Glisser pour changer l'ordre"
                            >
                              <GripVertical size={15} />
                            </button>
                          ) : <span className="fixed-order-mark">—</span>}
                        </td>
                        <td>
                          <button
                            type="button"
                            className={item.enabled === false ? "table-icon-button status-button" : "table-icon-button status-button status-button-ok"}
                            onClick={() => updateMeasurement(index, { enabled: item.enabled === false })}
                          >
                            {item.enabled === false ? "Ecarte" : "Inclus"}
                          </button>
                        </td>
                        <td>
                          {item.type === "stage" ? (
                            <input
                              className="table-text-input"
                              value={item.label ?? measurementLabel(item, index)}
                              onChange={(event) => updateMeasurement(index, { label: event.target.value })}
                              aria-label={`Nom du palier ${index + 1}`}
                            />
                          ) : measurementLabel(item, index)}
                        </td>
                        <td>
                          {item.type === "stage" || item.type === "post_warmup" ? (
                            <input
                              className="table-number-input"
                              type="number"
                              min={0.1}
                              max={40}
                              step={0.1}
                              value={item.speed ?? ""}
                              onChange={(event) => updateMeasurement(index, { speed: numberInput(event.target.value) })}
                              aria-label={`Vitesse de ${measurementLabel(item, index)}`}
                            />
                          ) : "0 km/h"}
                        </td>
                        <td>
                          {item.type === "recovery" || item.type === "rest_after" ? (
                            <label className="inline-number-field">
                              +
                              <input
                                className="table-number-input compact-input"
                                type="number"
                                min={0}
                                max={120}
                                step={1}
                                value={item.delay_minutes ?? ""}
                                onChange={(event) => updateMeasurement(index, { delay_minutes: numberInput(event.target.value) })}
                                aria-label="Minutes apres l'effort"
                              />
                              min
                            </label>
                          ) : "—"}
                        </td>
                        <td>
                          <label className="inline-number-field">
                            <input
                              className="table-number-input"
                              type="number"
                              min={0}
                              max={30}
                              step={0.1}
                              value={item.lactate_mmol_l ?? ""}
                              onChange={(event) => updateMeasurement(index, { lactate_mmol_l: numberInput(event.target.value) })}
                              aria-label={`Lactate de ${measurementLabel(item, index)}`}
                            />
                            mmol/L
                          </label>
                        </td>
                        <td>
                          {(item.source === "manual" || item.type === "recovery" || item.type === "rest_after") && (
                            <button type="button" className="table-icon-button" onClick={() => removeMeasurement(index)} aria-label="Supprimer la ligne">
                              <Trash2 size={13} />
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="lactate-graph">
                <div className="lactate-threshold-actions">
                  {(["sl1", "sl2"] as const).map((name) => (
                    <button
                      key={name}
                      type="button"
                      className={thresholdToPlace === name ? "secondary-button active-action" : "secondary-button"}
                      disabled={!validStages.length}
                      onClick={() => setThresholdToPlace((current) => current === name ? null : name)}
                    >
                      Placer {name.toUpperCase()}
                      {typeof draft.thresholds[name] === "number" ? ` (${measurementLabel(draft.measurements[draft.thresholds[name]!], draft.thresholds[name]!)})` : ""}
                    </button>
                  ))}
                </div>
                {thresholdToPlace && <p className="interaction-hint">Cliquez sur un point de palier inclus pour placer {thresholdToPlace.toUpperCase()}.</p>}
                {graphItems.length ? (
                  <Plot
                    data={[
                      {
                        type: "scatter",
                        mode: "lines+markers",
                        name: "Lactate",
                        x: graphItems.map((entry) => entry.label),
                        y: graphItems.map((entry) => entry.item.lactate_mmol_l),
                        customdata: graphItems.map((entry) => entry.index),
                        line: { color: "#ff5f6d", width: 2 },
                        marker: { color: "#ff5f6d", size: 8 },
                      },
                      {
                        type: "scatter",
                        mode: "lines",
                        name: "Protocole",
                        x: graphItems.map((entry) => entry.label),
                        y: graphItems.map((entry) => entry.item.speed ?? 0),
                        yaxis: "y2",
                        line: { color: "#10d38f", width: 1.5, shape: "hv" },
                      },
                    ]}
                    layout={{
                      autosize: true,
                      paper_bgcolor: "rgba(0,0,0,0)",
                      plot_bgcolor: "rgba(0,0,0,0)",
                      margin: { l: 48, r: 48, t: 28, b: 82 },
                      font: { color: "rgba(226,232,240,0.78)", size: 10 },
                      hovermode: "closest",
                      xaxis: { gridcolor: "rgba(255,255,255,0.055)", tickangle: -24 },
                      yaxis: { title: "mmol/L", gridcolor: "rgba(255,255,255,0.055)" },
                      yaxis2: { title: "km/h", overlaying: "y", side: "right", gridcolor: "rgba(0,0,0,0)" },
                      shapes: lactateThresholdShapes(draft, graphLabels),
                    }}
                    config={{ responsive: true, displayModeBar: false, doubleClick: false }}
                    style={{ width: "100%", height: 360 }}
                    useResizeHandler
                    onClick={(event: Readonly<{ points?: Array<{ customdata?: unknown }> }>) => {
                      const index = numeric(event.points?.[0]?.customdata);
                      if (index !== null) placeThreshold(index);
                    }}
                  />
                ) : (
                  <div className="lactate-graph-empty">
                    Saisissez au moins une mesure incluse pour afficher la courbe.
                  </div>
                )}
              </div>
            </div>
          </>
        )}
      </section>
    </section>
  );
});

export function buildLactateDraft(
  profile: Record<string, unknown>,
  analysis: MetaSoftAnalysis,
  initialDraft?: LactateTestDraft | null,
): LactateTestDraft {
  if (initialDraft) return normaliseDraft(initialDraft, analysis);
  const stress = profile.stress_test_results && typeof profile.stress_test_results === "object"
    ? profile.stress_test_results as Record<string, unknown>
    : {};
  const raw = Array.isArray(stress.lactate_profile) ? stress.lactate_profile : [];
  const measurements = raw.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
    .map(profileMeasurement);
  const thresholds = stress.lactate_thresholds && typeof stress.lactate_thresholds === "object"
    ? stress.lactate_thresholds as Record<string, { measurement_index?: unknown }>
    : {};
  return normaliseDraft({
    active: measurements.length > 0,
    measurements: measurements.length ? measurements : detectedMeasurements(analysis),
    thresholds: {
      sl1: numeric(thresholds.sl1?.measurement_index),
      sl2: numeric(thresholds.sl2?.measurement_index),
    },
  }, analysis);
}

export function lactateReportSummary(draft: LactateTestDraft): LactateReportSummary {
  const included = draft.measurements.filter((item) => item.enabled !== false);
  const label = (value?: number | null) => typeof value === "number" && draft.measurements[value]
    ? measurementLabel(draft.measurements[value], value)
    : "Non place";
  return {
    active: draft.active,
    includedCount: included.length,
    excludedCount: draft.measurements.length - included.length,
    validCount: included.filter((item) => numeric(item.lactate_mmol_l) !== null).length,
    sl1: label(draft.thresholds.sl1),
    sl2: label(draft.thresholds.sl2),
  };
}

function normaliseDraft(draft: LactateTestDraft, analysis: MetaSoftAnalysis): LactateTestDraft {
  const measurements = draft.measurements.length ? draft.measurements.map((item) => ({
    ...item,
    enabled: item.enabled !== false,
    source: item.source ?? (item.type === "stage" ? "manual" : "detected"),
  })) : detectedMeasurements(analysis);
  if (measurements[0]?.type !== "rest_before") {
    measurements.unshift({ type: "rest_before", source: "detected", enabled: true, speed: 0, lactate_mmol_l: null });
  }
  return { ...draft, measurements };
}

function detectedMeasurements(analysis: MetaSoftAnalysis): LactateMeasurementDraft[] {
  const segments = speedSegmentsForAnalysis(analysis).filter((segment) => (
    typeof segment.start_seconds === "number"
    && typeof segment.end_seconds === "number"
    && segment.end_seconds - segment.start_seconds >= 30
    && segment.speed_kmh > 0
  ));
  const warmup = segments.filter((segment) => normalisePhase(segment.phase).includes("echauff"));
  const exercise = segments.filter((segment) => normalisePhase(segment.phase).includes("exercice"));
  const measurements: LactateMeasurementDraft[] = [
    { type: "rest_before", source: "detected", enabled: true, speed: 0, lactate_mmol_l: null },
  ];
  const lastWarmup = warmup[warmup.length - 1];
  if (lastWarmup) measurements.push({
    type: "post_warmup",
    source: "detected",
    enabled: true,
    speed: lastWarmup.speed_kmh,
    lactate_mmol_l: null,
    phase: lastWarmup.phase,
    time_seconds: lastWarmup.end_seconds,
  });
  exercise.forEach((segment, index) => measurements.push({
    type: "stage",
    source: "detected",
    enabled: true,
    label: `Palier ${index + 1}`,
    stage_index: index + 1,
    speed: segment.speed_kmh,
    lactate_mmol_l: null,
    phase: segment.phase,
    time_seconds: segment.end_seconds,
  }));
  measurements.push(
    { type: "recovery", source: "detected", enabled: false, speed: 0, lactate_mmol_l: null, delay_minutes: 3 },
    { type: "recovery", source: "detected", enabled: false, speed: 0, lactate_mmol_l: null, delay_minutes: 15 },
  );
  return measurements;
}

function profileMeasurement(item: Record<string, unknown>): LactateMeasurementDraft {
  const allowed = new Set(["rest_before", "post_warmup", "stage", "recovery", "rest_after"]);
  const type = allowed.has(String(item.type)) ? item.type as LactateMeasurementDraft["type"] : "stage";
  return {
    type,
    speed: numeric(item.speed),
    lactate_mmol_l: numeric(item.lactate_mmol_l),
    enabled: item.enabled !== false,
    source: item.source === "detected" ? "detected" : "manual",
    label: typeof item.label === "string" ? item.label : null,
    stage_index: numeric(item.stage_index),
    phase: typeof item.phase === "string" ? item.phase : null,
    time_seconds: numeric(item.time_seconds),
    delay_minutes: numeric(item.delay_minutes),
  };
}

function measurementLabel(item: LactateMeasurementDraft | undefined, index: number): string {
  if (!item) return "Non place";
  if (item.type === "rest_before") return "Repos initial";
  if (item.type === "post_warmup") return "Fin echauffement";
  if (item.type === "recovery" || item.type === "rest_after") {
    return typeof item.delay_minutes === "number" ? `Recuperation +${item.delay_minutes} min` : "Recuperation";
  }
  return item.label?.trim() || (item.speed !== null ? `${item.speed} km/h` : `Palier ${index + 1}`);
}

function isValidStage(item: LactateMeasurementDraft | undefined): boolean {
  return Boolean(item && item.type === "stage" && item.enabled !== false && numeric(item.lactate_mmol_l) !== null);
}

function clearThresholdAt(thresholds: LactateTestDraft["thresholds"], index: number) {
  return {
    sl1: thresholds.sl1 === index ? null : thresholds.sl1,
    sl2: thresholds.sl2 === index ? null : thresholds.sl2,
  };
}

function remapThresholdsAfterRemoval(thresholds: LactateTestDraft["thresholds"], index: number) {
  const remap = (value?: number | null) => value === index ? null : typeof value === "number" && value > index ? value - 1 : value;
  return { sl1: remap(thresholds.sl1), sl2: remap(thresholds.sl2) };
}

function lactateThresholdShapes(draft: LactateTestDraft, labels: Record<number, string>) {
  return (["sl1", "sl2"] as const).flatMap((name) => {
    const index = draft.thresholds[name];
    return typeof index === "number" && labels[index] ? [{
      type: "line",
      x0: labels[index],
      x1: labels[index],
      y0: 0,
      y1: 1,
      yref: "paper",
      line: { color: name === "sl1" ? "#16e0c2" : "#ff8a00", width: 2, dash: "dash" },
    }] : [];
  });
}

function numberInput(value: string): number | null {
  if (!value.trim()) return null;
  return numeric(value);
}

function numeric(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() && Number.isFinite(Number(value))) return Number(value);
  return null;
}

function normalisePhase(value?: string | null): string {
  return (value ?? "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}
