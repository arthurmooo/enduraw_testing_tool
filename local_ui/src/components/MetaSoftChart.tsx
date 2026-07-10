import { memo, useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import type { MouseEvent as ReactMouseEvent } from "react";
import Plot from "react-plotly.js";
import { Maximize2, X } from "lucide-react";
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
  DraftMarkers,
  MarkerMode,
  MetaSoftMarkerName,
  MetaSoftPoint,
} from "../types/metasoft";

const DEBUG_ZOOM = new URLSearchParams(window.location.search).get("debugZoom") === "1";
const MARKER_POPOVER_WIDTH = 420;
const MARKER_POPOVER_HEIGHT = 240;

interface Props {
  analysis: import("../types/metasoft").MetaSoftAnalysis;
  graph: MetaSoftGraphConfig;
  markers: DraftMarkers;
  phaseFilter: string;
  smoothingSeconds: number;
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
}

function MetaSoftChartComponent({
  analysis,
  graph,
  markers,
  phaseFilter,
  smoothingSeconds,
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
}: Props) {
  const [localXRange, setLocalXRange] = useState<[number, number] | null>(null);
  const [plotRevision, setPlotRevision] = useState(0);
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
      xRange={xRange}
      onXRangeChange={handleXRangeChange}
      showSpeedBands={showSpeedBands}
      cursorPoint={cursorPoint}
      onCursorPoint={onCursorPoint}
      onPlaceMarker={onPlaceMarker}
      onDeleteMarker={onDeleteMarker}
    />
  );

  return (
    <section className="chart-card">
      <div className="chart-title-row">
        <h2>{graph.title}</h2>
        <SeriesToggles series={availableSeries} hiddenSeries={hiddenSeries} onToggle={toggleSeries} />
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
  onXRangeChange,
}: {
  analysis: import("../types/metasoft").MetaSoftAnalysis;
  graph: MetaSoftGraphConfig;
  series: MetaSoftSeriesConfig[];
  height: number;
  plotRevision: number;
  xRange: [number, number] | null;
  onXRangeChange: (range: [number, number] | null) => void;
}) {
  const rows = analysis.computed.running_economy ?? [];
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
          gridcolor: "rgba(255,255,255,0.055)",
        },
      }}
      config={{ responsive: true, displayModeBar: false, doubleClick: "reset" }}
      revision={plotRevision}
      style={{ width: "100%", height }}
      useResizeHandler
      onRelayout={(event: Readonly<Record<string, unknown>>) => {
        const nextRange = xRangeFromRelayout(event);
        if (nextRange !== undefined) onXRangeChange(nextRange);
      }}
      onDoubleClick={() => onXRangeChange(null)}
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
  xRange,
  onXRangeChange,
  showSpeedBands,
  cursorPoint,
  onCursorPoint,
  onPlaceMarker,
  onDeleteMarker,
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
  } | null>(null);
  const [markerHover, setMarkerHover] = useState<MarkerDragTarget | null>(null);
  const [dragPreview, setDragPreview] = useState<MarkerDragPreview | null>(null);
  const canEditTimeMarkers = graph.kind === "time";
  const chartPoints = useMemo(
    () => points.filter((point) => pointXValue(point, graph) !== null),
    [graph, points],
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
  const data = useMemo(() => series.map((seriesItem) => {
    const rawY = chartPoints.map((point) => point.values[seriesItem.key as keyof MetaSoftPoint["values"]]);
    const shouldSmooth = graph.kind === "time" && seriesItem.smoothable;
    return {
      type: "scatter",
      mode: graph.kind === "scatter" ? "markers" : "lines",
      name: seriesItem.label,
      x,
      y: shouldSmooth ? smoothSeries(x, rawY, smoothingSeconds) : rawY,
      yaxis: seriesItem.axis,
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
  }), [chartPoints, graph.kind, series, smoothingSeconds, speedHoverText, x]);
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
    yaxis: {
      title: { text: axisLabel(series, "y"), font: { size: 10, color: "rgba(226,232,240,0.65)" } },
      gridcolor: "rgba(255,255,255,0.055)",
      linecolor: "rgba(255,255,255,0.18)",
      zerolinecolor: "rgba(255,255,255,0.08)",
    },
    yaxis2: {
      overlaying: "y",
      side: "right",
      title: { text: axisLabel(series, "y2"), font: { size: 10, color: "rgba(226,232,240,0.65)" } },
      gridcolor: "rgba(255,255,255,0)",
      linecolor: "rgba(255,255,255,0.18)",
      zerolinecolor: "rgba(255,255,255,0.08)",
    },
  }), [annotations, defaultRange, effectiveRange, graph.kind, graph.xAxis, plotMargins, series, shapes, tickText, tickVals]);
  const config = useMemo(() => ({
    responsive: true,
    displayModeBar: false,
    scrollZoom: false,
    doubleClick: "reset",
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

  const resetZoomFromDoubleClick = useCallback((event?: ReactMouseEvent<HTMLDivElement>) => {
    if (!canEditTimeMarkers) return;
    debugZoom("double click reset requested", {
      graphId: graph.id,
      xRange,
      effectiveRange,
      defaultRange,
      detail: event?.detail,
    });
    event?.stopPropagation();
    clickBlockUntilRef.current = window.performance.now() + 450;
    suppressClickRef.current = true;
    clearPendingClick();
    setProposal(null);
    onXRangeChange(null);
  }, [canEditTimeMarkers, clearPendingClick, defaultRange, effectiveRange, graph.id, onXRangeChange, xRange]);

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
    const tSeconds = timeFromClientX(mouseEvent.clientX, wrapperRef.current, effectiveRange ?? defaultRange, plotMargins);
    if (tSeconds === null) return;
    clearPendingClick();
    clickTimerRef.current = window.setTimeout(() => {
      clickTimerRef.current = null;
      setProposal({
        left: clamp(mouseEvent.clientX - bounds.left, 8, Math.max(8, bounds.width - MARKER_POPOVER_WIDTH - 8)),
        top: clamp(mouseEvent.clientY - bounds.top, 8, Math.max(8, bounds.height - MARKER_POPOVER_HEIGHT - 8)),
        tSeconds: clamp(tSeconds, 0, maxTime),
        mode: "point",
        rangeDuration: "4:00",
        previousDuration: "0:10",
      });
    }, 320);
  }, [canEditTimeMarkers, clearPendingClick, defaultRange, effectiveRange, maxTime, plotMargins]);

  const cancelSingleClick = useCallback(() => {
    resetZoomFromDoubleClick();
  }, [resetZoomFromDoubleClick]);

  const handleContextMenu = useCallback((event: ReactMouseEvent<HTMLDivElement>) => {
    if (!canEditTimeMarkers) return;
    const target = nearestMarkerTargetFromMouse(event, wrapperRef.current, markers, effectiveRange ?? defaultRange, plotMargins);
    if (!target) return;
    event.preventDefault();
    if (!window.confirm(`Supprimer le marqueur ${markerDisplayName(target.marker)} ?`)) return;
    setProposal(null);
    onDeleteMarker(target.marker);
  }, [canEditTimeMarkers, defaultRange, effectiveRange, markers, onDeleteMarker, plotMargins]);

  const handleMouseDown = useCallback((event: ReactMouseEvent<HTMLDivElement>) => {
    if (!canEditTimeMarkers) return;
    if (event.button !== 0) return;
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
      onDoubleClickCapture={resetZoomFromDoubleClick}
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
        onDoubleClick={cancelSingleClick}
      />
      {proposal && (
        <div
          className="marker-popover"
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
