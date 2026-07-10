import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, FileUp, SlidersHorizontal } from "lucide-react";
import { AnalysisExportSection, type MarkerReportSummaryItem } from "./components/AnalysisExportSection";
import { CursorRail } from "./components/CursorRail";
import { MarkerPanel } from "./components/MarkerPanel";
import { MetaSoftChart } from "./components/MetaSoftChart";
import {
  RunningEconomyManualSection,
  type ManualEconomyReportSummary,
  type RunningEconomyManualHandle,
} from "./components/RunningEconomyManualSection";
import { GRAPH_CONFIGS } from "./lib/graphConfig";
import { ApiError, apiGet, apiPost, getBootstrap } from "./lib/localApi";
import {
  buildDraftMarker,
  createInitialMarkers,
  formatNumber,
  MARKER_NAMES,
  secondsToClock,
  serializeMarkerSelections,
} from "./lib/markerUtils";
import type {
  ConfirmedMarkers,
  DraftMarkers,
  LocalAnalysisPayload,
  MarkerMode,
  MetaSoftMarkerName,
  MetaSoftPoint,
  ProfileConflict,
  ReportResponse,
} from "./types/metasoft";

const NAV_ITEMS = [
  { label: "Lecture", targetId: "metasoft-reading" },
  { label: "Marqueurs", targetId: "metasoft-markers" },
  { label: "EC", targetId: "metasoft-running-economy" },
  { label: "Report", targetId: "metasoft-profile-report" },
];
const READING_GRAPH_CONFIGS = GRAPH_CONFIGS.filter((graph) => graph.source === "points");
const DEFAULT_READING_GRAPH_ID = READING_GRAPH_CONFIGS.some((graph) => graph.id === "vo2_vco2_time")
  ? "vo2_vco2_time"
  : READING_GRAPH_CONFIGS[0]?.id;
type ReadingViewMode = "all" | "focus";
const DEBUG_ZOOM = new URLSearchParams(window.location.search).get("debugZoom") === "1";

export default function App() {
  const [bootstrap, setBootstrap] = useState<{ matchId: string; token: string } | null>(null);
  const [payload, setPayload] = useState<LocalAnalysisPayload | null>(null);
  const [draftMarkers, setDraftMarkers] = useState<DraftMarkers | null>(null);
  const [confirmedMarkers, setConfirmedMarkers] = useState<ConfirmedMarkers>({});
  const [deletedMarkers, setDeletedMarkers] = useState<Set<MetaSoftMarkerName>>(new Set());
  const [dirtyMarkers, setDirtyMarkers] = useState<Set<MetaSoftMarkerName>>(new Set());
  const [phaseFilter, setPhaseFilter] = useState("Tout");
  const [smoothingSeconds, setSmoothingSeconds] = useState(20);
  const [showSpeedBands, setShowSpeedBands] = useState(true);
  const [timeXRange, setTimeXRange] = useState<[number, number] | null>(null);
  const [timeZoomResetRevision, setTimeZoomResetRevision] = useState(0);
  const [fullscreenGraphId, setFullscreenGraphId] = useState<string | null>(null);
  const [cursorPoint, setCursorPoint] = useState<MetaSoftPoint | null>(null);
  const [selectedReadingGraphId, setSelectedReadingGraphId] = useState(DEFAULT_READING_GRAPH_ID);
  const [readingViewMode, setReadingViewMode] = useState<ReadingViewMode>("all");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [conflicts, setConflicts] = useState<ProfileConflict[]>([]);
  const [manualEconomyReportSummary, setManualEconomyReportSummary] = useState<ManualEconomyReportSummary | null>(null);
  const manualEconomyRef = useRef<RunningEconomyManualHandle | null>(null);
  const ignoreTimeRelayoutUntilRef = useRef(0);
  const timeXRangeRef = useRef<[number, number] | null>(null);
  const blockedResetRangeRef = useRef<[number, number] | null>(null);
  const lastZoomSourceGraphIdRef = useRef<string | null>(null);
  const blockedResetGraphIdRef = useRef<string | null>(null);
  const cursorFrameRef = useRef<number | null>(null);
  const cursorPointRef = useRef<MetaSoftPoint | null>(null);
  const pendingCursorPointRef = useRef<MetaSoftPoint | null>(null);
  const reportEditRevisionRef = useRef(0);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const boot = getBootstrap();
        setBootstrap(boot);
        setBusy("Chargement");
        const result = await apiGet<LocalAnalysisPayload>(`/api/matches/${boot.matchId}/analysis`, boot.token);
        if (cancelled) return;
        const firstPoint = result.analysis.points[0] ?? null;
        const confirmed = result.confirmed_markers ?? {};
        const deleted = new Set(result.deleted_markers ?? []);
        const initialMarkers = createInitialMarkers(result.analysis);
        for (const name of MARKER_NAMES) {
          const marker = confirmed[name];
          if (marker) initialMarkers[name] = marker;
          if (deleted.has(name)) {
            initialMarkers[name] = buildDraftMarker(name, result.analysis.points, null, "point");
          }
        }
        setPayload(result);
        setDraftMarkers(initialMarkers);
        setConfirmedMarkers(confirmed);
        setDeletedMarkers(deleted);
        setDirtyMarkers(new Set());
        reportEditRevisionRef.current = 0;
        cursorPointRef.current = firstPoint;
        pendingCursorPointRef.current = firstPoint;
        setCursorPoint(firstPoint);
        setPhaseFilter("Tout");
        timeXRangeRef.current = null;
        blockedResetRangeRef.current = null;
        lastZoomSourceGraphIdRef.current = null;
        blockedResetGraphIdRef.current = null;
        setFullscreenGraphId(null);
        setTimeXRange(null);
        setReadingViewMode("all");
        setManualEconomyReportSummary(null);
      } catch (err) {
        if (!cancelled) setError(errorMessage(err));
      } finally {
        if (!cancelled) setBusy(null);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => () => {
    if (cursorFrameRef.current !== null) window.cancelAnimationFrame(cursorFrameRef.current);
  }, []);

  const phases = useMemo(
    () => Array.from(new Set((payload?.analysis.phases ?? []).map((phase) => phase.phase))).filter(Boolean),
    [payload],
  );
  const timeRangeKey = useMemo(() => {
    if (!timeXRange) return `full-${timeZoomResetRevision}`;
    return `range-${timeXRange[0].toFixed(3)}-${timeXRange[1].toFixed(3)}`;
  }, [timeXRange, timeZoomResetRevision]);
  const flushCursorPoint = useCallback(() => {
    cursorFrameRef.current = null;
    const next = pendingCursorPointRef.current;
    if (sameCursorPoint(cursorPointRef.current, next)) return;
    cursorPointRef.current = next;
    setCursorPoint(next);
  }, []);

  const handleCursorPoint = useCallback((_graphId: string, point: MetaSoftPoint | null) => {
    const current = cursorFrameRef.current !== null ? pendingCursorPointRef.current : cursorPointRef.current;
    if (sameCursorPoint(current, point)) return;
    pendingCursorPointRef.current = point;
    if (cursorFrameRef.current !== null) return;
    cursorFrameRef.current = window.requestAnimationFrame(flushCursorPoint);
  }, [flushCursorPoint]);

  const handleTimeXRangeChange = useCallback((graphId: string, range: [number, number] | null) => {
    const now = window.performance.now();
    if (range === null) {
      if (timeXRangeRef.current === null) {
        debugZoom("ignore reset without active range", { graphId, range });
        return;
      }
      // ponytail: keep one reset pass to avoid reusing a stale per-plot relayout range.
      ignoreTimeRelayoutUntilRef.current = now + 500;
      blockedResetRangeRef.current = timeXRangeRef.current;
      blockedResetGraphIdRef.current = lastZoomSourceGraphIdRef.current;
      debugZoom("accept reset", {
        graphId,
        blockedGraphId: blockedResetGraphIdRef.current,
        blockedRange: blockedResetRangeRef.current,
      });
      timeXRangeRef.current = null;
      lastZoomSourceGraphIdRef.current = null;
      setTimeZoomResetRevision((revision) => revision + 1);
      setTimeXRange(null);
      return;
    }
    if (now < ignoreTimeRelayoutUntilRef.current) {
      debugZoom("ignore range during reset window", { graphId, range, blockedRange: blockedResetRangeRef.current });
      return;
    }
    if (sameRange(range, blockedResetRangeRef.current)) {
      debugZoom("ignore stale reset range", {
        graphId,
        range,
        blockedGraphId: blockedResetGraphIdRef.current,
        blockedRange: blockedResetRangeRef.current,
      });
      return;
    }
    blockedResetRangeRef.current = null;
    blockedResetGraphIdRef.current = null;
    lastZoomSourceGraphIdRef.current = graphId;
    timeXRangeRef.current = range;
    debugZoom("accept range", { graphId, range });
    setTimeXRange(range);
  }, []);

  const markDirty = useCallback((marker: MetaSoftMarkerName) => {
    reportEditRevisionRef.current += 1;
    setDirtyMarkers((current) => new Set(current).add(marker));
    setReport(null);
    setConflicts([]);
    setError(null);
  }, []);

  const markManualEconomyDirty = useCallback(() => {
    reportEditRevisionRef.current += 1;
    setReport(null);
    setConflicts([]);
    setError(null);
  }, []);

  const placeMarker = useCallback((
    marker: MetaSoftMarkerName,
    tSeconds: number,
    mode: MarkerMode,
    windowStartSeconds?: number | null,
    windowEndSeconds?: number | null,
  ) => {
    if (!payload) return;
    setDraftMarkers((current) => {
      if (!current) return current;
      return {
        ...current,
        [marker]: buildDraftMarker(marker, payload.analysis.points, tSeconds, mode, windowStartSeconds, windowEndSeconds),
      };
    });
    markDirty(marker);
  }, [markDirty, payload]);

  const deleteMarker = useCallback((marker: MetaSoftMarkerName) => {
    if (!payload) return;
    setDraftMarkers((current) => current ? {
      ...current,
      [marker]: buildDraftMarker(marker, payload.analysis.points, null, "point"),
    } : current);
    markDirty(marker);
  }, [markDirty, payload]);

  const handleFullscreenChange = useCallback((graphId: string, open: boolean) => {
    setFullscreenGraphId(open ? graphId : null);
  }, []);

  if (error && !payload) {
    return (
      <main className="app-shell">
        <section className="fatal-panel">
          <AlertTriangle size={22} />
          <h1>MetaSoft local indisponible</h1>
          <p>{error}</p>
        </section>
      </main>
    );
  }

  if (!payload || !draftMarkers) {
    return (
      <main className="app-shell">
        <section className="loading-panel">Chargement de l'analyse MetaSoft locale...</section>
      </main>
    );
  }

  const { analysis, match, warnings } = payload;
  const profileVo2maxMlKgMin = profileMeasuredVo2max(payload.profile);
  const markerVo2maxMlKgMin = currentMarkerVo2maxMlKgMin(
    draftMarkers,
    confirmedMarkers,
    dirtyMarkers,
    deletedMarkers,
    profileVo2maxMlKgMin,
  );
  const selectedReadingGraph = READING_GRAPH_CONFIGS.find((graph) => graph.id === selectedReadingGraphId)
    ?? READING_GRAPH_CONFIGS[0];
  const markerReportSummary = buildMarkerReportSummary(
    draftMarkers,
    confirmedMarkers,
    dirtyMarkers,
    deletedMarkers,
  );

  const renderReadingChart = (graph: (typeof READING_GRAPH_CONFIGS)[number], height?: number) => (
    <MetaSoftChart
      key={`${readingViewMode}-${graph.kind === "time" ? `${graph.id}-${timeRangeKey}` : graph.id}`}
      analysis={analysis}
      graph={graph}
      markers={draftMarkers}
      phaseFilter={phaseFilter}
      smoothingSeconds={graph.kind === "time" ? smoothingSeconds : 0}
      showSpeedBands={graph.kind === "time" ? showSpeedBands : false}
      timeXRange={graph.kind === "time" ? timeXRange : null}
      timeZoomResetRevision={graph.kind === "time" ? timeZoomResetRevision : 0}
      cursorPoint={graph.kind === "time" ? cursorPoint : null}
      fullscreen={fullscreenGraphId === graph.id}
      height={height}
      onFullscreenChange={handleFullscreenChange}
      onTimeXRangeChange={graph.kind === "time" ? handleTimeXRangeChange : undefined}
      onCursorPoint={handleCursorPoint}
      onPlaceMarker={placeMarker}
      onDeleteMarker={deleteMarker}
    />
  );

  const reportProfile = async (overwrite = false) => {
    await runOfficialAction(overwrite ? "Overwrite" : "Report", async () => {
      const reportEditRevision = reportEditRevisionRef.current;
      try {
        const markerSelections = serializeMarkerSelections(draftMarkers, dirtyMarkers);
        const manualEconomyPayload = manualEconomyRef.current?.reportPayload();
        const response = await apiPost<ReportResponse>(
          `/api/matches/${match.match_id}/profile/report`,
          bootstrap?.token ?? "",
          {
            marker_selections: markerSelections,
            ...(manualEconomyPayload ?? {}),
            ...(overwrite ? { conflict_policy: "overwrite" } : {}),
          },
        );
        if (reportEditRevisionRef.current !== reportEditRevision) return;
        const canonical = await apiGet<LocalAnalysisPayload>(
          `/api/matches/${match.match_id}/analysis`,
          bootstrap?.token ?? "",
        );
        if (reportEditRevisionRef.current !== reportEditRevision) return;
        const canonicalConfirmed = canonical.confirmed_markers ?? {};
        const canonicalDeleted = new Set(canonical.deleted_markers ?? []);
        const canonicalDrafts = createInitialMarkers(canonical.analysis);
        for (const name of MARKER_NAMES) {
          const marker = canonicalConfirmed[name];
          if (marker) canonicalDrafts[name] = marker;
          if (canonicalDeleted.has(name)) {
            canonicalDrafts[name] = buildDraftMarker(name, canonical.analysis.points, null, "point");
          }
        }
        setPayload(canonical);
        setDraftMarkers(canonicalDrafts);
        setConfirmedMarkers(canonicalConfirmed);
        setDeletedMarkers(canonicalDeleted);
        setDirtyMarkers(new Set());
        setReport(response);
        setConflicts([]);
      } catch (err) {
        if (reportEditRevisionRef.current !== reportEditRevision) return;
        const apiError = err instanceof ApiError ? err : null;
        const nextConflicts = conflictsFromDetails(apiError?.details);
        if (apiError?.status === 409 && nextConflicts.length) {
          setConflicts(nextConflicts);
          setError("Conflits profil: confirmez l'ecrasement pour reporter.");
          return;
        }
        throw err;
      }
    });
  };

  return (
    <main className="app-shell">
      <header className="top-header">
        <div>
          <p className="eyebrow">Enduraw local</p>
          <h1>Lecture MetaSoft</h1>
          <p>{match.profile_name} / {match.xml_filename}</p>
        </div>
        <div className="header-badges">
          <span><FileUp size={15} />{analysis.file.filename}</span>
          <span className="ok-badge"><CheckCircle2 size={15} />Analyse locale OK</span>
          {warnings.length > 0 && <span className="warn-badge"><AlertTriangle size={15} />{warnings.length} warnings</span>}
        </div>
      </header>

      <nav className="sticky-nav">
        <div className="nav-buttons">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.label}
              type="button"
              onClick={() => document.getElementById(item.targetId)?.scrollIntoView({ behavior: "smooth", block: "start" })}
            >
              {item.label}
            </button>
          ))}
        </div>
        <label className="range-control">
          <SlidersHorizontal size={15} />
          Lissage
          <input
            type="range"
            min={0}
            max={60}
            step={5}
            value={smoothingSeconds}
            onChange={(event) => setSmoothingSeconds(Number(event.target.value))}
          />
          <span>{smoothingSeconds}s</span>
        </label>
        <button
          type="button"
          className={showSpeedBands ? "nav-toggle active" : "nav-toggle"}
          onClick={() => setShowSpeedBands((current) => !current)}
          aria-pressed={showSpeedBands}
        >
          Paliers vitesse
        </button>
        <div className="phase-filter">
          {["Tout", ...phases].map((phase) => (
            <button
              key={phase}
              type="button"
              onClick={() => setPhaseFilter(phase)}
              className={phaseFilter === phase ? "active" : ""}
            >
              {phase}
            </button>
          ))}
        </div>
      </nav>

      <section id="metasoft-reading" className="section-block reading-section">
        <div className="section-head reading-section-head">
          <div>
            <h2>Lecture</h2>
            <p>{readingViewMode === "all" ? "Tous les graphes de lecture visibles." : "Graphe principal pour travailler au calme."}</p>
          </div>
          <div className="view-mode-toggle" aria-label="Mode de vue lecture">
            <button
              type="button"
              className={readingViewMode === "all" ? "active" : ""}
              onClick={() => setReadingViewMode("all")}
              aria-pressed={readingViewMode === "all"}
            >
              Tout
            </button>
            <button
              type="button"
              className={readingViewMode === "focus" ? "active" : ""}
              onClick={() => setReadingViewMode("focus")}
              aria-pressed={readingViewMode === "focus"}
            >
              Focus
            </button>
          </div>
        </div>
        {readingViewMode === "all" ? (
          <div className="reading-workspace">
            <div className="charts-grid">
              {READING_GRAPH_CONFIGS.map((graph) => renderReadingChart(graph))}
            </div>
            <CursorRail analysis={analysis} cursorPoint={cursorPoint} />
          </div>
        ) : (
          <div className="reading-workspace">
            <div className="reading-main">
              {selectedReadingGraph && renderReadingChart(selectedReadingGraph, 430)}
              <div className="graph-picker" aria-label="Choisir le graphe principal">
                {READING_GRAPH_CONFIGS.map((graph) => (
                  <button
                    key={graph.id}
                    type="button"
                    className={graph.id === selectedReadingGraph?.id ? "graph-picker-button active" : "graph-picker-button"}
                    onClick={() => setSelectedReadingGraphId(graph.id)}
                    aria-pressed={graph.id === selectedReadingGraph?.id}
                  >
                    <span>{graph.title}</span>
                    <small>{graph.kind === "time" ? "Temps" : "Relation"}</small>
                  </button>
                ))}
              </div>
            </div>
            <CursorRail analysis={analysis} cursorPoint={cursorPoint} />
          </div>
        )}
      </section>

      <section id="metasoft-markers" className="section-block">
        <MarkerPanel
          draftMarkers={draftMarkers}
          confirmedMarkers={confirmedMarkers}
          dirtyMarkers={dirtyMarkers}
          deletedMarkers={deletedMarkers}
          profileVo2maxMlKgMin={profileVo2maxMlKgMin}
        />
      </section>

      <RunningEconomyManualSection
        ref={manualEconomyRef}
        analysis={analysis}
        profileVo2maxMlKgMin={markerVo2maxMlKgMin}
        initialManualEconomy={payload.manual_running_economy}
        onDraftChange={markManualEconomyDirty}
        onReportSummaryChange={setManualEconomyReportSummary}
      />

      <AnalysisExportSection
        busy={busy}
        error={error}
        report={report}
        conflicts={conflicts}
        markerSummary={markerReportSummary}
        manualEconomySummary={manualEconomyReportSummary}
        warnings={[...analysis.warnings, ...warnings]}
        onReport={() => void reportProfile(false)}
        onReportOverwrite={() => void reportProfile(true)}
      />
    </main>
  );

  async function runOfficialAction(label: string, action: () => Promise<void>) {
    setBusy(label);
    setError(null);
    try {
      await action();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }
}

function errorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  return "Action MetaSoft impossible.";
}

function profileMeasuredVo2max(profile: Record<string, unknown>): number | null {
  const stress = profile.stress_test_results;
  if (!stress || typeof stress !== "object") return null;
  const value = (stress as { measured_vo2max?: unknown }).measured_vo2max;
  return typeof value === "number" && Number.isFinite(value) && value > 0 ? value : null;
}

function currentMarkerVo2maxMlKgMin(
  draftMarkers: DraftMarkers,
  confirmedMarkers: ConfirmedMarkers,
  dirtyMarkers: Set<MetaSoftMarkerName>,
  deletedMarkers: Set<MetaSoftMarkerName>,
  fallback: number | null,
): number | null {
  if (dirtyMarkers.has("VO2_max")) {
    return positiveNumber(draftMarkers.VO2_max.values.vo2_ml_kg_min);
  }
  if (confirmedMarkers.VO2_max) {
    return positiveNumber(confirmedMarkers.VO2_max.values.vo2_ml_kg_min);
  }
  if (deletedMarkers.has("VO2_max")) return null;
  const marker = draftMarkers.VO2_max;
  const value = marker.values.vo2_ml_kg_min;
  return typeof value === "number" && Number.isFinite(value) && value > 0 ? value : fallback;
}

function positiveNumber(value: number | null | undefined): number | null {
  return typeof value === "number" && Number.isFinite(value) && value > 0 ? value : null;
}

function buildMarkerReportSummary(
  draftMarkers: DraftMarkers,
  confirmedMarkers: ConfirmedMarkers,
  dirtyMarkers: Set<MetaSoftMarkerName>,
  deletedMarkers: Set<MetaSoftMarkerName>,
): MarkerReportSummaryItem[] {
  return MARKER_NAMES.map((name) => {
    const draft = draftMarkers[name];
    const confirmed = confirmedMarkers[name];
    const dirty = dirtyMarkers.has(name);
    const official = confirmed && !dirty ? confirmed : null;
    const deleted = deletedMarkers.has(name) && !dirty;
    const row = official ?? draft;
    const status = dirty ? "A reporter" : official ? "Officiel" : deleted ? "Supprimé" : "Brouillon";
    return {
      name: name === "VO2_max" ? "VO2max" : name,
      status,
      time: secondsToClock(row.t_seconds),
      window: row.window_start_seconds === null || row.window_end_seconds === null
        ? "-"
        : `${secondsToClock(row.window_start_seconds)} - ${secondsToClock(row.window_end_seconds)}`,
      fc: formatNumber(row.values.fc_bpm, 0),
      vo2kg: formatNumber(row.values.vo2_ml_kg_min, 1),
      speed: formatNumber(row.values.speed_kmh, 1),
    };
  });
}

function sameCursorPoint(left: MetaSoftPoint | null, right: MetaSoftPoint | null): boolean {
  return (left?.index ?? null) === (right?.index ?? null);
}

function sameRange(left: [number, number], right: [number, number] | null): boolean {
  if (!right) return false;
  return Math.abs(left[0] - right[0]) < 0.25 && Math.abs(left[1] - right[1]) < 0.25;
}

function debugZoom(message: string, payload: Record<string, unknown>): void {
  if (!DEBUG_ZOOM) return;
  // eslint-disable-next-line no-console
  console.info(`[metasoft zoom] ${message}`, payload);
}

function conflictsFromDetails(details: unknown): ProfileConflict[] {
  if (!details || typeof details !== "object" || !("conflicts" in details)) return [];
  const conflicts = (details as { conflicts?: unknown }).conflicts;
  if (!Array.isArray(conflicts)) return [];
  return conflicts.filter(isProfileConflict);
}

function isProfileConflict(value: unknown): value is ProfileConflict {
  return Boolean(
    value
    && typeof value === "object"
    && typeof (value as { path?: unknown }).path === "string"
    && "current" in value
    && "incoming" in value,
  );
}
