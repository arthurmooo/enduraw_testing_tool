import {
  forwardRef,
  memo,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useState,
  type CSSProperties,
} from "react";
import Plot from "react-plotly.js";
import { Scissors, Trash2 } from "lucide-react";
import { formatNumber, secondsToClock } from "../lib/markerUtils";
import {
  buildManualEconomyPreviewRow,
  clampDraftToStage,
  correctedSeries,
  initialEconomyDraft,
  manualEconomySelection,
  manualEconomyStageSelection,
  normalizeExclusions,
  type ManualEconomyDraft,
  type ManualRunningEconomySelection,
  type ManualRunningEconomyStageSelection,
} from "../lib/runningEconomyManual";
import type {
  ManualRunningEconomyPayload,
  ManualRunningEconomyRow,
  MetaSoftAnalysis,
  MetaSoftPoint,
  MetaSoftWarmupStage,
} from "../types/metasoft";

interface Props {
  analysis: MetaSoftAnalysis;
  profileVo2maxMlKgMin: number | null;
  initialManualEconomy?: ManualRunningEconomyPayload | null;
}

export interface RunningEconomyManualHandle {
  reportPayload: () => {
    manual_running_economy_selections: ManualRunningEconomySelection[];
    manual_running_economy_stage_selections: ManualRunningEconomyStageSelection[];
  } | null;
}

export const RunningEconomyManualSection = memo(forwardRef<RunningEconomyManualHandle, Props>(function RunningEconomyManualSection({
  analysis,
  profileVo2maxMlKgMin,
  initialManualEconomy,
}: Props, ref) {
  const stableStages = useMemo(() => analysis.warmup_stages.filter(hasStageBounds), [analysis.warmup_stages]);
  const [selectedStageIndex, setSelectedStageIndex] = useState(stableStages[0]?.stage_index ?? 0);
  const [drafts, setDrafts] = useState<Record<number, ManualEconomyDraft>>({});
  const [activeExclusionIndex, setActiveExclusionIndex] = useState<number | null>(null);
  const [excludeMode, setExcludeMode] = useState(false);
  const [xRange, setXRange] = useState<[number, number] | null>(null);
  const [saveStatus, setSaveStatus] = useState<string | null>(null);
  const [savedManualEconomy, setSavedManualEconomy] = useState<ManualRunningEconomyPayload | null>(initialManualEconomy ?? null);
  const [dirty, setDirty] = useState(false);
  const selectedStage = useMemo(
    () => stableStages.find((stage) => stage.stage_index === selectedStageIndex) ?? stableStages[0] ?? null,
    [selectedStageIndex, stableStages],
  );

  useEffect(() => {
    setSavedManualEconomy(initialManualEconomy ?? null);
    setDirty(false);
    const savedRows = new Map((initialManualEconomy?.rows ?? []).map((row) => [row.stage_index, row]));
    const savedStageSelections = new Map(
      (initialManualEconomy?.stage_selections ?? []).map((item) => [item.stage_index, item.enabled]),
    );
    const hasSavedManualEconomy = Boolean(initialManualEconomy);
    const nextDrafts = Object.fromEntries(stableStages.map((stage) => {
      const saved = savedRows.get(stage.stage_index);
      const draft = saved ? draftFromSavedRow(saved) : initialEconomyDraft(stage);
      draft.enabled = savedStageSelections.get(stage.stage_index) ?? (saved ? true : !hasSavedManualEconomy);
      return [stage.stage_index, clampDraftToStage(draft, stage)];
    }));
    setDrafts(nextDrafts);
    setSelectedStageIndex(stableStages[0]?.stage_index ?? 0);
    setXRange(null);
    setActiveExclusionIndex(null);
  }, [analysis.file.filename]); // eslint-disable-line react-hooks/exhaustive-deps

  const previewRows = useMemo(
    () => stableStages.map((stage) => buildManualEconomyPreviewRow(
      analysis,
      stage,
      drafts[stage.stage_index] ?? initialEconomyDraft(stage),
      profileVo2maxMlKgMin,
    )),
    [analysis, drafts, profileVo2maxMlKgMin, stableStages],
  );
  const savedRows = useMemo(
    () => new Map((savedManualEconomy?.rows ?? []).map((row) => [row.stage_index, row])),
    [savedManualEconomy],
  );
  const rows = useMemo(
    () => previewRows.map((row) => (!dirty ? savedRows.get(row.stage_index) ?? row : row)),
    [dirty, previewRows, savedRows],
  );
  const selectedDraft = useMemo(
    () => (selectedStage ? drafts[selectedStage.stage_index] ?? initialEconomyDraft(selectedStage) : null),
    [drafts, selectedStage],
  );
  const selectedRow = useMemo(
    () => rows.find((row) => row.stage_index === selectedStage?.stage_index) ?? null,
    [rows, selectedStage],
  );
  const stagePoints = useMemo(
    () => selectedStage
      ? analysis.points.filter((point) => (
        typeof point.t_seconds === "number"
        && point.t_seconds >= selectedStage.start_seconds!
        && point.t_seconds <= selectedStage.end_seconds!
      ))
      : [],
    [analysis.points, selectedStage],
  );

  const updateSelectedDraft = useCallback((updater: (draft: ManualEconomyDraft, stage: MetaSoftWarmupStage) => ManualEconomyDraft) => {
    if (!selectedStage || !selectedDraft) return;
    setDrafts((current) => ({
      ...current,
      [selectedStage.stage_index]: clampDraftToStage(updater(selectedDraft, selectedStage), selectedStage),
    }));
    setDirty(true);
    setSaveStatus(null);
  }, [selectedDraft, selectedStage]);

  const handlePlotClick = useCallback((event: Readonly<{ points?: Array<{ x?: unknown }> }>) => {
    if (!selectedStage || !selectedDraft) return;
    if (!excludeMode) return;
    const clicked = typeof event.points?.[0]?.x === "number" ? event.points[0].x : null;
    if (clicked === null) return;
    const width = Math.min(12, Math.max(2, (selectedDraft.endSeconds - selectedDraft.startSeconds) * 0.08));
    const start = clicked - width / 2;
    const end = clicked + width / 2;
    const exclusions = normalizeExclusions(
      [...selectedDraft.exclusions, { start_seconds: start, end_seconds: end }],
      selectedDraft.startSeconds,
      selectedDraft.endSeconds,
    );
    setDrafts((current) => ({
      ...current,
      [selectedStage.stage_index]: clampDraftToStage({ ...selectedDraft, exclusions }, selectedStage),
    }));
    setDirty(true);
    setActiveExclusionIndex(Math.max(0, exclusions.findIndex((item) => start <= item.end_seconds && end >= item.start_seconds)));
    setExcludeMode(false);
    setSaveStatus(null);
  }, [excludeMode, selectedDraft, selectedStage]);

  const toggleStageEnabled = useCallback((stage: MetaSoftWarmupStage) => {
    const draft = drafts[stage.stage_index] ?? initialEconomyDraft(stage);
    setDrafts((current) => ({
      ...current,
      [stage.stage_index]: clampDraftToStage({ ...draft, enabled: !draft.enabled }, stage),
    }));
    setSelectedStageIndex(stage.stage_index);
    setDirty(true);
    setSaveStatus(null);
  }, [drafts]);

  const buildReportPayload = useCallback(() => {
    if (!stableStages.length) return null;
    const stageSelections = stableStages.map((stage) => manualEconomyStageSelection(
      stage,
      drafts[stage.stage_index] ?? initialEconomyDraft(stage),
    ));
    return {
      manual_running_economy_selections: stableStages
        .filter((stage) => (drafts[stage.stage_index] ?? initialEconomyDraft(stage)).enabled)
        .map((stage) => manualEconomySelection(
          stage,
          drafts[stage.stage_index] ?? initialEconomyDraft(stage),
        )),
      manual_running_economy_stage_selections: stageSelections,
    };
  }, [drafts, stableStages]);

  useImperativeHandle(ref, () => ({
    reportPayload: buildReportPayload,
  }), [buildReportPayload]);

  if (!stableStages.length) {
    return (
      <section id="metasoft-running-economy" className="section-block">
        <div className="section-head">
          <h2>EC</h2>
          <p>Aucun etat stable d'echauffement disponible.</p>
        </div>
      </section>
    );
  }

  return (
    <section id="metasoft-running-economy" className="section-block">
      <div className="section-head">
        <h2>EC</h2>
      <p>Selection manuelle dans les etats stables, sauvegardee automatiquement au report profil.</p>
      </div>
      <div className="ec-workbench">
        <section className="panel ec-chart-panel">
          <div className="panel-title-row">
            <h2>Bornes et artefacts</h2>
            <div className="ec-actions">
              <button
                type="button"
                className={excludeMode ? "secondary-button active-action" : "secondary-button"}
                onClick={() => {
                  setExcludeMode((current) => !current);
                  setActiveExclusionIndex(null);
                }}
              >
                <Scissors size={15} />
                Exclure artefact
              </button>
            </div>
          </div>
          {selectedStage && selectedDraft && (
            <>
              <div className="stage-strip">
                {stableStages.map((stage) => (
                  <button
                    key={stage.stage_index}
                    type="button"
                    className={stage.stage_index === selectedStage.stage_index ? "active" : ""}
                    onClick={() => {
                      setSelectedStageIndex(stage.stage_index);
                      setExcludeMode(false);
                      setActiveExclusionIndex(null);
                      setXRange(null);
                    }}
                  >
                    <strong>Palier {stage.stage_index}</strong>
                    <span>{formatNumber(stage.speed_kmh, 1)} km/h</span>
                  </button>
                ))}
              </div>
              <ManualEconomyPlot
                points={stagePoints}
                draft={selectedDraft}
                row={selectedRow}
                xRange={xRange}
                onXRangeChange={setXRange}
                onClick={excludeMode ? handlePlotClick : undefined}
              />
              <div className="duration-pill">
                Duree selectionnee : {formatNumber(selectedDraft.endSeconds - selectedDraft.startSeconds, 0)} s
              </div>
              <div className="bounds-grid">
                <label className="field">
                  Debut
                  <input
                    type="range"
                    min={selectedStage.start_seconds!}
                    max={selectedStage.end_seconds!}
                    step={1}
                    value={selectedDraft.startSeconds}
                    style={rangeFillStyle(selectedDraft.startSeconds, selectedStage.start_seconds!, selectedStage.end_seconds!)}
                    onChange={(event) => updateSelectedDraft((draft) => ({
                      ...draft,
                      startSeconds: Number(event.target.value),
                    }))}
                  />
                  <span>{secondsToClock(selectedDraft.startSeconds)}</span>
                </label>
                <label className="field">
                  Fin
                  <input
                    type="range"
                    min={selectedStage.start_seconds!}
                    max={selectedStage.end_seconds!}
                    step={1}
                    value={selectedDraft.endSeconds}
                    style={rangeFillStyle(selectedDraft.endSeconds, selectedStage.start_seconds!, selectedStage.end_seconds!)}
                    onChange={(event) => updateSelectedDraft((draft) => ({
                      ...draft,
                      endSeconds: Number(event.target.value),
                    }))}
                  />
                  <span>{secondsToClock(selectedDraft.endSeconds)}</span>
                </label>
              </div>
              <div className="exclusion-list">
                {selectedDraft.exclusions.length === 0 && <span className="status-muted">Aucun artefact exclu</span>}
                {selectedDraft.exclusions.map((item, index) => (
                  <button
                    key={`${item.start_seconds}-${item.end_seconds}`}
                    type="button"
                    className={activeExclusionIndex === index ? "table-icon-button active-action" : "table-icon-button"}
                    onClick={() => setActiveExclusionIndex(index)}
                  >
                    Artefact {index + 1}: {secondsToClock(item.start_seconds)} - {secondsToClock(item.end_seconds)}
                  </button>
                ))}
              </div>
              {activeExclusionIndex !== null && selectedDraft.exclusions[activeExclusionIndex] && (
                <ArtifactSliders
                  exclusion={selectedDraft.exclusions[activeExclusionIndex]}
                  index={activeExclusionIndex}
                  min={selectedDraft.startSeconds}
                  max={selectedDraft.endSeconds}
                  onChange={(index, next) => updateSelectedDraft((draft) => ({
                    ...draft,
                    exclusions: normalizeExclusions(
                      draft.exclusions.map((item, itemIndex) => itemIndex === index ? next : item),
                      draft.startSeconds,
                      draft.endSeconds,
                    ),
                  }))}
                  onDelete={(index) => {
                    updateSelectedDraft((draft) => ({
                      ...draft,
                      exclusions: draft.exclusions.filter((_item, itemIndex) => itemIndex !== index),
                    }));
                    setActiveExclusionIndex(null);
                  }}
                />
              )}
              {selectedRow?.warning && <p className="error-text">{selectedRow.warning}</p>}
              {saveStatus && <p className="panel-note">{saveStatus}</p>}
            </>
          )}
        </section>
        <section className="panel">
          <div className="panel-title-row">
            <h2>Tableau EC</h2>
            <span className="status-muted">J/kg/m</span>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Palier</th>
                  <th>JSON</th>
                  <th>Vitesse</th>
                  <th>Bornes</th>
                  <th>N pts</th>
                  <th>VO2</th>
                  <th>%VO2max</th>
                  <th>EC</th>
                  <th>DE</th>
                  <th>DECHO</th>
                  <th>DEFAT</th>
                  <th>DEPRO</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const stage = stableStages.find((item) => item.stage_index === row.stage_index);
                  if (!stage) return null;
                  const draft = drafts[row.stage_index] ?? initialEconomyDraft(stage);
                  const rowClass = [
                    row.stage_index === selectedStage?.stage_index ? "selected-row" : "",
                    draft.enabled ? "" : "muted-row",
                  ].filter(Boolean).join(" ");
                  return (
                    <tr
                      key={row.stage_index}
                      className={rowClass}
                      onClick={() => {
                        setSelectedStageIndex(row.stage_index);
                        setExcludeMode(false);
                        setActiveExclusionIndex(null);
                        setXRange(null);
                      }}
                    >
                      <td>{row.stage_index}</td>
                      <td>
                        <button
                          type="button"
                          className={draft.enabled ? "table-icon-button active-action" : "table-icon-button"}
                          onClick={(event) => {
                            event.stopPropagation();
                            toggleStageEnabled(stage);
                          }}
                        >
                          {draft.enabled ? "Inclus" : "Ecarte"}
                        </button>
                      </td>
                      <td>{formatNumber(row.speed_kmh, 1)}</td>
                      <td>{secondsToClock(row.start_seconds)} - {secondsToClock(row.end_seconds)}</td>
                      <td>{row.point_count}</td>
                      <td>{formatNumber(row.vo2_l_min, 2)}</td>
                      <td>{formatNumber(row.percent_vo2max, 1)}</td>
                      <td className="accent-cell">{formatNumber(row.ec_j_kg_m, 2)}</td>
                      <td>{formatNumber(row.de_kcal_h, 0)}</td>
                      <td>{formatNumber(row.decho_kcal_h, 0)}</td>
                      <td>{formatNumber(row.defat_kcal_h, 0)}</td>
                      <td>{formatNumber(row.depro_kcal_h, 0)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {profileVo2maxMlKgMin === null && (
            <p className="panel-note">VO2max profil requis pour afficher %VO2max.</p>
          )}
        </section>
      </div>
    </section>
  );
}));

const ManualEconomyPlot = memo(function ManualEconomyPlot({
  points,
  draft,
  row,
  xRange,
  onXRangeChange,
  onClick,
}: {
  points: MetaSoftPoint[];
  draft: ManualEconomyDraft;
  row: ManualRunningEconomyRow | null;
  xRange: [number, number] | null;
  onXRangeChange: (range: [number, number] | null) => void;
  onClick?: (event: Readonly<{ points?: Array<{ x?: unknown }> }>) => void;
}) {
  const times = useMemo(() => points.map((point) => point.t_seconds), [points]);
  const vo2Raw = useMemo(() => points.map((point) => numeric(point.values.vo2_l_min)), [points]);
  const vo2Corrected = useMemo(() => correctedSeries(points, draft.exclusions, "vo2_l_min"), [draft.exclusions, points]);
  const vco2Corrected = useMemo(() => correctedSeries(points, draft.exclusions, "vco2_l_min"), [draft.exclusions, points]);
  const veCorrected = useMemo(() => correctedSeries(points, draft.exclusions, "ve_l_min"), [draft.exclusions, points]);
  const defaultRange = useMemo<[number, number]>(() => {
    const numericTimes = times.filter((time): time is number => typeof time === "number" && Number.isFinite(time));
    return numericTimes.length
      ? [Math.min(...numericTimes), Math.max(...numericTimes)]
      : [draft.startSeconds, draft.endSeconds];
  }, [draft.endSeconds, draft.startSeconds, times]);
  const currentRange = useMemo(() => boundedXRange(xRange, defaultRange) ?? defaultRange, [defaultRange, xRange]);
  const tickVals = useMemo(() => buildTickVals(currentRange), [currentRange]);
  const shapes = useMemo(() => [
      {
        type: "rect",
        xref: "x",
        yref: "paper",
        x0: draft.startSeconds,
        x1: draft.endSeconds,
        y0: 0,
        y1: 1,
        fillcolor: "rgba(16, 211, 143, 0.12)",
        line: { color: "rgba(16, 211, 143, 0.7)", width: 1 },
        layer: "below",
      },
      { type: "line", xref: "x", yref: "paper", x0: draft.startSeconds, x1: draft.startSeconds, y0: 0, y1: 1, line: { color: "#76f4b7", width: 2 } },
      { type: "line", xref: "x", yref: "paper", x0: draft.endSeconds, x1: draft.endSeconds, y0: 0, y1: 1, line: { color: "#76f4b7", width: 2 } },
      ...draft.exclusions.map((item) => ({
        type: "rect",
        xref: "x",
        yref: "paper",
        x0: item.start_seconds,
        x1: item.end_seconds,
        y0: 0,
        y1: 1,
        fillcolor: "rgba(255, 96, 96, 0.20)",
        line: { color: "rgba(255, 170, 120, 0.75)", width: 1, dash: "dot" },
        layer: "below",
      })),
    ], [draft.endSeconds, draft.exclusions, draft.startSeconds]);
  const data = useMemo(() => [
    trace("VO2 brut", times, vo2Raw, "#64748b", "dot"),
    trace("VO2 hors artefacts", times, vo2Corrected, "#10a8ff"),
    trace("VCO2 hors artefacts", times, vco2Corrected, "#16e0c2"),
    { ...trace("VE hors artefacts", times, veCorrected, "#ff8a00"), yaxis: "y2" },
  ], [times, vco2Corrected, veCorrected, vo2Corrected, vo2Raw]);
  const annotations = useMemo(() => row?.ec_j_kg_m ? [{
    x: draft.endSeconds,
    y: 1,
    xref: "x",
    yref: "paper",
    text: `EC ${formatNumber(row.ec_j_kg_m, 2)}`,
    showarrow: false,
    font: { color: "#76f4b7", size: 11 },
    bgcolor: "rgba(6,20,36,0.82)",
    bordercolor: "rgba(16,211,143,0.32)",
    borderpad: 4,
  }] : [], [draft.endSeconds, row?.ec_j_kg_m]);
  const tickText = useMemo(() => tickVals.map(secondsToClock), [tickVals]);
  const layout = useMemo(() => ({
    autosize: true,
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    margin: { l: 44, r: 44, t: 12, b: 38 },
    font: { color: "rgba(226,232,240,0.78)", size: 10 },
    hovermode: "x unified",
    showlegend: true,
    legend: { orientation: "h", x: 0, y: 1.12, font: { size: 10 } },
    shapes,
    annotations,
    xaxis: {
      range: currentRange,
      tickvals: tickVals,
      ticktext: tickText,
      gridcolor: "rgba(255,255,255,0.055)",
    },
    yaxis: { title: "L/min", fixedrange: true, gridcolor: "rgba(255,255,255,0.055)" },
    yaxis2: { title: "VE", fixedrange: true, overlaying: "y", side: "right", gridcolor: "rgba(255,255,255,0)" },
    uirevision: `manual-running-economy-${defaultRange[0]}-${defaultRange[1]}`,
  }), [annotations, currentRange, defaultRange, shapes, tickText, tickVals]);
  const handleRelayout = useCallback((event: Readonly<Record<string, unknown>>) => {
    const nextRange = xRangeFromRelayout(event);
    if (nextRange !== undefined) onXRangeChange(boundedXRange(nextRange, defaultRange));
  }, [defaultRange, onXRangeChange]);
  return (
    <Plot
      data={data}
      layout={layout}
      config={{ responsive: true, displayModeBar: false, doubleClick: "reset" }}
      style={{ width: "100%", height: 330 }}
      useResizeHandler
      onClick={onClick}
      onRelayout={handleRelayout}
      onDoubleClick={() => onXRangeChange(null)}
    />
  );
});

function ArtifactSliders({
  exclusion,
  index,
  min,
  max,
  onChange,
  onDelete,
}: {
  exclusion: { start_seconds: number; end_seconds: number };
  index: number;
  min: number;
  max: number;
  onChange: (index: number, next: { start_seconds: number; end_seconds: number }) => void;
  onDelete: (index: number) => void;
}) {
  return (
    <div className="artifact-editor">
      <div className="panel-title-row">
        <strong>Artefact {index + 1}</strong>
        <button type="button" className="table-icon-button" onClick={() => onDelete(index)}>
          <Trash2 size={13} />
          Supprimer
        </button>
      </div>
      <div className="bounds-grid artifact-bounds">
        <label className="field">
          Debut artefact
          <input
            type="range"
            min={min}
            max={max}
            step={0.2}
            value={exclusion.start_seconds}
            style={rangeFillStyle(exclusion.start_seconds, min, max)}
            onChange={(event) => onChange(index, {
              ...exclusion,
              start_seconds: Number(event.target.value),
            })}
          />
          <span>{secondsToClock(exclusion.start_seconds)}</span>
        </label>
        <label className="field">
          Fin artefact
          <input
            type="range"
            min={min}
            max={max}
            step={0.2}
            value={exclusion.end_seconds}
            style={rangeFillStyle(exclusion.end_seconds, min, max)}
            onChange={(event) => onChange(index, {
              ...exclusion,
              end_seconds: Number(event.target.value),
            })}
          />
          <span>{secondsToClock(exclusion.end_seconds)}</span>
        </label>
      </div>
    </div>
  );
}

function trace(
  name: string,
  x: Array<number | null>,
  y: Array<number | null>,
  color: string,
  dash = "solid",
) {
  return {
    type: "scatter",
    mode: "lines",
    name,
    x,
    y,
    line: { color, width: dash === "solid" ? 1.6 : 1, dash },
    connectgaps: false,
  };
}

function rangeFillStyle(value: number, min: number, max: number): CSSProperties {
  const span = max - min;
  const progress = span > 0 ? Math.min(100, Math.max(0, ((value - min) / span) * 100)) : 0;
  return { "--range-progress": `${progress}%` } as CSSProperties;
}

function draftFromSavedRow(row: ManualRunningEconomyRow): ManualEconomyDraft {
  return {
    stageIndex: row.stage_index,
    enabled: true,
    startSeconds: row.start_seconds,
    endSeconds: row.end_seconds,
    exclusions: row.exclusions,
  };
}

function hasStageBounds(stage: MetaSoftWarmupStage): boolean {
  return typeof stage.start_seconds === "number"
    && typeof stage.end_seconds === "number"
    && stage.end_seconds > stage.start_seconds;
}

function numeric(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function xRangeFromRelayout(event: Readonly<Record<string, unknown>>): [number, number] | null | undefined {
  if (event["xaxis.autorange"] === true) return null;
  const eventRange = toRangeTuple(event["xaxis.range"]);
  if (eventRange) return eventRange;
  const start = toNumber(event["xaxis.range[0]"]);
  const end = toNumber(event["xaxis.range[1]"]);
  if (start === null || end === null || end <= start) return undefined;
  return [start, end];
}

function boundedXRange(range: [number, number] | null, bounds: [number, number]): [number, number] | null {
  if (!range) return null;
  const start = Math.max(bounds[0], range[0]);
  const end = Math.min(bounds[1], range[1]);
  return end > start ? [start, end] : null;
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

function buildTickVals(range: [number, number]): number[] {
  const span = range[1] - range[0];
  if (span <= 0) return [];
  const step = span > 2400 ? 600 : span > 900 ? 300 : span > 300 ? 60 : span > 120 ? 30 : 10;
  const vals = [];
  for (let value = Math.ceil(range[0] / step) * step; value <= range[1]; value += step) vals.push(value);
  return vals;
}
