import { memo, useEffect, useMemo, useRef, useState } from "react";
import type { MouseEvent as ReactMouseEvent } from "react";
import Plot from "react-plotly.js";
import { Maximize2, X } from "lucide-react";
import {
  buildMarkerAnnotations,
  buildMarkerShapes,
  buildStaticAnnotations,
  buildTimeBandShapes,
} from "../lib/chartUtils";
import { MARKER_COLORS, MetaSoftGraphConfig, MetaSoftSeriesConfig } from "../lib/graphConfig";
import { MARKER_NAMES, secondsToClock } from "../lib/markerUtils";
import type {
  DraftMarker,
  DraftMarkers,
  MarkerMode,
  MetaSoftMarkerName,
  MetaSoftPoint,
} from "../types/metasoft";

type MarkerDragPart = "start" | "center" | "end";
type MarkerDragTarget = { marker: MetaSoftMarkerName; part: MarkerDragPart };
type MarkerDragPreview = MarkerDragTarget & { xSeconds: number };

interface Props {
  analysis: import("../types/metasoft").MetaSoftAnalysis;
  graph: MetaSoftGraphConfig;
  markers: DraftMarkers;
  phaseFilter: string;
  smoothingSeconds: number;
  onCursorPoint: (point: MetaSoftPoint | null) => void;
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
  onCursorPoint,
  onPlaceMarker,
  onDeleteMarker,
}: Props) {
  const [fullscreen, setFullscreen] = useState(false);
  const [xRange, setXRange] = useState<[number, number] | null>(null);
  const [plotRevision, setPlotRevision] = useState(0);
  const [hiddenSeries, setHiddenSeries] = useState<Set<string>>(new Set());
  const availableSeries = graph.series.filter((series) => isSeriesAvailable(analysis, graph, series));
  const visibleSeries = availableSeries.filter((series) => !hiddenSeries.has(series.key));
  const missingSeries = graph.series.filter((series) => !isSeriesAvailable(analysis, graph, series));
  const points = useMemo(
    () => analysis.points.filter((point) => phaseFilter === "Tout" || point.phase === phaseFilter),
    [analysis.points, phaseFilter],
  );

  useEffect(() => {
    setXRange(null);
    setPlotRevision((revision) => revision + 1);
  }, [analysis.file.filename, phaseFilter]);
  useEffect(() => setHiddenSeries(new Set()), [analysis.file.filename, graph.id]);

  const handleXRangeChange = (range: [number, number] | null) => {
    setXRange(range);
    if (range === null) setPlotRevision((revision) => revision + 1);
  };

  const toggleSeries = (series: MetaSoftSeriesConfig) => {
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
  };

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
      smoothingSeconds={smoothingSeconds}
      xRange={xRange}
      onXRangeChange={handleXRangeChange}
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
          onClick={() => setFullscreen(true)}
          className="icon-button push-right"
          aria-label={`Ouvrir ${graph.title} en plein ecran`}
          title="Plein ecran"
        >
          <Maximize2 size={16} />
        </button>
      </div>
      {fullscreen ? <div className="chart-body" style={{ height: 260 }} /> : body(260)}
      {missingSeries.length > 0 && (
        <p className="missing-series">Absent XML : {missingSeries.map((series) => series.label).join(", ")}</p>
      )}
      {fullscreen && (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal-panel">
            <div className="modal-header">
              <h2>{graph.title}</h2>
              <SeriesToggles series={availableSeries} hiddenSeries={hiddenSeries} onToggle={toggleSeries} />
              <button
                type="button"
                className="icon-button push-right"
                onClick={() => setFullscreen(false)}
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
  smoothingSeconds,
  xRange,
  onXRangeChange,
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
  smoothingSeconds: number;
  xRange: [number, number] | null;
  onXRangeChange: (range: [number, number] | null) => void;
  onCursorPoint: (point: MetaSoftPoint | null) => void;
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
  } | null>(null);
  const [markerHover, setMarkerHover] = useState<MarkerDragTarget | null>(null);
  const [dragPreview, setDragPreview] = useState<MarkerDragPreview | null>(null);
  const canEditTimeMarkers = graph.kind === "time";
  const chartPoints = useMemo(
    () => points.filter((point) => pointXValue(point, graph) !== null),
    [graph, points],
  );
  const x = useMemo(() => chartPoints.map((point) => pointXValue(point, graph)), [chartPoints, graph]);
  const maxTime = Math.max(...analysis.points.map((point) => point.t_seconds ?? 0), 0);
  const defaultRange = defaultRangeFromValues(x, graph.kind === "time" ? maxTime : 1);
  const tickVals = graph.kind === "time" ? buildTickVals(defaultRange) : [];
  const effectiveRange = xRange && xRange[0] >= defaultRange[0] && xRange[1] <= defaultRange[1] ? xRange : null;
  const visibleMarkers = canEditTimeMarkers && dragPreview
    ? { ...markers, [dragPreview.marker]: previewDraggedMarker(markers[dragPreview.marker], dragPreview, maxTime) }
    : markers;
  const plotMargins = { l: 44, r: graph.series.some((item) => item.axis === "y2") ? 42 : 16, t: 14, b: 42 };
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
      line: { color: seriesItem.color, width: 0.8 },
      marker: { color: seriesItem.color, size: graph.kind === "scatter" ? 5 : 4 },
      hovertemplate: `%{y}<extra>${seriesItem.label}</extra>`,
      connectgaps: false,
    };
  }), [chartPoints, graph.kind, series, smoothingSeconds, x]);
  const layout = {
    autosize: true,
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    margin: plotMargins,
    font: { color: "rgba(226,232,240,0.78)", size: 10 },
    hovermode: graph.kind === "time" ? "x unified" : "closest",
    dragmode: "zoom",
    showlegend: false,
    shapes: canEditTimeMarkers ? [...staticShapes, ...markerShapes] : [],
    annotations: canEditTimeMarkers ? [...staticAnnotations, ...markerAnnotations] : [],
    xaxis: {
      range: effectiveRange ?? defaultRange,
      ...(graph.kind === "time" ? {
        tickvals: tickVals,
        ticktext: tickVals.map(secondsToClock),
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
  };

  useEffect(() => () => {
    if (clickTimerRef.current !== null) window.clearTimeout(clickTimerRef.current);
    if (dragFrameRef.current !== null) window.cancelAnimationFrame(dragFrameRef.current);
  }, []);

  useEffect(() => {
    dragPreviewRef.current = dragPreview;
  }, [dragPreview]);

  const clearPendingClick = () => {
    if (clickTimerRef.current === null) return;
    window.clearTimeout(clickTimerRef.current);
    clickTimerRef.current = null;
  };

  const updateMarkerHover = (target: MarkerDragTarget | null) => {
    if (sameMarkerTarget(markerHoverRef.current, target)) return;
    markerHoverRef.current = target;
    setMarkerHover(target);
  };

  const scheduleDragPreview = (next: MarkerDragPreview) => {
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
  };

  const clearPendingDragFrame = () => {
    if (dragFrameRef.current !== null) window.cancelAnimationFrame(dragFrameRef.current);
    dragFrameRef.current = null;
    pendingDragPreviewRef.current = null;
  };

  const openMarkerProposal = (event: Readonly<{ event?: MouseEvent; points?: Array<{ x?: unknown }> }>) => {
    if (!canEditTimeMarkers) return;
    if (suppressClickRef.current) {
      suppressClickRef.current = false;
      return;
    }
    const mouseEvent = event.event;
    const bounds = wrapperRef.current?.getBoundingClientRect();
    if (!mouseEvent || !bounds || mouseEvent.detail > 1) {
      clearPendingClick();
      return;
    }
    const tSeconds = timeFromClientX(mouseEvent.clientX, wrapperRef.current, effectiveRange ?? defaultRange, plotMargins);
    if (tSeconds === null) return;
    clearPendingClick();
    clickTimerRef.current = window.setTimeout(() => {
      clickTimerRef.current = null;
      setProposal({
        left: clamp(mouseEvent.clientX - bounds.left, 8, Math.max(8, bounds.width - 248)),
        top: clamp(mouseEvent.clientY - bounds.top, 8, Math.max(8, bounds.height - 166)),
        tSeconds: clamp(tSeconds, 0, maxTime),
        mode: "point",
        rangeDuration: "4:00",
      });
    }, 180);
  };

  const cancelSingleClick = () => {
    clearPendingClick();
    setProposal(null);
    onXRangeChange(null);
  };

  const handleContextMenu = (event: ReactMouseEvent<HTMLDivElement>) => {
    if (!canEditTimeMarkers) return;
    const target = nearestMarkerTargetFromMouse(event, wrapperRef.current, markers, effectiveRange ?? defaultRange, plotMargins);
    if (!target) return;
    event.preventDefault();
    setProposal(null);
    onDeleteMarker(target.marker);
  };

  const handleMouseDown = (event: ReactMouseEvent<HTMLDivElement>) => {
    if (!canEditTimeMarkers) return;
    if (event.button !== 0) return;
    const target = nearestMarkerTargetFromMouse(event, wrapperRef.current, markers, effectiveRange ?? defaultRange, plotMargins);
    const xSeconds = target ? timeFromMouse(event, wrapperRef.current, effectiveRange ?? defaultRange, plotMargins) : null;
    if (!target || xSeconds === null) return;
    event.preventDefault();
    suppressClickRef.current = true;
    clearPendingClick();
    clearPendingDragFrame();
    setProposal(null);
    const nextDrag = { ...target, xSeconds: clamp(xSeconds, 0, maxTime) };
    dragPreviewRef.current = nextDrag;
    setDragPreview(nextDrag);
  };

  const handleMouseMove = (event: ReactMouseEvent<HTMLDivElement>) => {
    if (!canEditTimeMarkers) return;
    const currentDrag = dragPreviewRef.current;
    if (currentDrag) {
      const xSeconds = timeFromMouse(event, wrapperRef.current, effectiveRange ?? defaultRange, plotMargins);
      if (xSeconds !== null) scheduleDragPreview({ ...currentDrag, xSeconds: clamp(xSeconds, 0, maxTime) });
      return;
    }
    updateMarkerHover(
      nearestMarkerTargetFromMouse(event, wrapperRef.current, markers, effectiveRange ?? defaultRange, plotMargins),
    );
  };

  const handleMouseUp = (event?: ReactMouseEvent<HTMLDivElement>) => {
    if (!canEditTimeMarkers) return;
    let finalDrag = pendingDragPreviewRef.current ?? dragPreviewRef.current;
    if (!finalDrag) return;
    const xSeconds = event
      ? timeFromMouse(event, wrapperRef.current, effectiveRange ?? defaultRange, plotMargins)
      : null;
    if (xSeconds !== null) finalDrag = { ...finalDrag, xSeconds: clamp(xSeconds, 0, maxTime) };
    clearPendingDragFrame();
    const next = draggedMarkerBounds(markers[finalDrag.marker], finalDrag.part, finalDrag.xSeconds, maxTime);
    onPlaceMarker(finalDrag.marker, next.tSeconds, next.mode, next.windowStart, next.windowEnd);
    dragPreviewRef.current = null;
    setDragPreview(null);
  };

  const placeProposalMarker = (marker: MetaSoftMarkerName) => {
    if (!proposal) return;
    if (proposal.mode === "point") {
      onPlaceMarker(marker, proposal.tSeconds, "point", null, null);
      setProposal(null);
      return;
    }
    const rangeSeconds = durationToSeconds(proposal.rangeDuration);
    if (rangeSeconds === null) return;
    const [windowStart, windowEnd] = centeredWindowBounds(proposal.tSeconds, rangeSeconds, maxTime);
    onPlaceMarker(marker, proposal.tSeconds, "range", windowStart, windowEnd);
    setProposal(null);
  };

  return (
    <div
      ref={wrapperRef}
      className="chart-body"
      style={{ cursor: cursorForMarkerDrag(dragPreview?.part ?? markerHover?.part ?? null, Boolean(dragPreview)) }}
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
        data={data}
        layout={layout}
        config={{
          responsive: true,
          displayModeBar: false,
          scrollZoom: false,
          doubleClick: "reset",
          editable: false,
        }}
        revision={plotRevision}
        style={{ width: "100%", height }}
        useResizeHandler
        onClick={canEditTimeMarkers ? openMarkerProposal : undefined}
        onRelayout={(event: Readonly<Record<string, unknown>>) => {
          const nextRange = xRangeFromRelayout(event);
          if (nextRange !== undefined) onXRangeChange(nextRange);
        }}
        onHover={(event: Readonly<{ points?: Array<{ customdata?: unknown; x?: unknown }> }>) => {
          onCursorPoint(nearestEventPoint(chartPoints, event, graph));
        }}
        onUnhover={() => onCursorPoint(null)}
        onDoubleClick={cancelSingleClick}
      />
      {proposal && (
        <div className="marker-popover" style={{ left: proposal.left, top: proposal.top }}>
          <div className="popover-head">
            <div>
              <p>Placer un seuil</p>
              <span>{secondsToClock(proposal.tSeconds)}</span>
            </div>
            <button type="button" onClick={() => setProposal(null)} aria-label="Fermer">x</button>
          </div>
          <div className="segmented">
            {(["point", "range"] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                onClick={() => setProposal({ ...proposal, mode })}
                className={proposal.mode === mode ? "active" : ""}
              >
                {mode === "point" ? "Ligne" : "Range"}
              </button>
            ))}
          </div>
          {proposal.mode === "range" && (
            <label className="field small-field">
              Duree
              <input
                value={proposal.rangeDuration}
                onChange={(event) => setProposal({ ...proposal, rangeDuration: event.target.value })}
                onBlur={() => {
                  const seconds = durationToSeconds(proposal.rangeDuration);
                  if (seconds !== null) setProposal({ ...proposal, rangeDuration: secondsToDuration(seconds) });
                }}
                placeholder="4:00"
              />
            </label>
          )}
          <div className="marker-choice-grid">
            {MARKER_NAMES.map((marker) => (
              <button
                key={marker}
                type="button"
                onClick={() => placeProposalMarker(marker)}
                disabled={proposal.mode === "range" && durationToSeconds(proposal.rangeDuration) === null}
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

function smoothSeries(
  x: Array<number | null>,
  y: Array<number | string | null | undefined>,
  windowSeconds: number,
): Array<number | string | null | undefined> {
  if (windowSeconds <= 0) return y;
  const radius = windowSeconds / 2;
  let left = 0;
  let right = 0;
  let sum = 0;
  let count = 0;
  return y.map((value, index) => {
    if (typeof value !== "number" || !Number.isFinite(value)) return value;
    const center = x[index];
    if (typeof center !== "number" || !Number.isFinite(center)) return value;
    while (right < y.length) {
      const rightX = x[right];
      if (typeof rightX !== "number" || rightX > center + radius) break;
      const candidate = y[right];
      if (typeof candidate === "number" && Number.isFinite(candidate)) {
        sum += candidate;
        count += 1;
      }
      right += 1;
    }
    while (left < y.length) {
      const leftX = x[left];
      if (typeof leftX !== "number" || leftX >= center - radius) break;
      const candidate = y[left];
      if (typeof candidate === "number" && Number.isFinite(candidate)) {
        sum -= candidate;
        count -= 1;
      }
      left += 1;
    }
    return count ? Number((sum / count).toFixed(3)) : value;
  });
}

function isSeriesAvailable(
  analysis: import("../types/metasoft").MetaSoftAnalysis,
  graph: MetaSoftGraphConfig,
  series: MetaSoftSeriesConfig,
): boolean {
  if (graph.source === "running_economy") {
    return (analysis.computed.running_economy ?? []).some((row) => row.value_j_kg_m !== null);
  }
  return isXAxisAvailable(analysis, graph)
    && Boolean(analysis.metrics[series.key as keyof typeof analysis.metrics])
    && hasNumericPointValue(analysis, series.key);
}

function isXAxisAvailable(
  analysis: import("../types/metasoft").MetaSoftAnalysis,
  graph: MetaSoftGraphConfig,
): boolean {
  if (graph.xAxis.key === "t_seconds" || graph.xAxis.key === "stage_index") return true;
  return Boolean(analysis.metrics[graph.xAxis.key]) && hasNumericPointValue(analysis, graph.xAxis.key);
}

function hasNumericPointValue(
  analysis: import("../types/metasoft").MetaSoftAnalysis,
  key: MetaSoftSeriesConfig["key"] | MetaSoftGraphConfig["xAxis"]["key"],
): boolean {
  if (key === "t_seconds" || key === "stage_index" || key === "value_j_kg_m") return true;
  return analysis.points.some((point) => {
    const value = point.values[key];
    return typeof value === "number" && Number.isFinite(value);
  });
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

function previewDraggedMarker(marker: DraftMarker, drag: MarkerDragPreview, maxTime: number): DraftMarker {
  const { tSeconds, mode, windowStart, windowEnd } = draggedMarkerBounds(marker, drag.part, drag.xSeconds, maxTime);
  return {
    ...marker,
    mode,
    t_seconds: tSeconds,
    window_start_seconds: windowStart,
    window_end_seconds: windowEnd,
  };
}

function draggedMarkerBounds(
  marker: DraftMarker,
  part: MarkerDragPart,
  xSeconds: number,
  maxTime: number,
): { tSeconds: number; mode: MarkerMode; windowStart: number | null; windowEnd: number | null } {
  if (marker.mode === "point" || marker.window_start_seconds === null || marker.window_end_seconds === null) {
    return { tSeconds: xSeconds, mode: "point", windowStart: null, windowEnd: null };
  }
  if (part === "center") {
    const [windowStart, windowEnd] = centeredWindowBounds(
      xSeconds,
      marker.window_end_seconds - marker.window_start_seconds,
      maxTime,
    );
    return { tSeconds: xSeconds, mode: "range", windowStart, windowEnd };
  }
  const upperBound = maxTime > 0 ? maxTime : Number.POSITIVE_INFINITY;
  const minDuration = 1;
  const maxStart = Math.max(0, marker.window_end_seconds - minDuration);
  const minEnd = marker.window_start_seconds + minDuration;
  const windowStart = part === "start"
    ? clamp(xSeconds, 0, maxStart)
    : marker.window_start_seconds;
  const windowEnd = part === "end"
    ? clamp(xSeconds, minEnd, Math.max(minEnd, upperBound))
    : marker.window_end_seconds;
  return { tSeconds: (windowStart + windowEnd) / 2, mode: "range", windowStart, windowEnd };
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
      { part: "start", seconds: item.mode === "range" ? item.window_start_seconds : null },
      { part: "end", seconds: item.mode === "range" ? item.window_end_seconds : null },
    ];
    return candidates.reduce<typeof best>((candidateBest, candidate) => {
      if (candidate.seconds === null) return candidateBest;
      const distance = Math.abs(candidate.seconds - xSeconds);
      if (distance > thresholdSeconds || (candidateBest && candidateBest.distance <= distance)) return candidateBest;
      return { target: { marker, part: candidate.part }, distance };
    }, best);
  }, null)?.target ?? null;
}

function cursorForMarkerDrag(part: MarkerDragPart | null, dragging: boolean): string | undefined {
  if (part === "start" || part === "end") return "ew-resize";
  if (part === "center") return dragging ? "grabbing" : "grab";
  return undefined;
}

function sameMarkerTarget(left: MarkerDragTarget | null, right: MarkerDragTarget | null): boolean {
  return (left?.marker ?? null) === (right?.marker ?? null)
    && (left?.part ?? null) === (right?.part ?? null);
}

function sameDragPreview(left: MarkerDragPreview | null, right: MarkerDragPreview | null): boolean {
  return sameMarkerTarget(left, right) && (left?.xSeconds ?? null) === (right?.xSeconds ?? null);
}

function timeFromMouse(
  event: ReactMouseEvent<HTMLDivElement>,
  wrapper: HTMLDivElement | null,
  range: [number, number],
  margin: { l: number; r: number },
): number | null {
  return timeFromClientX(event.clientX, wrapper, range, margin);
}

function timeFromClientX(
  clientX: number,
  wrapper: HTMLDivElement | null,
  range: [number, number],
  margin: { l: number; r: number },
): number | null {
  if (!wrapper) return null;
  const bounds = wrapper.getBoundingClientRect();
  const plotLeft = bounds.left + margin.l;
  const plotRight = bounds.right - margin.r;
  const plotWidth = plotRight - plotLeft;
  if (plotWidth <= 0 || clientX < plotLeft || clientX > plotRight) return null;
  return range[0] + ((clientX - plotLeft) / plotWidth) * (range[1] - range[0]);
}

function centeredWindowBounds(tSeconds: number, durationSeconds: number, maxTime: number): [number, number] {
  const duration = Math.max(1, durationSeconds);
  if (maxTime > 0 && duration >= maxTime) return [0, maxTime];
  let start = tSeconds - duration / 2;
  let end = tSeconds + duration / 2;
  if (start < 0) {
    end -= start;
    start = 0;
  }
  if (maxTime > 0 && end > maxTime) {
    start = Math.max(0, start - (end - maxTime));
    end = maxTime;
  }
  return [start, end];
}

function durationToSeconds(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  if (/^\d+([.,]\d+)?$/.test(trimmed)) {
    const parsed = Number(trimmed.replace(",", "."));
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
  }
  const parts = trimmed.split(":").map((part) => Number(part));
  if (parts.length < 2 || parts.length > 3 || parts.some((part) => !Number.isFinite(part) || part < 0)) {
    return null;
  }
  const [hours, minutes, seconds] = parts.length === 3 ? parts : [0, parts[0], parts[1]];
  const total = hours * 3600 + minutes * 60 + seconds;
  return total > 0 ? total : null;
}

function secondsToDuration(seconds: number): string {
  const rounded = Math.max(1, Math.round(seconds));
  const h = Math.floor(rounded / 3600);
  const m = Math.floor((rounded % 3600) / 60);
  const s = rounded % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
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

function nearestEventPoint(
  points: MetaSoftPoint[],
  event: Readonly<{ points?: Array<{ customdata?: unknown; x?: unknown }> }>,
  graph: MetaSoftGraphConfig,
): MetaSoftPoint | null {
  const pointIndex = event.points?.[0]?.customdata;
  if (typeof pointIndex === "number") {
    return points.find((point) => point.index === pointIndex) ?? null;
  }
  const x = event.points?.[0]?.x;
  if (typeof x !== "number") return null;
  return points.reduce<MetaSoftPoint | null>((best, point) => {
    const pointX = pointXValue(point, graph);
    if (pointX === null) return best;
    if (!best || best.t_seconds === null) return point;
    const bestX = pointXValue(best, graph);
    if (bestX === null) return point;
    return Math.abs(pointX - x) < Math.abs(bestX - x) ? point : best;
  }, null);
}

function defaultRangeFromValues(values: Array<number | null>, fallbackMax: number): [number, number] {
  const numericValues = values
    .filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  if (!numericValues.length) return [0, fallbackMax];
  const start = Math.min(...numericValues);
  const end = Math.max(...numericValues);
  if (end > start) return [start, end];
  const pad = Math.max(Math.abs(start) * 0.05, 1);
  return [start - pad, end + pad];
}

function buildTickVals(range: [number, number]): number[] {
  const span = range[1] - range[0];
  if (span <= 0) return [];
  const step = span > 5400 ? 1200 : span > 2400 ? 600 : 300;
  const vals = [];
  for (let value = Math.ceil(range[0] / step) * step; value <= range[1]; value += step) vals.push(value);
  return vals;
}

function pointXValue(point: MetaSoftPoint, graph: MetaSoftGraphConfig): number | null {
  if (graph.xAxis.key === "t_seconds") return point.t_seconds;
  if (graph.xAxis.key === "stage_index") return null;
  const value = point.values[graph.xAxis.key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function axisTitle(axis: MetaSoftGraphConfig["xAxis"]): string {
  return axis.unit ? `${axis.label} (${axis.unit})` : axis.label;
}

function axisLabel(series: MetaSoftSeriesConfig[], axis: "y" | "y2"): string {
  const units = series
    .filter((item) => item.axis === axis)
    .map((item) => item.unit)
    .filter((unit): unit is string => Boolean(unit));
  return Array.from(new Set(units)).join(" / ");
}
