import { memo, useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import type { MouseEvent as ReactMouseEvent } from "react";
import Plot from "react-plotly.js";
import { Maximize2, Minus, Plus, RotateCcw, X } from "lucide-react";
import {
  buildMarkerAnnotations,
  buildMarkerShapes,
  buildSpeedStepLineShapes,
  buildStaticAnnotations,
  buildTimeBandShapes,
} from "../lib/chartUtils";
import { MARKER_COLORS, MetaSoftGraphConfig, MetaSoftSeriesConfig } from "../lib/graphConfig";
import {
  axisLabel,
  axisTitle,
  averagePointsByTimeBlock,
  buildCursorAnnotations,
  buildCursorShapes,
  buildTickVals,
  centeredWindowBounds,
  clamp,
  cursorForMarkerDrag,
  defaultRangeFromValues,
  draggedMarkerBounds,
  durationToSeconds,
  isSeriesAvailable,
  markerModeLabel,
  nearestEventPoint,
  pointXValue,
  previewDraggedMarker,
  previousWindowBounds,
  sameDragPreview,
  sameMarkerTarget,
  scaledAxisRange,
  secondsToDuration,
  smoothSeries,
  timeFromClientX,
  xRangeFromRelayout,
  type MarkerDragPart,
  type MarkerDragPreview,
  type MarkerDragTarget,
} from "../lib/metasoftChartHelpers";
import { MARKER_NAMES, secondsToClock } from "../lib/markerUtils";
import type {
  ChartProcessingMode,
  DraftMarkers,
  MarkerMode,
  MetaSoftMarkerName,
  MetaSoftPoint,
} from "../types/metasoft";

const DEBUG_ZOOM = new URLSearchParams(window.location.search).get("debugZoom") === "1";
const MARKER_POPOVER_WIDTH = 336;
const MARKER_POPOVER_HEIGHT = 252;
const MARKER_MENU_WIDTH = 280;
const MARKER_MENU_HEIGHT = 174;
type ScaleMode = "common" | "series";

interface Props {
  analysis: import("../types/metasoft").MetaSoftAnalysis;
  graph: MetaSoftGraphConfig;
  markers: DraftMarkers;
  phaseFilter: string;
  smoothingSeconds: number;
  processingMode: ChartProcessingMode;
  showSpeedBands: boolean;
  timeXRange: [number, number] | null;
  timeZoomResetRevision: number;
  cursorPoint: MetaSoftPoint | null;
  fullscreen: boolean;
  height?: number;
  onFullscreenChange: (graphId: string, open: boolean) => void;
  onTimeXRangeChange?: (graphId: string, range: [number, number] | null) => void;
  onCursorPoint: (graphId: string, point: MetaSoftPoint | null) => void;
  onPlaceMarker: (
    marker: MetaSoftMarkerName,
    tSeconds: number,
    mode: MarkerMode,
    windowStartSeconds?: number | null,
    windowEndSeconds?: number | null,
  ) => void;
  onDeleteMarker: (marker: MetaSoftMarkerName) => void;
  onChangeMarkerWindowSeconds: (marker: MetaSoftMarkerName, durationSeconds: number) => void;
}

function MetaSoftChartComponent({
  analysis,
  graph,
  markers,
  phaseFilter,
  smoothingSeconds,
  processingMode,
  showSpeedBands,
  timeXRange,
  timeZoomResetRevision,
  cursorPoint,
  fullscreen,
  height = 260,
  onFullscreenChange,
  onTimeXRangeChange,
  onCursorPoint,
  onPlaceMarker,
  onDeleteMarker,
  onChangeMarkerWindowSeconds,
}: Props) {
  const [localXRange, setLocalXRange] = useState<[number, number] | null>(null);
  const [plotRevision, setPlotRevision] = useState(0);
  const [yScaleFactor, setYScaleFactor] = useState(1);
  const [scaleMode, setScaleMode] = useState<ScaleMode>("common");
  const [seriesScaleFactors, setSeriesScaleFactors] = useState<Record<string, number>>({});
  const [selectedScaleSeriesKey, setSelectedScaleSeriesKey] = useState<string>(graph.series[0]?.key ?? "");
  const [hiddenSeries, setHiddenSeries] = useState<Set<string>>(new Set());
  const modalTitleId = useId();
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);
  const availableSeries = useMemo(
    () => graph.series.filter((series) => isSeriesAvailable(analysis, graph, series)),
    [analysis, graph],
  );
  const visibleSeries = useMemo(
    () => availableSeries.filter((series) => !hiddenSeries.has(series.key)),
    [availableSeries, hiddenSeries],
  );
  const missingSeries = useMemo(
    () => graph.series.filter((series) => !isSeriesAvailable(analysis, graph, series)),
    [analysis, graph],
  );
  const points = useMemo(
    () => analysis.points.filter((point) => phaseFilter === "Tout" || point.phase === phaseFilter),
    [analysis.points, phaseFilter],
  );

  useEffect(() => {
    setLocalXRange(null);
    setPlotRevision((revision) => revision + 1);
  }, [analysis.file.filename, phaseFilter]);
  useEffect(() => {
    if (graph.kind === "time" && timeZoomResetRevision > 0) setPlotRevision((revision) => revision + 1);
  }, [graph.kind, timeZoomResetRevision]);
  useEffect(() => setHiddenSeries(new Set()), [analysis.file.filename, graph.id]);
  useEffect(() => {
    setYScaleFactor(1);
    setSeriesScaleFactors({});
    setScaleMode("common");
  }, [analysis.file.filename, graph.id]);
  useEffect(() => {
    if (!visibleSeries.some((series) => series.key === selectedScaleSeriesKey)) {
      setSelectedScaleSeriesKey(visibleSeries[0]?.key ?? "");
    }
  }, [selectedScaleSeriesKey, visibleSeries]);
  useEffect(() => {
    if (fullscreen) closeButtonRef.current?.focus();
  }, [fullscreen]);
  useEffect(() => {
    if (!fullscreen) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onFullscreenChange(graph.id, false);
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [fullscreen, graph.id, onFullscreenChange]);
  useEffect(() => {
    debugZoom("chart mounted", { graphId: graph.id, kind: graph.kind, timeZoomResetRevision, fullscreen });
    return () => debugZoom("chart unmounted", { graphId: graph.id, kind: graph.kind, timeZoomResetRevision, fullscreen });
  }, [fullscreen, graph.id, graph.kind, timeZoomResetRevision]);

  const handleXRangeChange = useCallback((range: [number, number] | null) => {
    if (graph.kind === "time" && onTimeXRangeChange) {
      onTimeXRangeChange(graph.id, range);
    } else {
      setLocalXRange(range);
    }
    if (range === null) setPlotRevision((revision) => revision + 1);
  }, [graph.id, graph.kind, onTimeXRangeChange]);
  const xRange = graph.kind === "time" ? timeXRange : localXRange;
  const changeYScale = useCallback((multiplier: number) => {
    if (scaleMode === "series") {
      setSeriesScaleFactors((current) => ({
        ...current,
        [selectedScaleSeriesKey]: clamp((current[selectedScaleSeriesKey] ?? 1) * multiplier, 0.35, 4),
      }));
    } else {
      setYScaleFactor((current) => clamp(current * multiplier, 0.35, 4));
    }
  }, [scaleMode, selectedScaleSeriesKey]);
  const resetYScale = useCallback(() => {
    if (scaleMode === "series") {
      setSeriesScaleFactors((current) => ({ ...current, [selectedScaleSeriesKey]: 1 }));
    } else {
      setYScaleFactor(1);
    }
  }, [scaleMode, selectedScaleSeriesKey]);

  const toggleSeries = useCallback((series: MetaSoftSeriesConfig) => {
    setHiddenSeries((current) => {
      const next = new Set(current);
      if (next.has(series.key)) {
        next.delete(series.key);
        return next;
      }
      if (availableSeries.length - next.size <= 1) return next;
      next.add(series.key);
      return next;
    });
  }, [availableSeries.length]);

  if (!availableSeries.length) {
    return (
      <section className="chart-card chart-card-empty">
        <div className="chart-title-row">
          <h2>{graph.title}</h2>
          <span className="status-warn">Absent XML</span>
        </div>
        <p>Aucune serie disponible pour ce graphe.</p>
      </section>
    );
  }

  const body = (height: number) => graph.source === "running_economy" ? (
    <RunningEconomyChart
      analysis={analysis}
      graph={graph}
      series={visibleSeries}
      height={height}
      plotRevision={plotRevision}
      xRange={xRange}
      yScaleFactor={yScaleFactor}
      onXRangeChange={handleXRangeChange}
    />
  ) : (
    <PointChartBody
      analysis={analysis}
      graph={graph}
      series={visibleSeries}
      points={points}
      markers={markers}
      height={height}
      plotRevision={plotRevision}
      plotResetKey={String(timeZoomResetRevision)}
      smoothingSeconds={smoothingSeconds}
      processingMode={processingMode}
      yScaleFactor={yScaleFactor}
      scaleMode={scaleMode}
      seriesScaleFactors={seriesScaleFactors}
      selectedScaleSeriesKey={selectedScaleSeriesKey}
      xRange={xRange}
      onXRangeChange={handleXRangeChange}
      showSpeedBands={showSpeedBands}
      cursorPoint={cursorPoint}
      onCursorPoint={onCursorPoint}
      onPlaceMarker={onPlaceMarker}
      onDeleteMarker={onDeleteMarker}
      onChangeMarkerWindowSeconds={onChangeMarkerWindowSeconds}
    />
  );

  return (
    <section className="chart-card">
      <div className="chart-title-row">
        <h2>{graph.title}</h2>
        <SeriesToggles series={availableSeries} hiddenSeries={hiddenSeries} onToggle={toggleSeries} />
        <ScaleControls
          series={visibleSeries}
          mode={scaleMode}
          selectedSeriesKey={selectedScaleSeriesKey}
          onModeChange={setScaleMode}
          onSelectedSeriesChange={setSelectedScaleSeriesKey}
          onZoomIn={() => changeYScale(0.8)}
          onZoomOut={() => changeYScale(1.25)}
          onAuto={resetYScale}
          onResetZoom={() => handleXRangeChange(null)}
          showResetZoom={xRange !== null}
        />
        <button
          type="button"
          onClick={() => onFullscreenChange(graph.id, true)}
          className="icon-button push-right"
          aria-label={`Ouvrir ${graph.title} en plein ecran`}
          title="Plein ecran"
        >
          <Maximize2 size={16} />
        </button>
      </div>
      {fullscreen ? <div className="chart-body" style={{ height }} /> : body(height)}
      {missingSeries.length > 0 && (
        <p className="missing-series">Absent XML : {missingSeries.map((series) => series.label).join(", ")}</p>
      )}
      {fullscreen && (
        <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby={modalTitleId}>
          <div className="modal-panel">
            <div className="modal-header">
              <h2 id={modalTitleId}>Plein ecran - {graph.title}</h2>
              <SeriesToggles series={availableSeries} hiddenSeries={hiddenSeries} onToggle={toggleSeries} />
              <ScaleControls
                series={visibleSeries}
                mode={scaleMode}
                selectedSeriesKey={selectedScaleSeriesKey}
                onModeChange={setScaleMode}
                onSelectedSeriesChange={setSelectedScaleSeriesKey}
                onZoomIn={() => changeYScale(0.8)}
                onZoomOut={() => changeYScale(1.25)}
                onAuto={resetYScale}
                onResetZoom={() => handleXRangeChange(null)}
                showResetZoom={xRange !== null}
              />
              <button
                type="button"
                ref={closeButtonRef}
                className="icon-button push-right"
                onClick={() => onFullscreenChange(graph.id, false)}
                aria-label="Fermer le plein ecran"
                title="Fermer"
              >
                <X size={18} />
              </button>
            </div>
            {body(Math.min(760, Math.max(420, window.innerHeight - 170)))}
          </div>
        </div>
      )}
    </section>
  );
}

export const MetaSoftChart = memo(MetaSoftChartComponent);

function plotlyAxisId(index: number): string {
  return index === 0 ? "y" : `y${index + 1}`;
}

function plotlyLayoutAxisKey(index: number): string {
  return index === 0 ? "yaxis" : `yaxis${index + 1}`;
}

function ScaleControls({
  series,
  mode,
  selectedSeriesKey,
  onModeChange,
  onSelectedSeriesChange,
  onZoomIn,
  onZoomOut,
  onAuto,
  onResetZoom,
  showResetZoom,
}: {
  series: MetaSoftSeriesConfig[];
  mode: ScaleMode;
  selectedSeriesKey: string;
  onModeChange: (mode: ScaleMode) => void;
  onSelectedSeriesChange: (key: string) => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onAuto: () => void;
  onResetZoom: () => void;
  showResetZoom: boolean;
}) {
  return (
    <div className="scale-controls" aria-label="Regler l'echelle verticale">
      {series.length > 1 && (
        <button
          type="button"
          onClick={() => onModeChange(mode === "common" ? "series" : "common")}
          title="Basculer entre une echelle commune et une echelle par courbe"
        >
          {mode === "series" ? "Par courbe" : "Commune"}
        </button>
      )}
      {mode === "series" && series.length > 1 && (
        <select
          aria-label="Courbe dont l'echelle est affichee et ajustee"
          value={selectedSeriesKey}
          onChange={(event) => onSelectedSeriesChange(event.target.value)}
        >
          {series.map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}
        </select>
      )}
      <button type="button" onClick={onZoomOut} title="Elargir l'echelle verticale" aria-label="Elargir l'echelle verticale">
        <Minus size={14} />
      </button>
      <button type="button" onClick={onAuto} title="Echelle automatique sur la zone visible">Auto</button>
      <button type="button" onClick={onZoomIn} title="Resserrer l'echelle verticale" aria-label="Resserrer l'echelle verticale">
        <Plus size={14} />
      </button>
      {showResetZoom && (
        <button type="button" className="zoom-reset-button" onClick={onResetZoom} title="Reinitialiser le zoom temporel">
          <RotateCcw size={14} /> Reinitialiser
        </button>
      )}
    </div>
  );
}

function SeriesToggles({
  series,
  hiddenSeries,
  onToggle,
}: {
  series: MetaSoftSeriesConfig[];
  hiddenSeries: Set<string>;
  onToggle: (series: MetaSoftSeriesConfig) => void;
}) {
  return (
    <div className="series-toggles">
      {series.map((item) => (
        <button
          key={item.key}
          type="button"
          onClick={() => onToggle(item)}
          className={hiddenSeries.has(item.key) ? "series-toggle muted" : "series-toggle"}
          aria-pressed={!hiddenSeries.has(item.key)}
        >
          <span style={{ backgroundColor: item.color }} />
          {item.label}
        </button>
      ))}
    </div>
  );
}

function RunningEconomyChart({
  analysis,
  graph,
  series,
  height,
  plotRevision,
  xRange,
  yScaleFactor,
  onXRangeChange,
}: {
  analysis: import("../types/metasoft").MetaSoftAnalysis;
  graph: MetaSoftGraphConfig;
  series: MetaSoftSeriesConfig[];
  height: number;
  plotRevision: number;
  xRange: [number, number] | null;
  yScaleFactor: number;
  onXRangeChange: (range: [number, number] | null) => void;
}) {
  const rows = analysis.computed.running_economy ?? [];
  const visibleValues = rows.filter((row) => (
    !xRange || (row.stage_index >= xRange[0] && row.stage_index <= xRange[1])
  )).map((row) => row.value_j_kg_m);
  const yRange = scaledAxisRange(visibleValues, yScaleFactor);
  const data = series.map((seriesItem) => ({
    type: "scatter",
    mode: "lines+markers",
    name: seriesItem.label,
    x: rows.map((row) => row.stage_index),
    y: rows.map((row) => row.value_j_kg_m),
    customdata: rows.map((row) => [row.speed_kmh, row.point_count]),
    line: { color: seriesItem.color, width: 1.5 },
    marker: { color: seriesItem.color, size: 7 },
    hovertemplate: "Palier %{x}<br>EC %{y}<br>Vitesse %{customdata[0]} km/h<extra></extra>",
  }));
  return (
    <Plot
      data={data}
      layout={{
        autosize: true,
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        margin: { l: 48, r: 18, t: 16, b: 42 },
        font: { color: "rgba(226,232,240,0.78)", size: 10 },
        dragmode: "zoom",
        showlegend: false,
        xaxis: {
          range: xRange ?? undefined,
          title: graph.xAxis.label,
          gridcolor: "rgba(255,255,255,0.055)",
          dtick: 1,
        },
        yaxis: {
          title: "J/kg/m",
          range: yRange,
          gridcolor: "rgba(255,255,255,0.055)",
        },
      }}
      config={{ responsive: true, displayModeBar: false, doubleClick: false }}
      revision={plotRevision}
      style={{ width: "100%", height }}
      useResizeHandler
      onRelayout={(event: Readonly<Record<string, unknown>>) => {
        const nextRange = xRangeFromRelayout(event);
        if (nextRange !== undefined) onXRangeChange(nextRange);
      }}
    />
  );
}

function PointChartBody({
  analysis,
  graph,
  series,
  points,
  markers,
  height,
  plotRevision,
  plotResetKey,
  smoothingSeconds,
  processingMode,
  yScaleFactor,
  scaleMode,
  seriesScaleFactors,
  selectedScaleSeriesKey,
  xRange,
  onXRangeChange,
  showSpeedBands,
  cursorPoint,
  onCursorPoint,
  onPlaceMarker,
  onDeleteMarker,
  onChangeMarkerWindowSeconds,
}: {
  analysis: import("../types/metasoft").MetaSoftAnalysis;
  graph: MetaSoftGraphConfig;
  series: MetaSoftSeriesConfig[];
  points: MetaSoftPoint[];
  markers: DraftMarkers;
  height: number;
  plotRevision: number;
  plotResetKey: string;
  smoothingSeconds: number;
  processingMode: ChartProcessingMode;
  yScaleFactor: number;
  scaleMode: ScaleMode;
  seriesScaleFactors: Record<string, number>;
  selectedScaleSeriesKey: string;
  xRange: [number, number] | null;
  onXRangeChange: (range: [number, number] | null) => void;
  showSpeedBands: boolean;
  cursorPoint: MetaSoftPoint | null;
  onCursorPoint: (graphId: string, point: MetaSoftPoint | null) => void;
  onPlaceMarker: (
    marker: MetaSoftMarkerName,
    tSeconds: number,
    mode: MarkerMode,
    windowStartSeconds?: number | null,
    windowEndSeconds?: number | null,
  ) => void;
  onDeleteMarker: (marker: MetaSoftMarkerName) => void;
  onChangeMarkerWindowSeconds: (marker: MetaSoftMarkerName, durationSeconds: number) => void;
}) {
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const clickTimerRef = useRef<number | null>(null);
  const clickBlockUntilRef = useRef(0);
  const suppressClickRef = useRef(false);
  const dragFrameRef = useRef<number | null>(null);
  const dragPreviewRef = useRef<MarkerDragPreview | null>(null);
  const pendingDragPreviewRef = useRef<MarkerDragPreview | null>(null);
  const markerHoverRef = useRef<MarkerDragTarget | null>(null);
  const [proposal, setProposal] = useState<{
    left: number;
    top: number;
    tSeconds: number;
    mode: MarkerMode;
    rangeDuration: string;
    previousDuration: string;
    opensBelow: boolean;
  } | null>(null);
  const [markerMenu, setMarkerMenu] = useState<{
    left: number;
    top: number;
    marker: MetaSoftMarkerName;
    duration: string;
    opensBelow: boolean;
  } | null>(null);
  const [markerHover, setMarkerHover] = useState<MarkerDragTarget | null>(null);
  const [dragPreview, setDragPreview] = useState<MarkerDragPreview | null>(null);
  const canEditTimeMarkers = graph.kind === "time";
  const processedPoints = useMemo(
    () => processingMode === "blocks" ? averagePointsByTimeBlock(points, 5) : points,
    [points, processingMode],
  );
  const chartPoints = useMemo(
    () => processedPoints.filter((point) => pointXValue(point, graph) !== null),
    [graph, processedPoints],
  );
  const x = useMemo(() => chartPoints.map((point) => pointXValue(point, graph)), [chartPoints, graph]);
  const maxTime = useMemo(
    () => Math.max(...analysis.points.map((point) => point.t_seconds ?? 0), 0),
    [analysis.points],
  );
  const defaultRange = useMemo(
    () => defaultRangeFromValues(x, graph.kind === "time" ? maxTime : 1),
    [graph.kind, maxTime, x],
  );
  const tickVals = useMemo(() => graph.kind === "time" ? buildTickVals(defaultRange) : [], [defaultRange, graph.kind]);
  const tickText = useMemo(() => tickVals.map(secondsToClock), [tickVals]);
  const effectiveRange = xRange && xRange[0] >= defaultRange[0] && xRange[1] <= defaultRange[1] ? xRange : null;
  const visibleMarkers = useMemo(() => canEditTimeMarkers && dragPreview
    ? { ...markers, [dragPreview.marker]: previewDraggedMarker(markers[dragPreview.marker], dragPreview, maxTime) }
    : markers, [canEditTimeMarkers, dragPreview, markers, maxTime]);
  const plotMargins = useMemo(
    () => ({ l: 44, r: graph.series.some((item) => item.axis === "y2") ? 42 : 16, t: 14, b: 42 }),
    [graph.series],
  );
  const staticShapes = useMemo(
    () => canEditTimeMarkers ? buildTimeBandShapes(analysis) : [],
    [analysis, canEditTimeMarkers],
  );
  const staticAnnotations = useMemo(
    () => canEditTimeMarkers ? buildStaticAnnotations(analysis) : [],
    [analysis, canEditTimeMarkers],
  );
  const markerShapes = useMemo(
    () => canEditTimeMarkers ? buildMarkerShapes(visibleMarkers) : [],
    [canEditTimeMarkers, visibleMarkers],
  );
  const markerAnnotations = useMemo(
    () => canEditTimeMarkers ? buildMarkerAnnotations(visibleMarkers) : [],
    [canEditTimeMarkers, visibleMarkers],
  );
  const cursorShapes = useMemo(
    () => buildCursorShapes(graph, cursorPoint),
    [cursorPoint, graph],
  );
  const cursorAnnotations = useMemo(
    () => buildCursorAnnotations(graph, series, cursorPoint),
    [cursorPoint, graph, series],
  );
  const speedLineShapes = useMemo(
    () => graph.kind === "time" && showSpeedBands ? buildSpeedStepLineShapes(analysis) : [],
    [analysis, graph.kind, showSpeedBands],
  );
  const shapes = useMemo(
    () => canEditTimeMarkers ? [...staticShapes, ...speedLineShapes, ...markerShapes, ...cursorShapes] : [],
    [canEditTimeMarkers, cursorShapes, markerShapes, speedLineShapes, staticShapes],
  );
  const annotations = useMemo(
    () => canEditTimeMarkers ? [...staticAnnotations, ...markerAnnotations, ...cursorAnnotations] : [],
    [canEditTimeMarkers, cursorAnnotations, markerAnnotations, staticAnnotations],
  );
  const speedHoverText = useMemo(
    () => chartPoints.map((point) => (
      typeof point.values.speed_kmh === "number"
        ? `${point.values.speed_kmh.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} km/h`
        : "n/a"
    )),
    [chartPoints],
  );
  const renderedValues = useMemo(() => Object.fromEntries(series.map((seriesItem) => {
    const rawY = chartPoints.map((point) => point.values[seriesItem.key as keyof MetaSoftPoint["values"]]);
    const shouldSmooth = processingMode === "smooth" && graph.kind === "time" && seriesItem.smoothable;
    return [seriesItem.key, shouldSmooth ? smoothSeries(x, rawY, smoothingSeconds) : rawY];
  })), [chartPoints, graph.kind, processingMode, series, smoothingSeconds, x]);
  const data = useMemo(() => series.map((seriesItem, seriesIndex) => {
    return {
      type: "scatter",
      mode: graph.kind === "scatter" ? "markers" : "lines",
      name: seriesItem.label,
      x,
      y: renderedValues[seriesItem.key],
      yaxis: scaleMode === "series" ? plotlyAxisId(seriesIndex) : seriesItem.axis,
      customdata: chartPoints.map((point) => point.index),
      text: speedHoverText,
      line: { color: seriesItem.color, width: 0.8 },
      marker: { color: seriesItem.color, size: graph.kind === "scatter" ? 5 : 4 },
      hoverinfo: graph.kind === "time" ? "none" : undefined,
      hovertemplate: graph.kind === "time"
        ? undefined
        : `${seriesItem.unit === "bpm" ? "%{y:.0f}" : "%{y}"}<br>Vitesse %{text}<extra>${seriesItem.label}</extra>`,
      connectgaps: false,
    };
  }), [chartPoints, graph.kind, renderedValues, scaleMode, series, speedHoverText, x]);
  const visibleXRange = effectiveRange ?? defaultRange;
  const axisRange = useCallback((axis: "y" | "y2") => scaledAxisRange(
    series
      .filter((item) => (item.axis ?? "y") === axis)
      .flatMap((item) => (renderedValues[item.key] ?? []).filter((_value, index) => {
        const xValue = x[index];
        return typeof xValue === "number" && xValue >= visibleXRange[0] && xValue <= visibleXRange[1];
      })),
    yScaleFactor,
  ), [renderedValues, series, visibleXRange, x, yScaleFactor]);
  const yRange = axisRange("y");
  const y2Range = axisRange("y2");
  const separateAxes = useMemo(() => Object.fromEntries(series.map((seriesItem, seriesIndex) => {
    const selected = seriesItem.key === selectedScaleSeriesKey;
    const range = scaledAxisRange(
      (renderedValues[seriesItem.key] ?? []).filter((_value, index) => {
        const xValue = x[index];
        return typeof xValue === "number" && xValue >= visibleXRange[0] && xValue <= visibleXRange[1];
      }),
      seriesScaleFactors[seriesItem.key] ?? 1,
    );
    return [plotlyLayoutAxisKey(seriesIndex), {
      range,
      ...(seriesIndex ? { overlaying: "y" } : {}),
      side: selected && seriesIndex ? "right" : "left",
      showticklabels: selected,
      showgrid: selected,
      title: selected ? { text: `${seriesItem.label} (${seriesItem.unit})`, font: { size: 10, color: seriesItem.color } } : undefined,
      tickfont: { color: seriesItem.color },
      gridcolor: selected ? "rgba(255,255,255,0.055)" : "rgba(255,255,255,0)",
      linecolor: selected ? seriesItem.color : "rgba(255,255,255,0)",
      zerolinecolor: "rgba(255,255,255,0.08)",
    }];
  })), [renderedValues, selectedScaleSeriesKey, series, seriesScaleFactors, visibleXRange, x]);
  const layout = useMemo(() => ({
    autosize: true,
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    margin: plotMargins,
    font: { color: "rgba(226,232,240,0.78)", size: 10 },
    hovermode: graph.kind === "time" ? "x unified" : "closest",
    dragmode: "zoom",
    showlegend: false,
    shapes,
    annotations,
    xaxis: {
      range: effectiveRange ?? defaultRange,
      ...(graph.kind === "time" ? {
        tickvals: tickVals,
        ticktext: tickText,
      } : {}),
      gridcolor: "rgba(255,255,255,0.055)",
      linecolor: "rgba(255,255,255,0.18)",
      zerolinecolor: "rgba(255,255,255,0.08)",
      title: { text: axisTitle(graph.xAxis), font: { size: 10, color: "rgba(226,232,240,0.65)" } },
    },
    ...(scaleMode === "series" ? separateAxes : { yaxis: {
      range: yRange,
      title: { text: axisLabel(series, "y"), font: { size: 10, color: "rgba(226,232,240,0.65)" } },
      gridcolor: "rgba(255,255,255,0.055)",
      linecolor: "rgba(255,255,255,0.18)",
      zerolinecolor: "rgba(255,255,255,0.08)",
    }, yaxis2: {
      range: y2Range,
      overlaying: "y",
      side: "right",
      title: { text: axisLabel(series, "y2"), font: { size: 10, color: "rgba(226,232,240,0.65)" } },
      gridcolor: "rgba(255,255,255,0)",
      linecolor: "rgba(255,255,255,0.18)",
      zerolinecolor: "rgba(255,255,255,0.08)",
    } }),
  }), [annotations, defaultRange, effectiveRange, graph.kind, graph.xAxis, plotMargins, scaleMode, separateAxes, series, shapes, tickText, tickVals, y2Range, yRange]);
  const config = useMemo(() => ({
    responsive: true,
    displayModeBar: false,
    scrollZoom: false,
    doubleClick: false,
    editable: false,
  }), []);

  useEffect(() => () => {
    if (clickTimerRef.current !== null) window.clearTimeout(clickTimerRef.current);
    if (dragFrameRef.current !== null) window.cancelAnimationFrame(dragFrameRef.current);
  }, []);

  useEffect(() => {
    dragPreviewRef.current = dragPreview;
  }, [dragPreview]);

  const clearPendingClick = useCallback(() => {
    if (clickTimerRef.current === null) return;
    window.clearTimeout(clickTimerRef.current);
    clickTimerRef.current = null;
  }, []);

  const updateMarkerHover = useCallback((target: MarkerDragTarget | null) => {
    if (sameMarkerTarget(markerHoverRef.current, target)) return;
    markerHoverRef.current = target;
    setMarkerHover(target);
  }, []);

  const scheduleDragPreview = useCallback((next: MarkerDragPreview) => {
    const current = pendingDragPreviewRef.current ?? dragPreviewRef.current;
    if (sameDragPreview(current, next)) return;
    pendingDragPreviewRef.current = next;
    if (dragFrameRef.current !== null) return;
    dragFrameRef.current = window.requestAnimationFrame(() => {
      dragFrameRef.current = null;
      const pending = pendingDragPreviewRef.current;
      pendingDragPreviewRef.current = null;
      if (!pending) return;
      setDragPreview((currentPreview) => {
        if (sameDragPreview(currentPreview, pending)) return currentPreview;
        dragPreviewRef.current = pending;
        return pending;
      });
    });
  }, []);

  const clearPendingDragFrame = useCallback(() => {
    if (dragFrameRef.current !== null) window.cancelAnimationFrame(dragFrameRef.current);
    dragFrameRef.current = null;
    pendingDragPreviewRef.current = null;
  }, []);

  const openMarkerProposal = useCallback((event: Readonly<{ event?: MouseEvent; points?: Array<{ x?: unknown }> }>) => {
    if (!canEditTimeMarkers) return;
    if (suppressClickRef.current || window.performance.now() < clickBlockUntilRef.current) {
      suppressClickRef.current = false;
      return;
    }
    const mouseEvent = event.event;
    const bounds = wrapperRef.current?.getBoundingClientRect();
    if (!mouseEvent || !bounds || mouseEvent.detail > 1) {
      if (mouseEvent?.detail && mouseEvent.detail > 1) clickBlockUntilRef.current = window.performance.now() + 450;
      clearPendingClick();
      return;
    }
    const clickedSeconds = timeFromClientX(mouseEvent.clientX, wrapperRef.current, effectiveRange ?? defaultRange, plotMargins);
    if (clickedSeconds === null) return;
    const tSeconds = processingMode === "blocks"
      ? Math.floor(clickedSeconds / 5) * 5 + 2.5
      : clickedSeconds;
    clearPendingClick();
    clickTimerRef.current = window.setTimeout(() => {
      clickTimerRef.current = null;
      const popoverWidth = Math.min(MARKER_POPOVER_WIDTH, Math.max(1, window.innerWidth - 24));
      const opensBelow = mouseEvent.clientY < MARKER_POPOVER_HEIGHT + 16;
      setMarkerMenu(null);
      setProposal({
        left: clamp(mouseEvent.clientX, popoverWidth / 2 + 12, window.innerWidth - popoverWidth / 2 - 12),
        top: opensBelow ? mouseEvent.clientY + 10 : mouseEvent.clientY - 10,
        tSeconds: clamp(tSeconds, 0, maxTime),
        mode: processingMode === "blocks" ? "range" : "point",
        rangeDuration: processingMode === "blocks" ? "0:05" : "4:00",
        previousDuration: "0:10",
        opensBelow,
      });
    }, 320);
  }, [canEditTimeMarkers, clearPendingClick, defaultRange, effectiveRange, maxTime, plotMargins, processingMode]);

  const handleContextMenu = useCallback((event: ReactMouseEvent<HTMLDivElement>) => {
    if (!canEditTimeMarkers) return;
    const target = nearestMarkerTargetFromMouse(event, wrapperRef.current, markers, effectiveRange ?? defaultRange, plotMargins);
    if (!target) return;
    event.preventDefault();
    const bounds = wrapperRef.current?.getBoundingClientRect();
    if (!bounds) return;
    const marker = markers[target.marker];
    const menuWidth = Math.min(MARKER_MENU_WIDTH, Math.max(1, window.innerWidth - 24));
    const opensBelow = event.clientY < MARKER_MENU_HEIGHT + 16;
    const duration = marker.mode !== "point" && marker.window_start_seconds !== null && marker.window_end_seconds !== null
      ? secondsToDuration(marker.window_end_seconds - marker.window_start_seconds)
      : "";
    setProposal(null);
    setMarkerMenu({
      marker: target.marker,
      duration,
      left: clamp(event.clientX, menuWidth / 2 + 12, window.innerWidth - menuWidth / 2 - 12),
      top: opensBelow ? event.clientY + 10 : event.clientY - 10,
      opensBelow,
    });
  }, [canEditTimeMarkers, defaultRange, effectiveRange, markers, plotMargins]);

  const handleMouseDown = useCallback((event: ReactMouseEvent<HTMLDivElement>) => {
    if (!canEditTimeMarkers) return;
    if (event.button !== 0) return;
    setMarkerMenu(null);
    const target = nearestMarkerTargetFromMouse(event, wrapperRef.current, markers, effectiveRange ?? defaultRange, plotMargins);
    const xSeconds = target
      ? timeFromClientX(event.clientX, wrapperRef.current, effectiveRange ?? defaultRange, plotMargins)
      : null;
    if (!target || xSeconds === null) return;
    event.preventDefault();
    suppressClickRef.current = true;
    clearPendingClick();
    clearPendingDragFrame();
    setProposal(null);
    const nextDrag = { ...target, xSeconds: clamp(xSeconds, 0, maxTime) };
    dragPreviewRef.current = nextDrag;
    setDragPreview(nextDrag);
  }, [canEditTimeMarkers, clearPendingClick, clearPendingDragFrame, defaultRange, effectiveRange, markers, maxTime, plotMargins]);

  const handleMouseMove = useCallback((event: ReactMouseEvent<HTMLDivElement>) => {
    if (!canEditTimeMarkers) return;
    const currentDrag = dragPreviewRef.current;
    if (currentDrag) {
      const xSeconds = timeFromClientX(event.clientX, wrapperRef.current, effectiveRange ?? defaultRange, plotMargins);
      if (xSeconds !== null) scheduleDragPreview({ ...currentDrag, xSeconds: clamp(xSeconds, 0, maxTime) });
      return;
    }
    updateMarkerHover(
      nearestMarkerTargetFromMouse(event, wrapperRef.current, markers, effectiveRange ?? defaultRange, plotMargins),
    );
  }, [canEditTimeMarkers, defaultRange, effectiveRange, markers, maxTime, plotMargins, scheduleDragPreview, updateMarkerHover]);

  const handleMouseUp = useCallback((event?: ReactMouseEvent<HTMLDivElement>) => {
    if (!canEditTimeMarkers) return;
    let finalDrag = pendingDragPreviewRef.current ?? dragPreviewRef.current;
    if (!finalDrag) return;
    const xSeconds = event
      ? timeFromClientX(event.clientX, wrapperRef.current, effectiveRange ?? defaultRange, plotMargins)
      : null;
    if (xSeconds !== null) finalDrag = { ...finalDrag, xSeconds: clamp(xSeconds, 0, maxTime) };
    clearPendingDragFrame();
    const next = draggedMarkerBounds(markers[finalDrag.marker], finalDrag.part, finalDrag.xSeconds, maxTime);
    onPlaceMarker(finalDrag.marker, next.tSeconds, next.mode, next.windowStart, next.windowEnd);
    dragPreviewRef.current = null;
    setDragPreview(null);
  }, [canEditTimeMarkers, clearPendingDragFrame, defaultRange, effectiveRange, markers, maxTime, onPlaceMarker, plotMargins]);

  const placeProposalMarker = useCallback((marker: MetaSoftMarkerName) => {
    if (!proposal) return;
    if (proposal.mode === "point") {
      onPlaceMarker(marker, proposal.tSeconds, "point", null, null);
      setProposal(null);
      return;
    }
    const rangeSeconds = durationToSeconds(
      proposal.mode === "previous" ? proposal.previousDuration : proposal.rangeDuration,
    );
    if (rangeSeconds === null) return;
    const [windowStart, windowEnd] = proposal.mode === "previous"
      ? previousWindowBounds(proposal.tSeconds, rangeSeconds)
      : centeredWindowBounds(proposal.tSeconds, rangeSeconds, maxTime);
    onPlaceMarker(marker, proposal.tSeconds, proposal.mode, windowStart, windowEnd);
    setProposal(null);
  }, [maxTime, onPlaceMarker, proposal]);
  const handleHover = useCallback((event: Readonly<{ points?: Array<{ customdata?: unknown; x?: unknown }> }>) => {
    onCursorPoint(graph.id, nearestEventPoint(chartPoints, event, graph));
  }, [chartPoints, graph, onCursorPoint]);
  const handleUnhover = useCallback(() => onCursorPoint(graph.id, null), [graph.id, onCursorPoint]);
  const handleRelayout = useCallback((event: Readonly<Record<string, unknown>>) => {
    const nextRange = xRangeFromRelayout(event);
    debugZoom("plot relayout", {
      graphId: graph.id,
      nextRange,
      xRange,
      effectiveRange,
      event,
    });
    if (nextRange !== undefined) onXRangeChange(nextRange);
  }, [effectiveRange, graph.id, onXRangeChange, xRange]);

  return (
    <div
      ref={wrapperRef}
      className="chart-body"
      style={{ height, cursor: cursorForMarkerDrag(dragPreview?.part ?? markerHover?.part ?? null, Boolean(dragPreview)) }}
      onContextMenu={handleContextMenu}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={(event) => {
        updateMarkerHover(null);
        handleMouseUp(event);
      }}
      onWheel={(event) => event.preventDefault()}
    >
      <Plot
        key={`${graph.id}-${plotResetKey}`}
        data={data}
        layout={layout}
        config={config}
        revision={plotRevision}
        style={{ width: "100%", height }}
        useResizeHandler
        onClick={canEditTimeMarkers ? openMarkerProposal : undefined}
        onRelayout={handleRelayout}
        onHover={handleHover}
        onUnhover={handleUnhover}
      />
      {proposal && (
        <div
          className={proposal.opensBelow ? "marker-popover marker-popover-below" : "marker-popover"}
          style={{ left: proposal.left, top: proposal.top }}
          onClick={(event) => event.stopPropagation()}
          onContextMenu={(event) => event.stopPropagation()}
          onMouseDown={(event) => event.stopPropagation()}
          onMouseMove={(event) => event.stopPropagation()}
          onMouseUp={(event) => event.stopPropagation()}
        >
          <div className="popover-head">
            <div>
              <p>Placer un seuil</p>
              <span>{secondsToClock(proposal.tSeconds)}</span>
            </div>
            <button type="button" onClick={() => setProposal(null)} aria-label="Fermer">
              <X size={16} />
            </button>
          </div>
          <div className="segmented">
            {(["point", "range", "previous"] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                onClick={() => setProposal({ ...proposal, mode })}
                className={proposal.mode === mode ? "active" : ""}
                aria-pressed={proposal.mode === mode}
              >
                {markerModeLabel(mode)}
              </button>
            ))}
          </div>
          <p className="popover-help">{markerModeHelp(proposal.mode)}</p>
          {proposal.mode !== "point" && (
            <label className="field small-field">
              Duree
              <input
                value={proposal.mode === "previous" ? proposal.previousDuration : proposal.rangeDuration}
                onChange={(event) => setProposal({
                  ...proposal,
                  [proposal.mode === "previous" ? "previousDuration" : "rangeDuration"]: event.target.value,
                })}
                onBlur={() => {
                  const key = proposal.mode === "previous" ? "previousDuration" : "rangeDuration";
                  const seconds = durationToSeconds(proposal[key]);
                  if (seconds !== null) setProposal({ ...proposal, [key]: secondsToDuration(seconds) });
                }}
                placeholder={proposal.mode === "previous" ? "0:10" : "4:00"}
              />
            </label>
          )}
          <div className="marker-choice-grid">
            {MARKER_NAMES.map((marker) => (
              <button
                key={marker}
                type="button"
                onClick={() => placeProposalMarker(marker)}
                disabled={proposal.mode !== "point" && durationToSeconds(
                  proposal.mode === "previous" ? proposal.previousDuration : proposal.rangeDuration,
                ) === null}
                style={{ borderColor: `${MARKER_COLORS[marker]}70`, color: MARKER_COLORS[marker] }}
              >
                {marker === "VO2_max" ? "VO2max" : marker}
              </button>
            ))}
          </div>
        </div>
      )}
      {markerMenu && (
        <div
          className={`marker-popover marker-action-menu${markerMenu.opensBelow ? " marker-popover-below" : ""}`}
          style={{ left: markerMenu.left, top: markerMenu.top }}
          role="dialog"
          aria-label={`Modifier ${markerDisplayName(markerMenu.marker)}`}
          onClick={(event) => event.stopPropagation()}
          onContextMenu={(event) => event.preventDefault()}
          onMouseDown={(event) => event.stopPropagation()}
          onMouseUp={(event) => event.stopPropagation()}
        >
          <div className="popover-head">
            <div>
              <p>Marqueur</p>
              <strong>{markerDisplayName(markerMenu.marker)}</strong>
            </div>
            <button type="button" onClick={() => setMarkerMenu(null)} aria-label="Fermer">
              <X size={16} />
            </button>
          </div>
          {markers[markerMenu.marker].mode !== "point" && (
            <label className="field small-field">
              Longueur de la fenetre
              <input
                value={markerMenu.duration}
                onChange={(event) => setMarkerMenu({ ...markerMenu, duration: event.target.value })}
                placeholder="0:20"
              />
            </label>
          )}
          <div className="marker-menu-actions">
            {markers[markerMenu.marker].mode !== "point" && (
              <button
                type="button"
                className="secondary-button"
                disabled={durationToSeconds(markerMenu.duration) === null}
                onClick={() => {
                  const seconds = durationToSeconds(markerMenu.duration);
                  if (seconds === null) return;
                  onChangeMarkerWindowSeconds(markerMenu.marker, seconds);
                  setMarkerMenu(null);
                }}
              >
                Modifier la longueur
              </button>
            )}
            <button
              type="button"
              className="danger-button"
              onClick={() => {
                onDeleteMarker(markerMenu.marker);
                setMarkerMenu(null);
              }}
            >
              Supprimer
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function nearestMarkerTargetFromMouse(
  event: ReactMouseEvent<HTMLDivElement>,
  wrapper: HTMLDivElement | null,
  markers: DraftMarkers,
  range: [number, number],
  margin: { l: number; r: number },
): MarkerDragTarget | null {
  if (!wrapper || !range[1]) return null;
  const bounds = wrapper.getBoundingClientRect();
  const plotLeft = bounds.left + margin.l;
  const plotRight = bounds.right - margin.r;
  const plotWidth = plotRight - plotLeft;
  if (plotWidth <= 0 || event.clientX < plotLeft || event.clientX > plotRight) return null;

  const xSeconds = range[0] + ((event.clientX - plotLeft) / plotWidth) * (range[1] - range[0]);
  const thresholdSeconds = Math.max(10, ((range[1] - range[0]) / plotWidth) * 12);
  return MARKER_NAMES.reduce<{ target: MarkerDragTarget; distance: number } | null>((best, marker) => {
    const item = markers[marker];
    const candidates: Array<{ part: MarkerDragPart; seconds: number | null }> = [
      { part: "center", seconds: item.t_seconds },
      { part: "start", seconds: item.mode !== "point" ? item.window_start_seconds : null },
      { part: "end", seconds: item.mode !== "point" ? item.window_end_seconds : null },
    ];
    return candidates.reduce<typeof best>((candidateBest, candidate) => {
      if (candidate.seconds === null) return candidateBest;
      const distance = Math.abs(candidate.seconds - xSeconds);
      if (distance > thresholdSeconds || (candidateBest && candidateBest.distance <= distance)) return candidateBest;
      return { target: { marker, part: candidate.part }, distance };
    }, best);
  }, null)?.target ?? null;
}

function markerDisplayName(marker: MetaSoftMarkerName): string {
  return marker === "VO2_max" ? "VO2max" : marker;
}

function markerModeHelp(mode: MarkerMode): string {
  if (mode === "point") return "Seuil place a l'instant selectionne.";
  if (mode === "previous") return "Fenetre avant l'instant selectionne.";
  return "Fenetre centree sur l'instant selectionne.";
}

function debugZoom(message: string, payload: Record<string, unknown>): void {
  if (!DEBUG_ZOOM) return;
  // eslint-disable-next-line no-console
  console.info(`[metasoft zoom chart] ${message}`, payload);
}
