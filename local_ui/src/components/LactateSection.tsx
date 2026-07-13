import { memo, useEffect, useMemo, useState } from "react";
import Plot from "react-plotly.js";
import { Plus, Trash2 } from "lucide-react";
import type { LactateMeasurementDraft, LactateTestDraft } from "../types/metasoft";

export const LactateSection = memo(function LactateSection({
  profile,
  initialDraft,
  onChange,
}: {
  profile: Record<string, unknown>;
  initialDraft?: LactateTestDraft | null;
  onChange: (draft: LactateTestDraft) => void;
}) {
  const [draft, setDraft] = useState<LactateTestDraft>(() => initialDraft ?? lactateFromProfile(profile));
  const [thresholdToPlace, setThresholdToPlace] = useState<"sl1" | "sl2" | null>(null);

  useEffect(() => {
    setDraft(initialDraft ?? lactateFromProfile(profile));
    setThresholdToPlace(null);
  }, [initialDraft, profile]);

  const update = (next: LactateTestDraft) => {
    setDraft(next);
    onChange(next);
  };
  const labels = useMemo(() => draft.measurements.map((item, index) => (
    item.type === "rest_before" ? "Repos avant"
      : item.type === "rest_after" ? "Repos apres"
        : `${item.speed ?? "-"} km/h (${index})`
  )), [draft.measurements]);

  const updateMeasurement = (index: number, patch: Partial<LactateMeasurementDraft>) => {
    update({
      ...draft,
      measurements: draft.measurements.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item),
    });
  };
  const addStage = () => {
    const measurements = [...draft.measurements];
    measurements.splice(Math.max(1, measurements.length - 1), 0, {
      type: "stage",
      speed: null,
      lactate_mmol_l: null,
    });
    update({ ...draft, measurements });
  };
  const removeStage = (index: number) => {
    const measurements = draft.measurements.filter((_item, itemIndex) => itemIndex !== index);
    const remap = (value?: number | null) => value === index ? null : typeof value === "number" && value > index ? value - 1 : value;
    update({
      ...draft,
      measurements,
      thresholds: { sl1: remap(draft.thresholds.sl1), sl2: remap(draft.thresholds.sl2) },
    });
  };
  const placeThreshold = (index: number) => {
    if (!thresholdToPlace || draft.measurements[index]?.type !== "stage") return;
    update({ ...draft, thresholds: { ...draft.thresholds, [thresholdToPlace]: index } });
    setThresholdToPlace(null);
  };

  return (
    <section id="metasoft-lactate" className="section-block">
      <div className="section-head">
        <h2>Lactate</h2>
        <p>Protocole et seuils lactiques independants des seuils ventilatoires.</p>
      </div>
      <section className="panel lactate-panel">
        <div className="panel-title-row">
          <label className="lactate-enable">
            <input
              type="checkbox"
              checked={draft.active}
              onChange={(event) => update({ ...draft, active: event.target.checked })}
            />
            Test avec lactate
          </label>
          {draft.active && (
            <button type="button" className="secondary-button" onClick={addStage}>
              <Plus size={15} /> Ajouter une vitesse
            </button>
          )}
        </div>
        {draft.active && (
          <div className="lactate-workspace">
            <div className="table-wrap">
              <table>
                <thead><tr><th>Mesure</th><th>Vitesse</th><th>Lactate (mmol/L)</th><th /></tr></thead>
                <tbody>
                  {draft.measurements.map((item, index) => (
                    <tr key={`${item.type}-${index}`}>
                      <td>{item.type === "rest_before" ? "Repos avant" : item.type === "rest_after" ? "Repos apres" : `Palier ${index}`}</td>
                      <td>
                        {item.type === "stage" ? (
                          <input
                            className="table-number-input"
                            type="number"
                            min={0.1}
                            max={40}
                            step={0.1}
                            value={item.speed ?? ""}
                            onChange={(event) => updateMeasurement(index, { speed: numberInput(event.target.value) })}
                          />
                        ) : "0 km/h"}
                      </td>
                      <td>
                        <input
                          className="table-number-input"
                          type="number"
                          min={0}
                          max={30}
                          step={0.1}
                          value={item.lactate_mmol_l ?? ""}
                          onChange={(event) => updateMeasurement(index, { lactate_mmol_l: numberInput(event.target.value) })}
                        />
                      </td>
                      <td>
                        {item.type === "stage" && (
                          <button type="button" className="table-icon-button" onClick={() => removeStage(index)}>
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
                    onClick={() => setThresholdToPlace((current) => current === name ? null : name)}
                  >
                    Placer {name.toUpperCase()}
                    {typeof draft.thresholds[name] === "number" ? ` (${labels[draft.thresholds[name]!]})` : ""}
                  </button>
                ))}
              </div>
              {thresholdToPlace && <p className="interaction-hint">Cliquez sur un point de palier pour placer {thresholdToPlace.toUpperCase()}.</p>}
              <Plot
                data={[
                  {
                    type: "scatter",
                    mode: "lines+markers",
                    name: "Lactate",
                    x: labels,
                    y: draft.measurements.map((item) => item.lactate_mmol_l),
                    line: { color: "#ff5f6d", width: 2 },
                    marker: { color: "#ff5f6d", size: 8 },
                  },
                  {
                    type: "scatter",
                    mode: "lines",
                    name: "Protocole",
                    x: labels,
                    y: draft.measurements.map((item) => item.speed ?? 0),
                    yaxis: "y2",
                    line: { color: "#10d38f", width: 1.5, shape: "hv" },
                  },
                ]}
                layout={{
                  autosize: true,
                  paper_bgcolor: "rgba(0,0,0,0)",
                  plot_bgcolor: "rgba(0,0,0,0)",
                  margin: { l: 48, r: 48, t: 28, b: 70 },
                  font: { color: "rgba(226,232,240,0.78)", size: 10 },
                  hovermode: "closest",
                  xaxis: { gridcolor: "rgba(255,255,255,0.055)" },
                  yaxis: { title: "mmol/L", gridcolor: "rgba(255,255,255,0.055)" },
                  yaxis2: { title: "km/h", overlaying: "y", side: "right", gridcolor: "rgba(0,0,0,0)" },
                  shapes: lactateThresholdShapes(draft, labels),
                }}
                config={{ responsive: true, displayModeBar: false }}
                style={{ width: "100%", height: 330 }}
                useResizeHandler
                onClick={(event: Readonly<{ points?: Array<{ pointIndex?: number }> }>) => (
                  placeThreshold(event.points?.[0]?.pointIndex ?? -1)
                )}
              />
            </div>
          </div>
        )}
      </section>
    </section>
  );
});

function lactateFromProfile(profile: Record<string, unknown>): LactateTestDraft {
  const stress = profile.stress_test_results && typeof profile.stress_test_results === "object"
    ? profile.stress_test_results as Record<string, unknown>
    : {};
  const raw = Array.isArray(stress.lactate_profile) ? stress.lactate_profile : [];
  const profileMeasurements = raw.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
    .map((item): LactateMeasurementDraft => {
      const type = item.type === "rest_before" || item.type === "rest_after" ? item.type : "stage";
      return { type, speed: numeric(item.speed), lactate_mmol_l: numeric(item.lactate_mmol_l) };
    });
  const measurements: LactateMeasurementDraft[] = profileMeasurements.length
    ? ensureRestMeasurements(profileMeasurements)
    : defaultMeasurements();
  const thresholds = stress.lactate_thresholds && typeof stress.lactate_thresholds === "object"
    ? stress.lactate_thresholds as Record<string, { measurement_index?: unknown }>
    : {};
  return {
    active: profileMeasurements.length > 0,
    measurements,
    thresholds: {
      sl1: numeric(thresholds.sl1?.measurement_index),
      sl2: numeric(thresholds.sl2?.measurement_index),
    },
  };
}

function defaultMeasurements(): LactateMeasurementDraft[] {
  return [
    { type: "rest_before", speed: 0, lactate_mmol_l: null },
    { type: "stage", speed: null, lactate_mmol_l: null },
    { type: "rest_after", speed: 0, lactate_mmol_l: null },
  ];
}

function ensureRestMeasurements(items: LactateMeasurementDraft[]): LactateMeasurementDraft[] {
  const result = [...items];
  if (result[0]?.type !== "rest_before") result.unshift({ type: "rest_before", speed: 0, lactate_mmol_l: null });
  if (result[result.length - 1]?.type !== "rest_after") result.push({ type: "rest_after", speed: 0, lactate_mmol_l: null });
  return result;
}

function lactateThresholdShapes(draft: LactateTestDraft, labels: string[]) {
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
