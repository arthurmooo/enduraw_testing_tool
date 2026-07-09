import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, FileUp, SlidersHorizontal } from "lucide-react";
import { AnalysisExportSection } from "./components/AnalysisExportSection";
import { CursorRail } from "./components/CursorRail";
import { MarkerPanel } from "./components/MarkerPanel";
import { MetaSoftChart } from "./components/MetaSoftChart";
import { RunningEconomyManualSection, type RunningEconomyManualHandle } from "./components/RunningEconomyManualSection";
import { GRAPH_CONFIGS } from "./lib/graphConfig";
import { ApiError, apiGet, apiPost, getBootstrap } from "./lib/localApi";
import { buildDraftMarker, createInitialMarkers, serializeMarkerSelections } from "./lib/markerUtils";
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
  { label: "Analyse", targetId: "metasoft-analysis-export" },
  { label: "EC", targetId: "metasoft-running-economy" },
  { label: "Report", targetId: "metasoft-profile-report" },
];
const READING_GRAPH_CONFIGS = GRAPH_CONFIGS.filter((graph) => graph.source === "points");
const DEBUG_ZOOM = new URLSearchParams(window.location.search).get("debugZoom") === "1";

export default function App() {
  const [bootstrap, setBootstrap] = useState<{ matchId: string; token: string } | null>(null);
  const [payload, setPayload] = useState<LocalAnalysisPayload | null>(null);
  const [draftMarkers, setDraftMarkers] = useState<DraftMarkers | null>(null);
  const [confirmedMarkers, setConfirmedMarkers] = useState<ConfirmedMarkers>({});
  const [dirtyMarkers, setDirtyMarkers] = useState<Set<MetaSoftMarkerName>>(new Set());
  const [phaseFilter, setPhaseFilter] = useState("Tout");
  const [smoothingSeconds, setSmoothingSeconds] = useState(20);
  const [showSpeedBands, setShowSpeedBands] = useState(true);
  const [timeXRange, setTimeXRange] = useState<[number, number] | null>(null);
  const [timeZoomResetRevision, setTimeZoomResetRevision] = useState(0);
  const [fullscreenGraphId, setFullscreenGraphId] = useState<string | null>(null);
  const [cursorPoint, setCursorPoint] = useState<MetaSoftPoint | null>(null);
  const [cursorSourceGraphId, setCursorSourceGraphId] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [conflicts, setConflicts] = useState<ProfileConflict[]>([]);
  const manualEconomyRef = useRef<RunningEconomyManualHandle | null>(null);
  const ignoreTimeRelayoutUntilRef = useRef(0);
  const timeXRangeRef = useRef<[number, number] | null>(null);
  const blockedResetRangeRef = useRef<[number, number] | null>(null);
  const lastZoomSourceGraphIdRef = useRef<string | null>(null);
  const blockedResetGraphIdRef = useRef<string | null>(null);
  const cursorFrameRef = useRef<number | null>(null);
  const cursorPointRef = useRef<MetaSoftPoint | null>(null);
  const pendingCursorPointRef = useRef<MetaSoftPoint | null>(null);
  const cursorSourceGraphIdRef = useRef<string | null>(null);

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
        setPayload(result);
        setDraftMarkers(createInitialMarkers(result.analysis));
        cursorPointRef.current = firstPoint;
        pendingCursorPointRef.current = firstPoint;
        setCursorPoint(firstPoint);
        cursorSourceGraphIdRef.current = null;
        setCursorSourceGraphId(null);
        setPhaseFilter("Tout");
        timeXRangeRef.current = null;
        blockedResetRangeRef.current = null;
        lastZoomSourceGraphIdRef.current = null;
        blockedResetGraphIdRef.current = null;
        setFullscreenGraphId(null);
        setTimeXRange(null);
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

  const updateCursorSourceGraphId = useCallback((graphId: string | null) => {
    if (cursorSourceGraphIdRef.current === graphId) return;
    cursorSourceGraphIdRef.current = graphId;
    setCursorSourceGraphId(graphId);
  }, []);

  const handleCursorPoint = useCallback((graphId: string, point: MetaSoftPoint | null) => {
    updateCursorSourceGraphId(point ? graphId : null);
    const current = cursorFrameRef.current !== null ? pendingCursorPointRef.current : cursorPointRef.current;
    if (sameCursorPoint(current, point)) return;
    pendingCursorPointRef.current = point;
    if (cursorFrameRef.current !== null) return;
    cursorFrameRef.current = window.requestAnimationFrame(flushCursorPoint);
  }, [flushCursorPoint, updateCursorSourceGraphId]);

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
    setDirtyMarkers((current) => new Set(current).add(marker));
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
    profileVo2maxMlKgMin,
  );

  const reportProfile = async (overwrite = false) => {
    await runOfficialAction(overwrite ? "Overwrite" : "Report", async () => {
      try {
        const markerSelections = serializeMarkerSelections(draftMarkers);
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
        setReport(response);
        setConflicts([]);
        acceptConfirmedMarkers(response.confirmed_markers);
      } catch (err) {
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
          <span className="ok-badge"><CheckCircle2 size={15} />Analyse Python</span>
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

      <section id="metasoft-reading" className="section-block reading-grid">
        <div className="charts-grid">
          {READING_GRAPH_CONFIGS.map((graph) => (
            <MetaSoftChart
              key={graph.kind === "time" ? `${graph.id}-${timeRangeKey}` : graph.id}
              analysis={analysis}
              graph={graph}
              markers={draftMarkers}
              phaseFilter={phaseFilter}
              smoothingSeconds={smoothingSeconds}
              showSpeedBands={showSpeedBands}
              timeXRange={graph.kind === "time" ? timeXRange : null}
              timeZoomResetRevision={graph.kind === "time" ? timeZoomResetRevision : 0}
              cursorPoint={graph.kind === "time" ? cursorPoint : null}
              cursorSourceGraphId={graph.kind === "time" ? cursorSourceGraphId : null}
              fullscreen={fullscreenGraphId === graph.id}
              onFullscreenChange={(open) => setFullscreenGraphId(open ? graph.id : null)}
              onTimeXRangeChange={graph.kind === "time" ? handleTimeXRangeChange : undefined}
              onCursorPoint={handleCursorPoint}
              onPlaceMarker={placeMarker}
              onDeleteMarker={deleteMarker}
            />
          ))}
        </div>
        <CursorRail analysis={analysis} cursorPoint={cursorPoint} />
      </section>

      <section id="metasoft-markers" className="section-block">
        <MarkerPanel
          draftMarkers={draftMarkers}
          confirmedMarkers={confirmedMarkers}
          dirtyMarkers={dirtyMarkers}
          profileVo2maxMlKgMin={profileVo2maxMlKgMin}
        />
      </section>

      <RunningEconomyManualSection
        ref={manualEconomyRef}
        analysis={analysis}
        profileVo2maxMlKgMin={markerVo2maxMlKgMin}
        initialManualEconomy={payload.manual_running_economy}
      />

      <AnalysisExportSection
        busy={busy}
        error={error}
        report={report}
        conflicts={conflicts}
        onReport={() => void reportProfile(false)}
        onReportOverwrite={() => void reportProfile(true)}
      />
    </main>
  );

  function acceptConfirmedMarkers(markers: ConfirmedMarkers) {
    setConfirmedMarkers(markers);
    setDirtyMarkers(new Set());
  }

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
  fallback: number | null,
): number | null {
  const marker = dirtyMarkers.has("VO2_max")
    ? draftMarkers.VO2_max
    : confirmedMarkers.VO2_max ?? draftMarkers.VO2_max;
  const value = marker.values.vo2_ml_kg_min;
  return typeof value === "number" && Number.isFinite(value) && value > 0 ? value : fallback;
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
