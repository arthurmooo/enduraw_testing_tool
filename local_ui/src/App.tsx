import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, FileUp, SlidersHorizontal } from "lucide-react";
import { AnalysisExportSection } from "./components/AnalysisExportSection";
import { CursorRail } from "./components/CursorRail";
import { MarkerPanel } from "./components/MarkerPanel";
import { MetaSoftChart } from "./components/MetaSoftChart";
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
  ReportPreviewResponse,
  ReportResponse,
} from "./types/metasoft";

const NAV_ITEMS = [
  { label: "Lecture", targetId: "metasoft-reading" },
  { label: "Marqueurs", targetId: "metasoft-markers" },
  { label: "Analyse", targetId: "metasoft-analysis-export" },
  { label: "Report", targetId: "metasoft-profile-report" },
];
const READING_GRAPH_CONFIGS = GRAPH_CONFIGS.filter((graph) => graph.source === "points");

export default function App() {
  const [bootstrap, setBootstrap] = useState<{ matchId: string; token: string } | null>(null);
  const [payload, setPayload] = useState<LocalAnalysisPayload | null>(null);
  const [draftMarkers, setDraftMarkers] = useState<DraftMarkers | null>(null);
  const [confirmedMarkers, setConfirmedMarkers] = useState<ConfirmedMarkers>({});
  const [dirtyMarkers, setDirtyMarkers] = useState<Set<MetaSoftMarkerName>>(new Set());
  const [phaseFilter, setPhaseFilter] = useState("Tout");
  const [smoothingSeconds, setSmoothingSeconds] = useState(20);
  const [cursorPoint, setCursorPoint] = useState<MetaSoftPoint | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<ReportPreviewResponse | null>(null);
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [conflicts, setConflicts] = useState<ProfileConflict[]>([]);
  const cursorFrameRef = useRef<number | null>(null);
  const cursorPointRef = useRef<MetaSoftPoint | null>(null);
  const pendingCursorPointRef = useRef<MetaSoftPoint | null>(null);

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
        setPhaseFilter("Tout");
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

  const flushCursorPoint = useCallback(() => {
    cursorFrameRef.current = null;
    const next = pendingCursorPointRef.current;
    if (sameCursorPoint(cursorPointRef.current, next)) return;
    cursorPointRef.current = next;
    setCursorPoint(next);
  }, []);

  const handleCursorPoint = useCallback((point: MetaSoftPoint | null) => {
    const current = cursorFrameRef.current !== null ? pendingCursorPointRef.current : cursorPointRef.current;
    if (sameCursorPoint(current, point)) return;
    pendingCursorPointRef.current = point;
    if (cursorFrameRef.current !== null) return;
    cursorFrameRef.current = window.requestAnimationFrame(flushCursorPoint);
  }, [flushCursorPoint]);

  const markDirty = useCallback((marker: MetaSoftMarkerName) => {
    setDirtyMarkers((current) => new Set(current).add(marker));
    setPreview(null);
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

  const officializeMarkers = async () => {
    await runOfficialAction("Sauvegarde", async () => {
      const response = await apiPost<{ ok: true; markers: ConfirmedMarkers }>(
        `/api/matches/${match.match_id}/markers/officialize`,
        bootstrap?.token ?? "",
        { marker_selections: serializeMarkerSelections(draftMarkers) },
      );
      acceptConfirmedMarkers(response.markers);
    });
  };

  const previewReport = async () => {
    await runOfficialAction("Preview", async () => {
      const response = await apiPost<ReportPreviewResponse>(
        `/api/matches/${match.match_id}/profile/report-preview`,
        bootstrap?.token ?? "",
        { marker_selections: serializeMarkerSelections(draftMarkers) },
      );
      setPreview(response);
      setConflicts(response.conflicts);
      acceptConfirmedMarkers(response.confirmed_markers);
    });
  };

  const reportProfile = async (overwrite = false) => {
    await runOfficialAction(overwrite ? "Overwrite" : "Report", async () => {
      try {
        const response = await apiPost<ReportResponse>(
          `/api/matches/${match.match_id}/profile/report`,
          bootstrap?.token ?? "",
          {
            marker_selections: serializeMarkerSelections(draftMarkers),
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
              key={graph.id}
              analysis={analysis}
              graph={graph}
              markers={draftMarkers}
              phaseFilter={phaseFilter}
              smoothingSeconds={smoothingSeconds}
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
          saving={busy === "Sauvegarde"}
          onSave={() => void officializeMarkers()}
        />
      </section>

      <AnalysisExportSection
        analysis={analysis}
        busy={busy}
        error={error}
        preview={preview}
        report={report}
        conflicts={conflicts}
        onPreview={() => void previewReport()}
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

function sameCursorPoint(left: MetaSoftPoint | null, right: MetaSoftPoint | null): boolean {
  return (left?.index ?? null) === (right?.index ?? null);
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
