import {
  memo,
  useMemo,
  useRef,
  useState,
  type DragEvent,
  type MouseEvent as ReactMouseEvent,
} from "react";
import Plot from "react-plotly.js";
import { GripVertical, Plus, Trash2 } from "lucide-react";
import {
  ChartActionPopover,
  ChartPlacementPopover,
  ChartScaleControls,
  ChartSeriesToggles,
  chartPopoverPosition,
  type ChartPopoverPosition,
  type ChartSeriesOption,
  useChartClickArbitration,
} from "./ChartControls";
import {
  buildSpeedStepLinePoints,
  buildStaticAnnotations,
  buildTimeBandShapes,
  speedSegmentsForAnalysis,
} from "../lib/chartUtils";
import {
  buildTickVals,
  scaledAxisRange,
  xRangeFromRelayout,
} from "../lib/metasoftChartHelpers";
import { secondsToClock } from "../lib/markerUtils";
import type {
  LactateMeasurementDraft,
  LactateThresholdDraft,
  LactateTestDraft,
  MetaSoftAnalysis,
} from "../types/metasoft";

type LactateThresholdName = "sl1" | "sl2";
type LactateThresholdMode = LactateThresholdDraft["mode"];
type LactateTimelineItem = {
  item: LactateMeasurementDraft;
  index: number;
  label: string;
  timeSeconds: number;
  speed: number;
};
const LACTATE_PLOT_MARGINS = { l: 54, r: 48, t: 42, b: 92 };
const LACTATE_SERIES: ChartSeriesOption[] = [
  { key: "lactate", label: "Lactate", color: "#ff5f6d" },
  { key: "protocol", label: "Paliers vitesse", color: "#10d38f" },
];

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
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
  const [dropIndex, setDropIndex] = useState<number | null>(null);
  const plotWrapRef = useRef<HTMLDivElement | null>(null);
  const suppressThresholdClickRef = useRef(false);
  const plotPointerStartRef = useRef<{ x: number; y: number } | null>(null);
  const ignoreRelayoutUntilRef = useRef(0);
  const [thresholdProposal, setThresholdProposal] = useState<{
    timeSeconds: number;
    speed: number;
    mode: LactateThresholdMode;
    rangeDurationSeconds: string;
    position: ChartPopoverPosition;
  } | null>(null);
  const [thresholdDrag, setThresholdDrag] = useState<{
    name: LactateThresholdName;
    initial: LactateThresholdDraft;
  } | null>(null);
  const [thresholdMenu, setThresholdMenu] = useState<{
    name: LactateThresholdName;
    rangeDurationSeconds: string;
    position: ChartPopoverPosition;
  } | null>(null);
  const [thresholdPreview, setThresholdPreview] = useState<LactateTestDraft["thresholds"] | null>(null);
  const [lactateXRange, setLactateXRange] = useState<[number, number] | null>(null);
  const [lactateZoomRevision, setLactateZoomRevision] = useState(0);
  const [lactateYScaleFactor, setLactateYScaleFactor] = useState(1);
  const [hiddenSeries, setHiddenSeries] = useState<Set<string>>(new Set());
  const {
    block: blockThresholdClicks,
    cancel: cancelThresholdClick,
    isBlocked: thresholdClicksBlocked,
    schedule: scheduleThresholdClick,
  } = useChartClickArbitration();

  const updateMeasurement = (index: number, patch: Partial<LactateMeasurementDraft>) => {
    const current = draft.measurements[index];
    const autoIncludesRecovery = Boolean(current)
      && (current.type === "recovery" || current.type === "rest_after")
      && Object.prototype.hasOwnProperty.call(patch, "lactate_mmol_l")
      && numeric(patch.lactate_mmol_l) !== null
      && current.inclusion_touched !== true;
    const measurements = draft.measurements.map((item, itemIndex) => {
      if (itemIndex !== index) return item;
      return { ...item, ...patch, ...(autoIncludesRecovery ? { enabled: true } : {}) };
    });
    const timelineChanged = patch.enabled !== undefined
      || patch.speed !== undefined
      || autoIncludesRecovery;
    onChange({
      ...draft,
      measurements,
      thresholds: timelineChanged
        ? rebuildLactateThresholds(draft.thresholds, measurements)
        : draft.thresholds,
    });
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
    onChange({
      ...draft,
      measurements,
      thresholds: rebuildLactateThresholds(draft.thresholds, measurements),
    });
  };
  const addRecovery = () => {
    const delays = draft.measurements
      .filter((item) => item.type === "recovery" || item.type === "rest_after")
      .map((item) => item.delay_minutes)
      .filter((value): value is number => typeof value === "number");
    const measurements: LactateMeasurementDraft[] = [...draft.measurements, {
        type: "recovery",
        source: "manual",
        enabled: true,
        speed: 0,
        lactate_mmol_l: null,
        delay_minutes: delays.length ? Math.max(...delays) + 5 : 3,
      }];
    onChange({
      ...draft,
      measurements,
      thresholds: rebuildLactateThresholds(draft.thresholds, measurements),
    });
  };
  const moveStage = (from: number, to: number) => {
    if (from === to || draft.measurements[from]?.type !== "stage" || draft.measurements[to]?.type !== "stage") return;
    const moved = draft.measurements[from];
    const measurements = [...draft.measurements];
    measurements.splice(from, 1);
    measurements.splice(to, 0, moved);
    onChange({
      ...draft,
      measurements,
      thresholds: rebuildLactateThresholds(draft.thresholds, measurements),
    });
  };
  const timelineItems = useMemo<LactateTimelineItem[]>(
    () => buildLactateTimelineItems(draft.measurements),
    [draft.measurements],
  );
  const graphItems = useMemo(() => timelineItems.filter(({ item }) => (
    numeric(item.lactate_mmol_l) !== null
  )), [timelineItems]);
  const thresholdStages = useMemo(
    () => buildLactateTimelineItems(draft.measurements, true).filter(({ item, speed }) => (
      item.type === "stage" && speed > 0
    )),
    [draft.measurements],
  );
  const defaultXRange = useMemo<[number, number]>(() => {
    const times = timelineItems.map((entry) => entry.timeSeconds);
    if (!times.length) return [0, 60];
    const start = Math.min(...times);
    const end = Math.max(...times);
    const padding = Math.max((end - start) * 0.025, 5);
    return [Math.max(0, start - padding), end + padding];
  }, [timelineItems]);
  const protocolPoints = useMemo(
    () => lactateProtocolPoints(analysis, defaultXRange[1]),
    [analysis, defaultXRange],
  );
  const visibleThresholds = thresholdPreview ?? draft.thresholds;
  const effectiveXRange = lactateXRange
    && lactateXRange[0] >= defaultXRange[0]
    && lactateXRange[1] <= defaultXRange[1]
    ? lactateXRange
    : null;
  const visibleXRange = effectiveXRange ?? defaultXRange;
  const xTickVals = useMemo(() => buildTickVals(visibleXRange), [visibleXRange]);
  const lactateYRange = useMemo(
    () => scaledAxisRange(graphItems.map((entry) => entry.item.lactate_mmol_l), lactateYScaleFactor),
    [graphItems, lactateYScaleFactor],
  );
  const availableSeries = useMemo(() => LACTATE_SERIES.filter((series) => {
    return series.key === "lactate" ? graphItems.length > 0 : protocolPoints.x.length > 0;
  }), [graphItems.length, protocolPoints.x.length]);
  const showLactateScale = graphItems.length > 0 && !hiddenSeries.has("lactate");

  const placeThreshold = (
    name: LactateThresholdName,
  ) => {
    if (!thresholdProposal) return;
    const selection = buildLactateThresholdAtPosition(
      thresholdProposal.timeSeconds,
      thresholdProposal.mode,
      numericInput(thresholdProposal.rangeDurationSeconds),
      thresholdStages,
    );
    if (!selection) return;
    onChange({ ...draft, thresholds: { ...draft.thresholds, [name]: selection } });
    setThresholdProposal(null);
  };

  const resetLactateZoom = () => {
    ignoreRelayoutUntilRef.current = Date.now() + 600;
    setLactateXRange(null);
    setLactateZoomRevision((revision) => revision + 1);
  };

  const thresholdFromClientX = (clientX: number) => timelineTimeFromClientX(
    clientX,
    plotWrapRef.current,
    visibleXRange,
  );

  const beginThresholdDrag = (event: ReactMouseEvent<HTMLDivElement>) => {
    if (event.button !== 0 || event.detail > 1) return;
    if (isLactateChartControlTarget(event.target)) return;
    const timeSeconds = thresholdFromClientX(event.clientX);
    const target = timeSeconds === null
      ? null
      : nearestLactateThresholdName(visibleThresholds, timeSeconds, visibleXRange, plotWrapRef.current, thresholdStages);
    if (!target) return;
    const initial = visibleThresholds[target];
    if (!initial) return;
    event.preventDefault();
    suppressThresholdClickRef.current = true;
    cancelThresholdClick();
    setThresholdProposal(null);
    setThresholdMenu(null);
    setThresholdDrag({ name: target, initial });
    setThresholdPreview(draft.thresholds);
  };

  const moveThresholdDrag = (event: ReactMouseEvent<HTMLDivElement>) => {
    if (!thresholdDrag) return;
    const timeSeconds = thresholdFromClientX(event.clientX);
    if (timeSeconds === null) return;
    const selection = buildLactateThresholdAtPosition(
      timeSeconds,
      thresholdDrag.initial.mode,
      lactateThresholdDuration(thresholdDrag.initial),
      thresholdStages,
    );
    if (!selection) return;
    setThresholdPreview({ ...draft.thresholds, [thresholdDrag.name]: selection });
  };

  const endThresholdDrag = () => {
    if (!thresholdDrag || !thresholdPreview) return;
    onChange({ ...draft, thresholds: thresholdPreview });
    setThresholdDrag(null);
    setThresholdPreview(null);
    window.setTimeout(() => {
      suppressThresholdClickRef.current = false;
    }, 0);
  };

  const openThresholdProposal = (event: ReactMouseEvent<HTMLDivElement>) => {
    if (isLactateChartControlTarget(event.target)) return;
    if (event.detail > 1) {
      blockThresholdClicks();
      return;
    }
    if (
      thresholdClicksBlocked()
      || suppressThresholdClickRef.current
    ) {
      suppressThresholdClickRef.current = false;
      return;
    }
    const bounds = plotWrapRef.current?.getBoundingClientRect();
    if (
      !bounds
      || event.clientY < bounds.top + LACTATE_PLOT_MARGINS.t
      || event.clientY > bounds.bottom - LACTATE_PLOT_MARGINS.b
    ) return;
    const timeSeconds = thresholdFromClientX(event.clientX);
    const speed = timeSeconds === null ? null : speedAtTimelineTime(timeSeconds, thresholdStages);
    if (timeSeconds !== null && speed !== null && speed > 0) {
      const position = chartPopoverPosition(event.clientX, event.clientY, 238);
      scheduleThresholdClick(() => {
        setThresholdMenu(null);
        setThresholdProposal({
          timeSeconds,
          speed: clamp(speed, 0.1, 40),
          mode: "point",
          rangeDurationSeconds: "60",
          position,
        });
      });
    }
  };

  const openThresholdMenu = (event: ReactMouseEvent<HTMLDivElement>) => {
    if (isLactateChartControlTarget(event.target)) return;
    blockThresholdClicks();
    const timeSeconds = thresholdFromClientX(event.clientX);
    const target = timeSeconds === null
      ? null
      : nearestLactateThresholdName(visibleThresholds, timeSeconds, visibleXRange, plotWrapRef.current, thresholdStages);
    if (!target) return;
    event.preventDefault();
    suppressThresholdClickRef.current = true;
    setThresholdProposal(null);
    const threshold = visibleThresholds[target];
    setThresholdMenu({
      name: target,
      rangeDurationSeconds: threshold?.mode === "range"
        ? String(Math.round(lactateThresholdDuration(threshold) ?? 60))
        : "",
      position: chartPopoverPosition(event.clientX, event.clientY, 210, 280),
    });
  };

  const trackPlotPointerDown = (event: ReactMouseEvent<HTMLDivElement>) => {
    plotPointerStartRef.current = event.button === 0 && event.detail === 1
      ? { x: event.clientX, y: event.clientY }
      : null;
  };

  const trackPlotPointerUp = (event: ReactMouseEvent<HTMLDivElement>) => {
    const start = plotPointerStartRef.current;
    plotPointerStartRef.current = null;
    if (!start || Math.hypot(event.clientX - start.x, event.clientY - start.y) <= 4) return;
    suppressThresholdClickRef.current = true;
    window.setTimeout(() => {
      suppressThresholdClickRef.current = false;
    }, 0);
  };

  const toggleSeries = (series: ChartSeriesOption) => {
    setHiddenSeries((current) => {
      const next = new Set(current);
      if (next.has(series.key)) next.delete(series.key);
      else next.add(series.key);
      return next;
    });
  };

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
                <p className="panel-note">Glissez les paliers pour les reordonner. Saisir une recuperation l'inclut automatiquement ; une ligne ecartee reste sauvegardee mais est masquee du graphe et du JSON officiel.</p>
              </div>
              <div className="ec-actions">
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => {
                    if (!window.confirm("Remplacer les paliers lactate par ceux detectes dans le XML courant ?")) return;
                    onChange(buildDetectedLactateDraft(analysis, true));
                  }}
                >
                  Re-detecter depuis le XML
                </button>
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
                    <tr><th>Ordre</th><th>Statut</th><th>Repere</th><th>Vitesse</th><th>Delai</th><th>Lactate</th></tr>
                  </thead>
                  <tbody>
                    {draft.measurements.map((item, index) => (
                      <tr
                        key={`${item.type}-${item.stage_index ?? "manual"}-${index}`}
                        className={[
                          item.enabled === false ? "muted-row" : "",
                          draggedIndex === index ? "lactate-dragging-row" : "",
                          dropIndex === index && draggedIndex !== null && draggedIndex !== index
                            ? draggedIndex < index ? "lactate-drop-after" : "lactate-drop-before"
                            : "",
                        ].filter(Boolean).join(" ")}
                        onDragEnter={() => {
                          if (item.type === "stage" && draggedIndex !== null && draggedIndex !== index) setDropIndex(index);
                        }}
                        onDragOver={(event) => {
                          if (item.type === "stage" && draggedIndex !== null) {
                            event.preventDefault();
                            event.dataTransfer.dropEffect = "move";
                          }
                        }}
                        onDrop={(event) => {
                          event.preventDefault();
                          if (draggedIndex !== null) moveStage(draggedIndex, index);
                          setDraggedIndex(null);
                          setDropIndex(null);
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
                                setDropIndex(null);
                              }}
                              onDragEnd={() => {
                                setDraggedIndex(null);
                                setDropIndex(null);
                              }}
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
                            onClick={() => updateMeasurement(index, {
                              enabled: item.enabled === false,
                              inclusion_touched: true,
                            })}
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
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="lactate-graph">
                <div className="lactate-threshold-panel">
                  <div>
                    <strong>Seuils lactiques</strong>
                    <p>Cliquez la courbe pour placer SL1 ou SL2. Glissez le trait pour le deplacer ; double-cliquez pour modifier sa duree ou le supprimer.</p>
                  </div>
                  {(["sl1", "sl2"] as const).map((name) => (
                    <div className="lactate-threshold-row" key={name}>
                      <strong>{name.toUpperCase()}</strong>
                      <span>{lactateThresholdLabel(visibleThresholds[name])}</span>
                      {visibleThresholds[name] && (
                        <button
                          type="button"
                          className="table-icon-button"
                          onClick={() => onChange({
                            ...draft,
                            thresholds: { ...draft.thresholds, [name]: null },
                          })}
                          aria-label={`Supprimer ${name.toUpperCase()}`}
                        >
                          <Trash2 size={14} />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
                {timelineItems.length ? (
                  <>
                    <div className="lactate-chart-toolbar">
                      <ChartSeriesToggles
                        series={availableSeries}
                        hiddenSeries={hiddenSeries}
                        onToggle={toggleSeries}
                      />
                      {(showLactateScale || effectiveXRange !== null) && (
                        <ChartScaleControls
                          series={[LACTATE_SERIES[0]]}
                          mode="common"
                          selectedSeriesKey="lactate"
                          onModeChange={() => undefined}
                          onSelectedSeriesChange={() => undefined}
                          onZoomIn={() => setLactateYScaleFactor((factor) => factor * 0.8)}
                          onZoomOut={() => setLactateYScaleFactor((factor) => factor * 1.25)}
                          onAuto={() => setLactateYScaleFactor(1)}
                          onResetZoom={resetLactateZoom}
                          showResetZoom={effectiveXRange !== null}
                          showScaleButtons={showLactateScale}
                        />
                      )}
                    </div>
                    <div
                      ref={plotWrapRef}
                      className="lactate-plot-wrap"
                      onMouseDownCapture={trackPlotPointerDown}
                      onMouseUpCapture={trackPlotPointerUp}
                      onMouseDown={beginThresholdDrag}
                      onMouseMove={moveThresholdDrag}
                      onMouseUp={endThresholdDrag}
                      onMouseLeave={endThresholdDrag}
                      onClickCapture={openThresholdProposal}
                      onDoubleClick={openThresholdMenu}
                      onContextMenu={openThresholdMenu}
                    >
                    <Plot
                      key={`lactate-${lactateZoomRevision}`}
                      data={[
                        ...(!hiddenSeries.has("lactate") && graphItems.length ? [{
                          type: "scatter",
                          mode: "lines+markers",
                          name: "Lactate",
                          x: graphItems.map((entry) => entry.timeSeconds),
                          y: graphItems.map((entry) => entry.item.lactate_mmol_l),
                          text: graphItems.map((entry) => `${entry.label}<br>${formatSpeed(entry.speed)} km/h`),
                          hovertemplate: "%{text}<br>%{y:.1f} mmol/L<extra></extra>",
                          line: { color: "#ff5f6d", width: 2 },
                          marker: { color: "#ff5f6d", size: 8 },
                        }] : []),
                        ...(!hiddenSeries.has("protocol") && protocolPoints.x.length ? [{
                          type: "scatter",
                          mode: "lines",
                          name: "Paliers vitesse",
                          x: protocolPoints.x,
                          y: protocolPoints.y,
                          hovertemplate: "%{y:.1f} km/h<extra></extra>",
                          yaxis: "y2",
                          line: { color: "#10d38f", width: 1.5, shape: "hv" },
                        }] : []),
                      ]}
                      layout={{
                        autosize: true,
                        paper_bgcolor: "rgba(0,0,0,0)",
                        plot_bgcolor: "rgba(0,0,0,0)",
                        margin: LACTATE_PLOT_MARGINS,
                        font: { color: "rgba(226,232,240,0.78)", size: 11 },
                        hovermode: "closest",
                        dragmode: "zoom",
                        xaxis: {
                          title: "Temps du test",
                          range: [visibleXRange[0], visibleXRange[1]],
                          tickvals: xTickVals,
                          ticktext: xTickVals.map(secondsToClock),
                          gridcolor: "rgba(255,255,255,0.055)",
                          zerolinecolor: "rgba(255,255,255,0.16)",
                        },
                        yaxis: {
                          title: "Lactate (mmol/L)",
                          range: lactateYRange && [lactateYRange[0], lactateYRange[1]],
                          gridcolor: "rgba(255,255,255,0.055)",
                        },
                        yaxis2: {
                          title: "Vitesse (km/h)",
                          overlaying: "y",
                          side: "right",
                          showgrid: false,
                          visible: !hiddenSeries.has("protocol"),
                        },
                        shapes: [
                          ...(!hiddenSeries.has("protocol") ? buildTimeBandShapes(analysis) : []),
                          ...lactateThresholdShapes(visibleThresholds, thresholdStages),
                        ],
                        annotations: [
                          ...(!hiddenSeries.has("protocol") ? buildStaticAnnotations(analysis) : []),
                          ...lactateThresholdAnnotations(visibleThresholds, thresholdStages),
                        ],
                      }}
                      config={{
                        responsive: true,
                        displayModeBar: false,
                        displaylogo: false,
                        scrollZoom: false,
                        doubleClick: false,
                      }}
                      style={{ width: "100%", height: 380 }}
                      useResizeHandler
                      onRelayout={(event: Readonly<Record<string, unknown>>) => {
                        if (Date.now() < ignoreRelayoutUntilRef.current) return;
                        const range = xRangeFromRelayout(event);
                        if (range !== undefined) setLactateXRange(range);
                      }}
                    />
                    {thresholdProposal && (
                      <ChartPlacementPopover
                        position={thresholdProposal.position}
                        title="Placer un seuil lactique"
                        valueLabel={`${secondsToClock(thresholdProposal.timeSeconds)} · ${formatSpeed(thresholdProposal.speed)} km/h`}
                        modes={[
                          { value: "point" as const, label: "Ligne" },
                          { value: "range" as const, label: "Range" },
                        ]}
                        activeMode={thresholdProposal.mode}
                        onModeChange={(mode) => setThresholdProposal({ ...thresholdProposal, mode })}
                        help={thresholdProposal.mode === "range"
                          ? "Plage centree sur le clic, entierement comprise entre le premier et le dernier palier."
                          : "Trait place a la vitesse selectionnee."}
                        onClose={() => setThresholdProposal(null)}
                      >
                        {thresholdProposal.mode === "range" && (
                          <label className="field small-field">
                            Duree de la plage (secondes)
                            <input
                              type="number"
                              min="1"
                              step="1"
                              inputMode="numeric"
                              value={thresholdProposal.rangeDurationSeconds}
                              onChange={(event) => setThresholdProposal({
                                ...thresholdProposal,
                                rangeDurationSeconds: event.target.value,
                              })}
                              placeholder="60"
                            />
                          </label>
                        )}
                        <div className="marker-choice-grid lactate-threshold-choices">
                          {(["sl1", "sl2"] as const).map((name) => (
                            <button
                              key={name}
                              type="button"
                              disabled={thresholdProposal.mode === "range"
                                && !validLactateRangeDuration(
                                  thresholdProposal.rangeDurationSeconds,
                                  thresholdStages,
                                  thresholdProposal.timeSeconds,
                                )}
                              style={{ color: name === "sl1" ? "#16e0c2" : "#ff8a00", borderColor: name === "sl1" ? "#16e0c288" : "#ff8a0088" }}
                              onClick={() => placeThreshold(name)}
                            >
                              {name.toUpperCase()}
                            </button>
                          ))}
                        </div>
                      </ChartPlacementPopover>
                    )}
                    {thresholdMenu && visibleThresholds[thresholdMenu.name] && (
                      <ChartActionPopover
                        position={thresholdMenu.position}
                        eyebrow="Seuil lactique"
                        title={thresholdMenu.name.toUpperCase()}
                        ariaLabel={`Modifier ${thresholdMenu.name.toUpperCase()}`}
                        onClose={() => setThresholdMenu(null)}
                      >
                        {visibleThresholds[thresholdMenu.name]?.mode === "range" && (
                          <label className="field small-field">
                            Duree de la plage (secondes)
                            <input
                              type="number"
                              min="1"
                              step="1"
                              inputMode="numeric"
                              value={thresholdMenu.rangeDurationSeconds}
                              onChange={(event) => setThresholdMenu({
                                ...thresholdMenu,
                                rangeDurationSeconds: event.target.value,
                              })}
                              placeholder="60"
                            />
                          </label>
                        )}
                        <div className="marker-menu-actions">
                          {visibleThresholds[thresholdMenu.name]?.mode === "range" && (
                            <button
                              type="button"
                              className="secondary-button"
                              disabled={!validLactateRangeDuration(
                                thresholdMenu.rangeDurationSeconds,
                                thresholdStages,
                                visibleThresholds[thresholdMenu.name]
                                  ? lactateThresholdTime(visibleThresholds[thresholdMenu.name]!, thresholdStages)
                                  : null,
                              )}
                              onClick={() => {
                                const current = visibleThresholds[thresholdMenu.name];
                                if (!current) return;
                                const center = lactateThresholdTime(current, thresholdStages);
                                const next = center === null ? null : buildLactateThresholdAtPosition(
                                  center,
                                  "range",
                                  numericInput(thresholdMenu.rangeDurationSeconds),
                                  thresholdStages,
                                );
                                if (!next) return;
                                onChange({
                                  ...draft,
                                  thresholds: { ...draft.thresholds, [thresholdMenu.name]: next },
                                });
                                setThresholdMenu(null);
                              }}
                            >
                              Modifier la duree
                            </button>
                          )}
                          <button
                            type="button"
                            className="danger-button"
                            onClick={() => {
                              onChange({
                                ...draft,
                                thresholds: { ...draft.thresholds, [thresholdMenu.name]: null },
                              });
                              setThresholdMenu(null);
                            }}
                          >
                            Supprimer
                          </button>
                        </div>
                      </ChartActionPopover>
                    )}
                    </div>
                  </>
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
  profileProvenanceValid = true,
): LactateTestDraft {
  if (initialDraft) return mergeLactateDraft(initialDraft, analysis);
  if (!profileProvenanceValid) return buildDetectedLactateDraft(analysis, false);
  const stress = profile.stress_test_results && typeof profile.stress_test_results === "object"
    ? profile.stress_test_results as Record<string, unknown>
    : {};
  const raw = Array.isArray(stress.lactate_profile) ? stress.lactate_profile : [];
  const measurements = raw.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
    .map(profileMeasurement);
  const thresholds = stress.lactate_thresholds && typeof stress.lactate_thresholds === "object"
    ? stress.lactate_thresholds as Record<string, Record<string, unknown>>
    : {};
  const profileDraft = {
    active: measurements.length > 0,
    measurements,
    thresholds: {
      sl1: lactateThresholdFromSaved(thresholds.sl1, measurements),
      sl2: lactateThresholdFromSaved(thresholds.sl2, measurements),
    },
  };
  return measurements.length && profileMatchesAnalysis(measurements, analysis)
    ? mergeLactateDraft(profileDraft, analysis)
    : buildDetectedLactateDraft(analysis, false);
}

export function buildDetectedLactateDraft(analysis: MetaSoftAnalysis, active = false): LactateTestDraft {
  return { active, measurements: detectedMeasurements(analysis), thresholds: { sl1: null, sl2: null } };
}

export function lactateReportSummary(draft: LactateTestDraft): LactateReportSummary {
  const included = draft.measurements.filter((item) => item.enabled !== false);
  return {
    active: draft.active,
    includedCount: included.length,
    excludedCount: draft.measurements.length - included.length,
    validCount: included.filter((item) => numeric(item.lactate_mmol_l) !== null).length,
    sl1: lactateThresholdLabel(draft.thresholds.sl1),
    sl2: lactateThresholdLabel(draft.thresholds.sl2),
  };
}

function mergeLactateDraft(draft: LactateTestDraft, analysis: MetaSoftAnalysis): LactateTestDraft {
  const saved = draft.measurements.map((item) => {
    const migrateFilledRecovery = (item.type === "recovery" || item.type === "rest_after")
      && item.enabled === false
      && item.inclusion_touched !== true
      && numeric(item.lactate_mmol_l) !== null;
    return {
      ...item,
      enabled: migrateFilledRecovery || item.enabled !== false,
      source: item.source ?? (item.type === "stage" ? "manual" : "detected"),
    };
  });
  const detected = detectedMeasurements(analysis);
  const detectedStages = detected.filter((item) => item.type === "stage");
  const usedSaved = new Set<number>();
  const savedMatchByDetected = new Map<LactateMeasurementDraft, number>();
  detectedStages.forEach((stage) => {
    const index = bestSavedStageMatch(saved, stage, usedSaved);
    if (index >= 0) {
      usedSaved.add(index);
      savedMatchByDetected.set(stage, index);
    }
  });

  const allDetectedAlreadyPresent = detectedStages.length > 0 && savedMatchByDetected.size === detectedStages.length;
  let entries: Array<{ item: LactateMeasurementDraft; savedIndex: number | null }>;
  if (allDetectedAlreadyPresent) {
    const detectedBySaved = new Map(Array.from(savedMatchByDetected, ([stage, index]) => [index, stage]));
    entries = saved.map((item, index) => {
      const current = detectedBySaved.get(index);
      return {
        savedIndex: index,
        item: current ? mergeDetectedStage(current, item) : item,
      };
    });
    for (const structural of detected.filter((item) => item.type !== "stage")) {
      if (hasStructuralMeasurement(entries.map((entry) => entry.item), structural)) continue;
      const entry = { item: structural, savedIndex: null };
      if (structural.type === "rest_before") entries.unshift(entry);
      else if (structural.type === "post_warmup") entries.splice(entries[0]?.item.type === "rest_before" ? 1 : 0, 0, entry);
      else entries.push(entry);
    }
  } else {
    entries = detected.map((item) => {
      if (item.type !== "stage") {
        const index = saved.findIndex((candidate, savedIndex) => !usedSaved.has(savedIndex) && sameStructuralMeasurement(candidate, item));
        if (index >= 0) usedSaved.add(index);
        return { item: index >= 0 ? { ...item, ...saved[index], source: item.source } : item, savedIndex: index >= 0 ? index : null };
      }
      const index = savedMatchByDetected.get(item);
      return { item: index === undefined ? item : mergeDetectedStage(item, saved[index]), savedIndex: index ?? null };
    });
    const manual = saved.flatMap((item, index) => (
      !usedSaved.has(index) && (item.type === "stage" || item.source === "manual")
        ? [{ item, savedIndex: index }]
        : []
    ));
    const recoveryIndex = entries.findIndex((entry) => entry.item.type === "recovery" || entry.item.type === "rest_after");
    entries.splice(recoveryIndex < 0 ? entries.length : recoveryIndex, 0, ...manual);
  }

  return {
    ...draft,
    measurements: entries.map((entry) => entry.item),
    thresholds: {
      sl1: lactateThresholdFromSaved(draft.thresholds.sl1, saved),
      sl2: lactateThresholdFromSaved(draft.thresholds.sl2, saved),
    },
  };
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

function bestSavedStageMatch(
  saved: LactateMeasurementDraft[],
  detected: LactateMeasurementDraft,
  used: Set<number>,
): number {
  let bestIndex = -1;
  let bestScore = Number.POSITIVE_INFINITY;
  saved.forEach((candidate, index) => {
    if (used.has(index) || candidate.type !== "stage") return;
    const sameIndex = candidate.source === "detected"
      && candidate.stage_index === detected.stage_index;
    const sameTime = candidate.source === "detected"
      && numeric(candidate.time_seconds) !== null
      && numeric(detected.time_seconds) !== null
      && Math.abs(numeric(candidate.time_seconds)! - numeric(detected.time_seconds)!) <= 2;
    const sameSpeed = numeric(candidate.speed) !== null
      && numeric(detected.speed) !== null
      && Math.abs(numeric(candidate.speed)! - numeric(detected.speed)!) <= 0.11;
    const score = sameIndex ? 0 : sameTime ? 1 : sameSpeed ? (candidate.source === "detected" ? 2 : 3) : 99;
    if (score < bestScore) {
      bestScore = score;
      bestIndex = index;
    }
  });
  return bestScore < 99 ? bestIndex : -1;
}

function mergeDetectedStage(
  detected: LactateMeasurementDraft,
  saved: LactateMeasurementDraft,
): LactateMeasurementDraft {
  return {
    ...detected,
    ...saved,
    source: "detected",
    stage_index: detected.stage_index,
    phase: detected.phase,
    time_seconds: detected.time_seconds,
  };
}

function sameStructuralMeasurement(left: LactateMeasurementDraft, right: LactateMeasurementDraft): boolean {
  if (left.type !== right.type) return false;
  if (left.type !== "recovery" && left.type !== "rest_after") return true;
  return numeric(left.delay_minutes) === numeric(right.delay_minutes);
}

function hasStructuralMeasurement(items: LactateMeasurementDraft[], target: LactateMeasurementDraft): boolean {
  return items.some((item) => sameStructuralMeasurement(item, target));
}

function profileMatchesAnalysis(measurements: LactateMeasurementDraft[], analysis: MetaSoftAnalysis): boolean {
  const detectedStages = detectedMeasurements(analysis).filter((item) => item.type === "stage");
  if (!detectedStages.length) return true;
  const profileStages = measurements.filter((item) => (
    item.type === "stage"
    && item.source === "detected"
    && numeric(item.time_seconds) !== null
  ));
  const used = new Set<number>();
  return detectedStages.every((stage) => {
    const index = bestSavedStageMatch(profileStages, stage, used);
    if (index < 0) return false;
    used.add(index);
    return Math.abs(numeric(profileStages[index].time_seconds)! - numeric(stage.time_seconds)!) <= 2;
  });
}

function profileMeasurement(item: Record<string, unknown>): LactateMeasurementDraft {
  const allowed = new Set(["rest_before", "post_warmup", "stage", "recovery", "rest_after"]);
  const type = allowed.has(String(item.type)) ? item.type as LactateMeasurementDraft["type"] : "stage";
  return {
    type,
    speed: numeric(item.speed),
    lactate_mmol_l: numeric(item.lactate_mmol_l),
    enabled: item.enabled !== false,
    inclusion_touched: item.inclusion_touched === true,
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

function buildLactateTimelineItems(
  measurements: LactateMeasurementDraft[],
  includeDisabled = false,
): LactateTimelineItem[] {
  const times = new Map<number, number>();
  const ordered = measurements.flatMap((item, index) => {
    if (item.type === "recovery" || item.type === "rest_after" || numeric(item.speed) === null) return [];
    const knownTime = item.type === "rest_before" ? 0 : numeric(item.time_seconds);
    if (knownTime !== null) times.set(index, knownTime);
    return [index];
  });
  for (let cursor = 0; cursor < ordered.length;) {
    if (times.has(ordered[cursor])) {
      cursor += 1;
      continue;
    }
    const start = cursor;
    while (cursor < ordered.length && !times.has(ordered[cursor])) cursor += 1;
    const previous = start > 0 ? times.get(ordered[start - 1]) ?? 0 : 0;
    const next = cursor < ordered.length ? times.get(ordered[cursor]) ?? null : null;
    const step = next !== null && next > previous
      ? (next - previous) / (cursor - start + 1)
      : 60;
    for (let offset = 0; offset < cursor - start; offset += 1) {
      times.set(ordered[start + offset], previous + step * (offset + 1));
    }
  }
  const stageTimes = measurements.flatMap((item, index) => (
    item.type === "stage" && times.has(index) ? [times.get(index)!] : []
  ));
  const effortEnd = stageTimes.length
    ? Math.max(...stageTimes)
    : Math.max(0, ...times.values());
  let recoveryFallback = 0;
  return measurements.flatMap((item, index) => {
    const speed = numeric(item.speed);
    if ((!includeDisabled && item.enabled === false) || speed === null) return [];
    const isRecovery = item.type === "recovery" || item.type === "rest_after";
    const delaySeconds = isRecovery ? numeric(item.delay_minutes) : null;
    if (isRecovery && delaySeconds === null) recoveryFallback += 1;
    const timeSeconds = isRecovery
      ? effortEnd + (delaySeconds === null ? recoveryFallback * 60 : delaySeconds * 60)
      : times.get(index);
    return timeSeconds === undefined
      ? []
      : [{ item, index, label: measurementLabel(item, index), timeSeconds, speed }];
  }).sort((left, right) => left.timeSeconds - right.timeSeconds || left.index - right.index);
}

function lactateProtocolPoints(
  analysis: MetaSoftAnalysis,
  maxTime: number,
): { x: number[]; y: number[] } {
  const source = buildSpeedStepLinePoints(analysis);
  const x = [...source.x];
  const y = [...source.y];
  const lastTime = x[x.length - 1];
  if (lastTime !== undefined && maxTime > lastTime) {
    x.push(lastTime, maxTime);
    y.push(0, 0);
  }
  return { x, y };
}

function isLactateChartControlTarget(target: EventTarget | null): boolean {
  return target instanceof Element
    && Boolean(target.closest("button, input, select, .modebar, .legend, .marker-popover"));
}

function rebuildLactateThresholds(
  thresholds: LactateTestDraft["thresholds"],
  measurements: LactateMeasurementDraft[],
): LactateTestDraft["thresholds"] {
  const stages = buildLactateTimelineItems(measurements, true).filter(({ item, speed }) => (
    item.type === "stage" && speed > 0
  ));
  return Object.fromEntries((["sl1", "sl2"] as const).map((name) => {
    const threshold = thresholds[name];
    if (!threshold) return [name, threshold];
    const center = lactateThresholdTime(threshold, stages);
    const rebuilt = center === null ? null : buildLactateThresholdAtPosition(
      center,
      threshold.mode,
      lactateThresholdDuration(threshold),
      stages,
    );
    return [name, rebuilt ?? threshold];
  }));
}

function lactateThresholdShapes(
  thresholds: LactateTestDraft["thresholds"],
  stages: LactateTimelineItem[],
) {
  return (["sl1", "sl2"] as const).flatMap((name) => {
    const threshold = thresholds[name];
    if (!threshold) return [];
    const center = lactateThresholdTime(threshold, stages);
    if (center === null) return [];
    const color = name === "sl1" ? "#16e0c2" : "#ff8a00";
    const shapes: Array<Record<string, unknown>> = [{
      type: "line",
      x0: center,
      x1: center,
      y0: 0,
      y1: 1,
      yref: "paper",
      line: { color, width: 3, dash: "dash" },
    }];
    if (
      threshold.mode === "range"
      && numeric(threshold.window_start_seconds) !== null
      && numeric(threshold.window_end_seconds) !== null
    ) {
      const rawStart = numeric(threshold.window_start_seconds);
      const rawEnd = numeric(threshold.window_end_seconds);
      if (rawStart === null || rawEnd === null || rawStart === rawEnd) return shapes;
      shapes.unshift({
        type: "rect",
        x0: Math.min(rawStart, rawEnd),
        x1: Math.max(rawStart, rawEnd),
        y0: 0,
        y1: 1,
        yref: "paper",
        fillcolor: `${color}22`,
        line: { color: `${color}99`, width: 2 },
        layer: "below",
      });
    }
    return shapes;
  });
}

function lactateThresholdAnnotations(
  thresholds: LactateTestDraft["thresholds"],
  stages: LactateTimelineItem[],
) {
  return (["sl1", "sl2"] as const).flatMap((name) => {
    const threshold = thresholds[name];
    const center = threshold ? lactateThresholdTime(threshold, stages) : null;
    return center !== null ? [{
      x: center,
      y: 1,
      xref: "x",
      yref: "paper",
      text: name.toUpperCase(),
      showarrow: false,
      yanchor: "bottom",
      font: { color: name === "sl1" ? "#16e0c2" : "#ff8a00", size: 14 },
      bgcolor: "rgba(2,12,25,0.88)",
      bordercolor: name === "sl1" ? "#16e0c2" : "#ff8a00",
      borderpad: 4,
    }] : [];
  });
}

function lactateThresholdFromSaved(
  value: unknown,
  measurements: LactateMeasurementDraft[],
): LactateThresholdDraft | null {
  if (typeof value === "number") {
    const speed = numeric(measurements[value]?.speed);
    const timeSeconds = numeric(measurements[value]?.time_seconds);
    return speed !== null && speed > 0
      ? { mode: "point", speed_kmh: speed, ...(timeSeconds === null ? {} : { time_seconds: timeSeconds }) }
      : null;
  }
  if (!value || typeof value !== "object") return null;
  const saved = value as Record<string, unknown>;
  const indexedSpeed = typeof saved.measurement_index === "number"
    ? numeric(measurements[saved.measurement_index]?.speed)
    : null;
  const speed = numeric(saved.speed_kmh) ?? numeric(saved.speed) ?? indexedSpeed;
  if (speed === null || speed <= 0) return null;
  const indexedTime = typeof saved.measurement_index === "number"
    ? numeric(measurements[saved.measurement_index]?.time_seconds)
    : null;
  const timeSeconds = numeric(saved.time_seconds) ?? indexedTime;
  const timeFields = timeSeconds === null ? {} : { time_seconds: timeSeconds };
  const mode = saved.mode === "range" ? "range" : "point";
  if (mode === "point") return { mode, speed_kmh: speed, ...timeFields };
  const start = numeric(saved.speed_start_kmh) ?? numeric(saved.speed_start);
  const end = numeric(saved.speed_end_kmh) ?? numeric(saved.speed_end);
  const windowStart = numeric(saved.window_start_seconds);
  const windowEnd = numeric(saved.window_end_seconds);
  if ((windowStart === null || windowEnd === null || windowStart >= windowEnd)
      && (start === null || end === null || start >= end)) {
    return { mode: "point", speed_kmh: speed, ...timeFields };
  }
  return {
    mode,
    speed_kmh: start !== null && end !== null ? clamp(speed, start, end) : speed,
    ...(start === null ? {} : { speed_start_kmh: start }),
    ...(end === null ? {} : { speed_end_kmh: end }),
    ...timeFields,
    ...(windowStart === null ? {} : { window_start_seconds: windowStart }),
    ...(windowEnd === null ? {} : { window_end_seconds: windowEnd }),
  };
}

function lactateThresholdLabel(threshold?: LactateThresholdDraft | null): string {
  if (!threshold) return "Non place";
  const duration = lactateThresholdDuration(threshold);
  if (threshold.mode === "range" && duration !== null) {
    return `${formatSpeed(threshold.speed_kmh)} km/h / ${Math.round(duration)} s`;
  }
  return `${formatSpeed(threshold.speed_kmh)} km/h`;
}

function timelineTimeFromClientX(
  clientX: number,
  wrapper: HTMLDivElement | null,
  range: [number, number],
): number | null {
  const rect = plotAreaRect(wrapper);
  if (!rect || rect.width <= 0 || clientX < rect.left || clientX > rect.right) return null;
  return range[0] + ((clientX - rect.left) / rect.width) * (range[1] - range[0]);
}

function plotAreaRect(wrapper: HTMLDivElement | null): DOMRect | null {
  return wrapper?.querySelector<SVGRectElement>(".nsewdrag")?.getBoundingClientRect() ?? null;
}

function speedAtTimelineTime(timeSeconds: number, stages: LactateTimelineItem[]): number | null {
  if (!stages.length || timeSeconds < stages[0].timeSeconds || timeSeconds > stages[stages.length - 1].timeSeconds) {
    return null;
  }
  for (let index = 0; index < stages.length - 1; index += 1) {
    const left = stages[index];
    const right = stages[index + 1];
    if (timeSeconds < left.timeSeconds || timeSeconds > right.timeSeconds) continue;
    if (right.timeSeconds === left.timeSeconds) return left.speed;
    const ratio = (timeSeconds - left.timeSeconds) / (right.timeSeconds - left.timeSeconds);
    return left.speed + ratio * (right.speed - left.speed);
  }
  return stages[stages.length - 1].speed;
}

function timelineTimeAtSpeed(
  speed: number,
  stages: LactateTimelineItem[],
  preferredTime?: number,
): number | null {
  if (!stages.length) return null;
  const candidates: number[] = [];
  for (let index = 0; index < stages.length - 1; index += 1) {
    const left = stages[index];
    const right = stages[index + 1];
    if (speed < Math.min(left.speed, right.speed) || speed > Math.max(left.speed, right.speed)) continue;
    if (left.speed === right.speed) {
      if (speed === left.speed) {
        candidates.push(preferredTime === undefined
          ? (left.timeSeconds + right.timeSeconds) / 2
          : clamp(preferredTime, left.timeSeconds, right.timeSeconds));
      }
      continue;
    }
    const ratio = (speed - left.speed) / (right.speed - left.speed);
    candidates.push(left.timeSeconds + ratio * (right.timeSeconds - left.timeSeconds));
  }
  for (const stage of stages) {
    if (stage.speed === speed) candidates.push(stage.timeSeconds);
  }
  if (!candidates.length) {
    return stages.reduce((nearest, stage) => (
      Math.abs(stage.speed - speed) < Math.abs(nearest.speed - speed) ? stage : nearest
    )).timeSeconds;
  }
  return preferredTime === undefined
    ? candidates[0]
    : candidates.reduce((nearest, candidate) => (
      Math.abs(candidate - preferredTime) < Math.abs(nearest - preferredTime) ? candidate : nearest
    ));
}

function buildLactateThresholdAtPosition(
  rawTimeSeconds: number,
  mode: LactateThresholdMode,
  rangeDurationSeconds: number | null,
  stages: LactateTimelineItem[],
): LactateThresholdDraft | null {
  if (!stages.length) return null;
  const minimumTime = stages[0].timeSeconds;
  const maximumTime = stages[stages.length - 1].timeSeconds;
  const timeSeconds = clamp(rawTimeSeconds, minimumTime, maximumTime);
  const speed = speedAtTimelineTime(timeSeconds, stages);
  if (speed === null || speed <= 0) return null;
  if (mode === "point") {
    return { mode, speed_kmh: speed, time_seconds: timeSeconds };
  }
  if (
    rangeDurationSeconds === null
    || rangeDurationSeconds < 1
    || timeSeconds - rangeDurationSeconds / 2 < minimumTime
    || timeSeconds + rangeDurationSeconds / 2 > maximumTime
  ) return null;
  const windowStart = timeSeconds - rangeDurationSeconds / 2;
  const windowEnd = timeSeconds + rangeDurationSeconds / 2;
  return {
    mode,
    speed_kmh: speed,
    time_seconds: timeSeconds,
    window_start_seconds: windowStart,
    window_end_seconds: windowEnd,
  };
}

function lactateThresholdTime(
  threshold: LactateThresholdDraft,
  stages: LactateTimelineItem[],
): number | null {
  if (!stages.length) return null;
  const minimum = stages[0].timeSeconds;
  const maximum = stages[stages.length - 1].timeSeconds;
  const saved = numeric(threshold.time_seconds);
  if (saved !== null && saved >= minimum && saved <= maximum) return saved;
  return timelineTimeAtSpeed(threshold.speed_kmh, stages);
}

function lactateThresholdDuration(threshold: LactateThresholdDraft): number | null {
  if (
    threshold.mode !== "range"
    || typeof threshold.window_start_seconds !== "number"
    || typeof threshold.window_end_seconds !== "number"
  ) return null;
  return threshold.window_end_seconds - threshold.window_start_seconds;
}

function nearestLactateThresholdName(
  thresholds: LactateTestDraft["thresholds"],
  position: number,
  range: [number, number],
  wrapper: HTMLDivElement | null,
  stages: LactateTimelineItem[],
): LactateThresholdName | null {
  const rect = plotAreaRect(wrapper);
  if (!rect || rect.width <= 0) return null;
  const tolerance = ((range[1] - range[0]) / rect.width) * 18;
  let best: { name: LactateThresholdName; distance: number } | null = null;
  for (const name of ["sl1", "sl2"] as const) {
    const threshold = thresholds[name];
    if (!threshold) continue;
    const candidate = lactateThresholdTime(threshold, stages);
    if (candidate === null) continue;
    const distance = Math.abs(candidate - position);
    if (distance <= tolerance && (!best || distance < best.distance)) {
      best = { name, distance };
    }
  }
  return best?.name ?? null;
}

function numericInput(value: string): number | null {
  return numeric(value.replace(",", "."));
}

function validLactateRangeDuration(
  value: string,
  stages: LactateTimelineItem[],
  center: number | null,
): boolean {
  const duration = numericInput(value);
  if (duration === null || duration < 1 || !stages.length || center === null) return false;
  return center - duration / 2 >= stages[0].timeSeconds
    && center + duration / 2 <= stages[stages.length - 1].timeSeconds;
}

function formatSpeed(value: number): string {
  return value.toLocaleString("fr-FR", { maximumFractionDigits: 1 });
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(Math.max(value, minimum), maximum);
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
