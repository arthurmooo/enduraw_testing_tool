import {
  forwardRef,
  memo,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
} from "react";
import Plot from "react-plotly.js";
import { Minus, Plus, RotateCcw, Scissors, Trash2 } from "lucide-react";
import { formatNumber, secondsToClock } from "../lib/markerUtils";
import { scaledAxisRange } from "../lib/metasoftChartHelpers";
import { speedSegmentsForAnalysis } from "../lib/chartUtils";
import {
  buildManualEconomyPreviewRow,
  buildManualRestPreview,
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
  ManualRunningEconomyRestBaseline,
  ManualRunningEconomyRestSelection,
  ManualRunningEconomyRow,
  MetaSoftDraftPayload,
  MetaSoftAnalysis,
  MetaSoftPoint,
  MetaSoftWarmupStage,
} from "../types/metasoft";

interface Props {
  analysis: MetaSoftAnalysis;
  profileVo2maxMlKgMin: number | null;
  initialManualEconomy?: ManualRunningEconomyPayload | null;
  initialDraft?: MetaSoftDraftPayload | null;
  onDraftChange: () => void;
  onReportSummaryChange?: (summary: ManualEconomyReportSummary | null) => void;
}

export interface ManualEconomyReportSummary {
  includedCount: number;
  excludedCount: number;
  rows: Array<{
    stageIndex: number;
    enabled: boolean;
    speed: string;
    bounds: string;
    pointCount: number;
    ec: string;
    warning: string | null;
  }>;
}

export interface RunningEconomyManualHandle {
  reportPayload: () => {
    manual_running_economy_selections: ManualRunningEconomySelection[];
    manual_running_economy_stage_selections: ManualRunningEconomyStageSelection[];
    manual_running_economy_rest_selection: ManualRunningEconomyRestSelection;
  } | null;
}

export const RunningEconomyManualSection = memo(forwardRef<RunningEconomyManualHandle, Props>(function RunningEconomyManualSection({
  analysis,
  profileVo2maxMlKgMin,
  initialManualEconomy,
  initialDraft,
  onDraftChange,
  onReportSummaryChange,
}: Props, ref) {
  const detectedStages = useMemo(
    () => analysis.warmup_stages.filter(hasStageBounds).map((stage) => ({ ...stage, source: "detected" as const })),
    [analysis.warmup_stages],
  );
  const restStage = useMemo(() => restSelectionStage(analysis), [analysis]);
  const [manualStages, setManualStages] = useState<MetaSoftWarmupStage[]>([]);
  const stableStages = useMemo(() => [...detectedStages, ...manualStages], [detectedStages, manualStages]);
  const selectableStages = useMemo(() => speedSegmentsForAnalysis(analysis).filter(isSelectableEconomyStage), [analysis]);
  const workStages = useMemo(
    () => restStage ? [restStage, ...stableStages] : stableStages,
    [restStage, stableStages],
  );
  const [selectedStageIndex, setSelectedStageIndex] = useState(restStage?.stage_index ?? detectedStages[0]?.stage_index ?? 0);
  const [drafts, setDrafts] = useState<Record<number, ManualEconomyDraft>>({});
  const [activeExclusionIndex, setActiveExclusionIndex] = useState<number | null>(null);
  const [excludeMode, setExcludeMode] = useState(false);
  const [xRange, setXRange] = useState<[number, number] | null>(null);
  const [plotResetRevision, setPlotResetRevision] = useState(0);
  const ignoreRelayoutUntilRef = useRef(0);
  const [stagePickerOpen, setStagePickerOpen] = useState(false);
  const [selectedStageKeys, setSelectedStageKeys] = useState<Set<string>>(new Set());
  const [saveStatus, setSaveStatus] = useState<string | null>(null);
  const [savedManualEconomy, setSavedManualEconomy] = useState<ManualRunningEconomyPayload | null>(initialManualEconomy ?? null);
  const [dirtyStageIndexes, setDirtyStageIndexes] = useState<Set<number>>(new Set());
  const selectedStage = useMemo(
    () => workStages.find((stage) => stage.stage_index === selectedStageIndex) ?? workStages[0] ?? null,
    [selectedStageIndex, workStages],
  );

  useEffect(() => {
    setSavedManualEconomy(initialManualEconomy ?? null);
    setDirtyStageIndexes(new Set());
    const savedRows = new Map((initialManualEconomy?.rows ?? []).map((row) => [row.stage_index, row]));
    const savedStageSelections = new Map(
      (initialManualEconomy?.stage_selections ?? []).map((item) => [item.stage_index, item.enabled]),
    );
    const draftSelections = new Map(
      (initialDraft?.manual_running_economy_selections ?? []).map((item) => [item.stage_index, item]),
    );
    const draftStageSelections = new Map(
      (initialDraft?.manual_running_economy_stage_selections ?? []).map((item) => [item.stage_index, item.enabled]),
    );
    const hasSavedManualEconomy = Boolean(initialManualEconomy);
    const manualSelections = [
      ...(initialDraft?.manual_running_economy_selections ?? []),
      ...(initialManualEconomy?.rows ?? [])
        .filter((row) => row.sources?.selection === "manual_free_zone")
        .map((row) => ({ ...row, source: "manual" as const })),
    ].filter((item, index, items) => (
      item.source === "manual" && items.findIndex((candidate) => candidate.stage_index === item.stage_index) === index
    ));
    const restoredManualStages = manualSelections.map((item) => manualSelectionStage(analysis, item));
    setManualStages(restoredManualStages);
    const economyStages = [...detectedStages, ...restoredManualStages];
    const nextDrafts = Object.fromEntries(economyStages.map((stage) => {
      const saved = savedRows.get(stage.stage_index);
      const restoredDraft = draftSelections.get(stage.stage_index);
      const draft = restoredDraft
        ? draftFromSelection(restoredDraft)
        : saved ? draftFromSavedRow(saved) : initialEconomyDraft(stage);
      draft.enabled = draftStageSelections.get(stage.stage_index)
        ?? savedStageSelections.get(stage.stage_index)
        ?? (saved ? true : !hasSavedManualEconomy);
      return [stage.stage_index, clampDraftToStage(draft, stage)];
    }));
    if (restStage) {
      const restSelection = initialDraft?.manual_running_economy_rest_selection
        ?? initialManualEconomy?.rest_baseline;
      nextDrafts[restStage.stage_index] = hasRestSelection(restSelection)
        ? draftFromRestSelection(restStage, restSelection)
        : initialEconomyDraft(restStage);
    }
    setDrafts(nextDrafts);
    const restoredDirty = new Set([
      ...draftSelections.keys(),
      ...draftStageSelections.keys(),
    ]);
    if (initialDraft?.manual_running_economy_rest_selection) {
      restoredDirty.add(0);
      economyStages.forEach((stage) => restoredDirty.add(stage.stage_index));
    }
    setDirtyStageIndexes(restoredDirty);
    setSelectedStageIndex(restStage?.stage_index ?? economyStages[0]?.stage_index ?? 0);
    setXRange(null);
    setActiveExclusionIndex(null);
    setStagePickerOpen(false);
    setSelectedStageKeys(new Set());
  }, [analysis, detectedStages, initialDraft, initialManualEconomy, restStage]);

  const manualRestBaseline = useMemo<ManualRunningEconomyRestBaseline | null>(() => {
    if (!restStage) return null;
    return buildManualRestPreview(
      analysis.points,
      drafts[restStage.stage_index] ?? initialEconomyDraft(restStage),
    );
  }, [analysis.points, drafts, restStage]);

  const previewRows = useMemo(
    () => stableStages.map((stage) => buildManualEconomyPreviewRow(
      analysis,
      stage,
      drafts[stage.stage_index] ?? initialEconomyDraft(stage),
      profileVo2maxMlKgMin,
      manualRestBaseline,
    )),
    [analysis, drafts, manualRestBaseline, profileVo2maxMlKgMin, stableStages],
  );
  const savedRows = useMemo(
    () => new Map((savedManualEconomy?.rows ?? []).map((row) => [row.stage_index, row])),
    [savedManualEconomy],
  );
  const rows = useMemo(
    () => previewRows.map((row) => (
      dirtyStageIndexes.has(row.stage_index)
        ? row
        : savedRows.get(row.stage_index) ?? row
    )),
    [dirtyStageIndexes, previewRows, savedRows],
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

  const markStageDirty = useCallback((stageIndex: number) => {
    setDirtyStageIndexes((current) => new Set([
      ...current,
      ...(stageIndex === 0 ? stableStages.map((stage) => stage.stage_index) : [stageIndex]),
    ]));
    onDraftChange();
  }, [onDraftChange, stableStages]);

  const updateSelectedDraft = useCallback((updater: (draft: ManualEconomyDraft, stage: MetaSoftWarmupStage) => ManualEconomyDraft) => {
    if (!selectedStage || !selectedDraft) return;
    setDrafts((current) => ({
      ...current,
      [selectedStage.stage_index]: clampDraftToStage(updater(selectedDraft, selectedStage), selectedStage),
    }));
    markStageDirty(selectedStage.stage_index);
    setSaveStatus(null);
  }, [markStageDirty, selectedDraft, selectedStage]);

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
    markStageDirty(selectedStage.stage_index);
    setActiveExclusionIndex(Math.max(0, exclusions.findIndex((item) => start <= item.end_seconds && end >= item.start_seconds)));
    setExcludeMode(false);
    setSaveStatus(null);
  }, [excludeMode, markStageDirty, selectedDraft, selectedStage]);

  const toggleStageEnabled = useCallback((stage: MetaSoftWarmupStage) => {
    const draft = drafts[stage.stage_index] ?? initialEconomyDraft(stage);
    setDrafts((current) => ({
      ...current,
      [stage.stage_index]: clampDraftToStage({ ...draft, enabled: !draft.enabled }, stage),
    }));
    setSelectedStageIndex(stage.stage_index);
    markStageDirty(stage.stage_index);
    setSaveStatus(null);
  }, [drafts, markStageDirty]);

  const handleXRangeChange = useCallback((range: [number, number] | null) => {
    if (Date.now() < ignoreRelayoutUntilRef.current) return;
    setXRange(range);
  }, []);

  const resetPlotZoom = useCallback(() => {
    ignoreRelayoutUntilRef.current = Date.now() + 600;
    setXRange(null);
    setPlotResetRevision((current) => current + 1);
  }, []);

  const addFreeManualStage = useCallback(() => {
    const stageIndex = nextManualStageIndex(stableStages);
    const stage = manualSelectionStage(analysis, { stage_index: stageIndex });
    const draft = initialManualZoneDraft(analysis, stage);
    setManualStages((current) => [...current, stage]);
    setDrafts((current) => ({ ...current, [stageIndex]: draft }));
    setSelectedStageIndex(stageIndex);
    markStageDirty(stageIndex);
    setXRange(null);
  }, [analysis, markStageDirty, stableStages]);

  const addSelectedStages = useCallback(() => {
    const candidates = selectableStages.filter((stage) => (
      selectedStageKeys.has(economyStageKey(stage))
      && !stableStages.some((current) => sameEconomyStage(current, stage))
    ));
    if (!candidates.length) return;
    const firstIndex = nextManualStageIndex(stableStages);
    const additions = candidates.map((stage, index) => ({
      ...stage,
      stage_index: firstIndex + index,
      source: "manual" as const,
    }));
    setManualStages((current) => [...current, ...additions]);
    setDrafts((current) => ({
      ...current,
      ...Object.fromEntries(additions.map((stage) => [stage.stage_index, initialEconomyDraft(stage)])),
    }));
    setDirtyStageIndexes((current) => new Set([...current, ...additions.map((stage) => stage.stage_index)]));
    onDraftChange();
    setSelectedStageIndex(additions[0].stage_index);
    setSelectedStageKeys(new Set());
    setStagePickerOpen(false);
    setXRange(null);
    setSaveStatus(null);
  }, [onDraftChange, selectableStages, selectedStageKeys, stableStages]);

  const removeManualStage = useCallback((stage: MetaSoftWarmupStage) => {
    setManualStages((current) => current.filter((item) => item.stage_index !== stage.stage_index));
    setDrafts((current) => {
      const next = { ...current };
      delete next[stage.stage_index];
      return next;
    });
    setSelectedStageIndex(restStage?.stage_index ?? detectedStages[0]?.stage_index ?? 0);
    markStageDirty(stage.stage_index);
  }, [detectedStages, markStageDirty, restStage]);

  const buildReportPayload = useCallback(() => {
    if (!stableStages.length || !restStage) return null;
    const restDraft = drafts[restStage.stage_index] ?? initialEconomyDraft(restStage);
    const stageSelections = stableStages.map((stage) => manualEconomyStageSelection(
      stage,
      drafts[stage.stage_index] ?? initialEconomyDraft(stage),
    ));
    return {
      manual_running_economy_selections: stableStages
        .map((stage) => manualEconomySelection(
          stage,
          drafts[stage.stage_index] ?? initialEconomyDraft(stage),
        )),
      manual_running_economy_stage_selections: stageSelections,
      manual_running_economy_rest_selection: {
        start_seconds: restDraft.startSeconds,
        end_seconds: restDraft.endSeconds,
        exclusions: restDraft.exclusions,
      },
    };
  }, [drafts, restStage, stableStages]);
  const reportSummary = useMemo<ManualEconomyReportSummary>(() => {
    const summaryRows = rows.map((row) => {
      const stage = stableStages.find((item) => item.stage_index === row.stage_index);
      const draft = stage ? drafts[row.stage_index] ?? initialEconomyDraft(stage) : null;
      return {
        stageIndex: row.stage_index,
        enabled: Boolean(draft?.enabled),
        speed: formatNumber(row.speed_kmh, 1),
        bounds: `${secondsToClock(row.start_seconds)} - ${secondsToClock(row.end_seconds)}`,
        pointCount: row.point_count,
        ec: formatNumber(row.ec_j_kg_m, 2),
        warning: row.warning ?? null,
      };
    });
    return {
      includedCount: summaryRows.filter((row) => row.enabled).length,
      excludedCount: summaryRows.filter((row) => !row.enabled).length,
      rows: summaryRows,
    };
  }, [drafts, rows, stableStages]);

  useEffect(() => {
    onReportSummaryChange?.(stableStages.length ? reportSummary : null);
  }, [onReportSummaryChange, reportSummary, stableStages.length]);

  useImperativeHandle(ref, () => ({
    reportPayload: buildReportPayload,
  }), [buildReportPayload]);

  return (
    <section id="metasoft-running-economy" className="section-block">
      <div className="section-head">
        <h2>EC</h2>
      <p>Repos et zones d'effort choisis manuellement, sauvegardes avec le brouillon.</p>
      </div>
      <div className="ec-workbench">
        <section className="panel ec-chart-panel">
          <div className="panel-title-row">
            <h2>Bornes et artefacts</h2>
            <div className="ec-actions">
              <button
                type="button"
                className={stagePickerOpen ? "secondary-button active-action" : "secondary-button"}
                aria-expanded={stagePickerOpen}
                onClick={() => {
                  setStagePickerOpen((current) => !current);
                  setSelectedStageKeys(new Set());
                }}
              >
                <Plus size={15} /> Ajouter une zone EC
              </button>
              {selectedStage?.source === "manual" && (
                <button type="button" className="secondary-button" onClick={() => removeManualStage(selectedStage)}>
                  <Trash2 size={15} /> Supprimer la zone
                </button>
              )}
              <button
                type="button"
                className={excludeMode ? "secondary-button active-action" : "secondary-button"}
                aria-pressed={excludeMode}
                onClick={() => {
                  setExcludeMode((current) => !current);
                  setActiveExclusionIndex(null);
                }}
              >
                <Scissors size={15} />
                Exclure artefact
              </button>
              {excludeMode && <span className="interaction-hint">Cliquez dans le graphe pour placer l'artefact.</span>}
            </div>
          </div>
          {stagePickerOpen && (
            <div className="ec-stage-picker">
              <div className="ec-stage-picker-head">
                <div>
                  <strong>Choisir les paliers a analyser</strong>
                  <p>Selectionnez un ou plusieurs paliers. Chaque zone gardera ses propres bornes et exclusions.</p>
                </div>
                <button
                  type="button"
                  className="table-icon-button"
                  onClick={() => setSelectedStageKeys(new Set(
                    selectableStages
                      .filter((stage) => !stableStages.some((current) => sameEconomyStage(current, stage)))
                      .map(economyStageKey),
                  ))}
                >
                  Tout selectionner
                </button>
              </div>
              <div className="ec-stage-options">
                {selectableStages.map((stage) => {
                  const key = economyStageKey(stage);
                  const alreadyAdded = stableStages.some((current) => sameEconomyStage(current, stage));
                  const selected = alreadyAdded || selectedStageKeys.has(key);
                  return (
                    <label className={[
                      "ec-stage-option",
                      selected ? "selected" : "",
                      alreadyAdded ? "already-added" : "",
                    ].filter(Boolean).join(" ")} key={key}>
                      <input
                        type="checkbox"
                        checked={selected}
                        disabled={alreadyAdded}
                        onChange={() => setSelectedStageKeys((current) => {
                          const next = new Set(current);
                          if (next.has(key)) next.delete(key);
                          else next.add(key);
                          return next;
                        })}
                      />
                      <span>
                        <strong>{formatNumber(stage.speed_kmh, 1)} km/h</strong>
                        <small>{stage.phase || "Phase non renseignee"} · {secondsToClock(stage.start_seconds)} - {secondsToClock(stage.end_seconds)}</small>
                      </span>
                      {alreadyAdded && <em>Deja ajoute</em>}
                    </label>
                  );
                })}
                {!selectableStages.length && <p className="panel-note">Aucun palier stable d'au moins 30 s detecte dans ce test.</p>}
              </div>
              <div className="ec-stage-picker-actions">
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => {
                    addFreeManualStage();
                    setStagePickerOpen(false);
                    setSelectedStageKeys(new Set());
                  }}
                >
                  Ajouter une zone libre
                </button>
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => {
                    setStagePickerOpen(false);
                    setSelectedStageKeys(new Set());
                  }}
                >
                  Annuler
                </button>
                <button type="button" className="primary-button" disabled={!selectedStageKeys.size} onClick={addSelectedStages}>
                  {selectedStageKeys.size
                    ? `Ajouter ${selectedStageKeys.size} ${selectedStageKeys.size > 1 ? "paliers" : "palier"}`
                    : "Selectionnez des paliers"}
                </button>
              </div>
            </div>
          )}
          {selectedStage && selectedDraft && (
            <>
              <div className="stage-strip">
                {workStages.map((stage) => (
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
                    <strong>{stage.stage_index === 0 ? "Repos" : stage.source === "manual" ? `Zone ${stage.stage_index - 1000}` : `Palier ${stage.stage_index}`}</strong>
                    <span>{stage.stage_index === 0 ? "reference EC" : `${formatNumber(stage.speed_kmh, 1)} km/h`}</span>
                  </button>
                ))}
              </div>
              <ManualEconomyPlot
                key={`${selectedStage.stage_index}-${plotResetRevision}`}
                points={stagePoints}
                draft={selectedDraft}
                row={selectedRow}
                xRange={xRange}
                onXRangeChange={handleXRangeChange}
                onResetZoom={resetPlotZoom}
                onClick={excludeMode ? handlePlotClick : undefined}
              />
              {selectedStage.stage_index === 0 && (
                <p className={manualRestBaseline ? "panel-note" : "error-text"}>
                  {manualRestBaseline
                    ? `Repos retenu: ${manualRestBaseline.point_count} points VO2/VCO2.`
                    : "Choisissez un repos contenant des points VO2/VCO2 utilisables."}
                </p>
              )}
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
                  onDone={() => setActiveExclusionIndex(null)}
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
            <div className="table-summary">
              <span className="status-ok">{reportSummary.includedCount} inclus</span>
              <span className="status-muted">{reportSummary.excludedCount} ecartes</span>
              <span className="status-muted">J/kg/m</span>
            </div>
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
                    draft.enabled ? "ec-row-included" : "muted-row ec-row-excluded",
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
                      <td>{stage.source === "manual" ? `Zone ${stage.stage_index - 1000}` : row.stage_index}</td>
                      <td>
                        <button
                          type="button"
                          className={draft.enabled ? "table-icon-button status-button status-button-ok" : "table-icon-button status-button"}
                          aria-pressed={draft.enabled}
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
  onResetZoom,
  onClick,
}: {
  points: MetaSoftPoint[];
  draft: ManualEconomyDraft;
  row: ManualRunningEconomyRow | null;
  xRange: [number, number] | null;
  onXRangeChange: (range: [number, number] | null) => void;
  onResetZoom: () => void;
  onClick?: (event: Readonly<{ points?: Array<{ x?: unknown }> }>) => void;
}) {
  const [yScaleFactor, setYScaleFactor] = useState(1);
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
  const yRange = useMemo(() => scaledAxisRange(
    times.flatMap((time, index) => (
      inRange(time, currentRange) ? [vo2Raw[index], vo2Corrected[index], vco2Corrected[index]] : []
    )),
    yScaleFactor,
  ), [currentRange, times, vco2Corrected, vo2Corrected, vo2Raw, yScaleFactor]);
  const y2Range = useMemo(() => scaledAxisRange(
    veCorrected.filter((_value, index) => inRange(times[index], currentRange)),
    yScaleFactor,
  ), [currentRange, times, veCorrected, yScaleFactor]);
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
    hoverlabel: {
      bgcolor: "rgba(6,20,36,0.94)",
      bordercolor: "rgba(248,250,252,0.22)",
      font: { color: "#f8fafc", size: 11 },
    },
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
    yaxis: { title: "L/min", range: yRange, fixedrange: true, gridcolor: "rgba(255,255,255,0.055)" },
    yaxis2: { title: "VE", range: y2Range, fixedrange: true, overlaying: "y", side: "right", gridcolor: "rgba(255,255,255,0)" },
  }), [annotations, currentRange, shapes, tickText, tickVals, y2Range, yRange]);
  const handleRelayout = useCallback((event: Readonly<Record<string, unknown>>) => {
    const nextRange = xRangeFromRelayout(event);
    if (nextRange !== undefined) onXRangeChange(boundedXRange(nextRange, defaultRange));
  }, [defaultRange, onXRangeChange]);
  return (
    <div className="ec-plot-wrap">
      <div className="ec-plot-controls scale-controls">
        <button type="button" onClick={() => setYScaleFactor((value) => Math.min(4, value * 1.25))}><Minus size={14} /></button>
        <button type="button" onClick={() => setYScaleFactor(1)}>Auto</button>
        <button type="button" onClick={() => setYScaleFactor((value) => Math.max(0.35, value * 0.8))}><Plus size={14} /></button>
        {xRange && (
          <button type="button" className="zoom-reset-button" onClick={onResetZoom} title="Reinitialiser le zoom temporel">
            <RotateCcw size={14} /> Reinitialiser
          </button>
        )}
      </div>
      <Plot
        data={data}
        layout={layout}
        config={{ responsive: true, displayModeBar: false, doubleClick: false }}
        style={{ width: "100%", height: 330 }}
        useResizeHandler
        onClick={onClick}
        onRelayout={handleRelayout}
      />
    </div>
  );
});

function ArtifactSliders({
  exclusion,
  index,
  min,
  max,
  onChange,
  onDelete,
  onDone,
}: {
  exclusion: { start_seconds: number; end_seconds: number };
  index: number;
  min: number;
  max: number;
  onChange: (index: number, next: { start_seconds: number; end_seconds: number }) => void;
  onDelete: (index: number) => void;
  onDone: () => void;
}) {
  return (
    <div className="artifact-editor">
      <div className="panel-title-row">
        <strong>Artefact {index + 1}</strong>
        <div className="artifact-editor-actions">
          <button type="button" className="table-icon-button" onClick={onDone}>
            Terminer
          </button>
          <button type="button" className="table-icon-button" onClick={() => onDelete(index)}>
            <Trash2 size={13} />
            Supprimer
          </button>
        </div>
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
    customdata: x.map((time) => (typeof time === "number" && Number.isFinite(time) ? secondsToClock(time) : "")),
    line: { color, width: dash === "solid" ? 1.6 : 1, dash },
    hovertemplate: `<b>${name}</b><br>%{customdata}<br>%{y:.3f}<extra></extra>`,
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

function draftFromSelection(selection: {
  stage_index: number;
  start_seconds: number;
  end_seconds: number;
  exclusions: ManualRunningEconomyRow["exclusions"];
}): ManualEconomyDraft {
  return {
    stageIndex: selection.stage_index,
    enabled: true,
    startSeconds: selection.start_seconds,
    endSeconds: selection.end_seconds,
    exclusions: selection.exclusions,
  };
}

function draftFromRestSelection(
  stage: MetaSoftWarmupStage,
  selection: ManualRunningEconomyRestSelection,
): ManualEconomyDraft {
  return clampDraftToStage({
    stageIndex: stage.stage_index,
    enabled: true,
    startSeconds: selection.start_seconds,
    endSeconds: selection.end_seconds,
    exclusions: selection.exclusions,
  }, stage);
}

function restSelectionStage(analysis: MetaSoftAnalysis): MetaSoftWarmupStage | null {
  const times = analysis.points
    .filter((point) => point.phase === "Repos" && typeof point.t_seconds === "number")
    .map((point) => point.t_seconds as number);
  if (times.length < 2) return null;
  return {
    stage_index: 0,
    speed_kmh: 0,
    start_seconds: Math.min(...times),
    end_seconds: Math.max(...times),
    point_count: times.length,
    source: "detected",
  };
}

function manualSelectionStage(
  analysis: MetaSoftAnalysis,
  selection: { stage_index: number; start_seconds?: number; end_seconds?: number },
): MetaSoftWarmupStage {
  const times = analysis.points
    .map((point) => point.t_seconds)
    .filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  if (!times.length) {
    return { stage_index: selection.stage_index, speed_kmh: 0, start_seconds: 0, end_seconds: 0, point_count: 0, source: "manual" };
  }
  const start = selection.start_seconds ?? Math.min(...times);
  const end = selection.end_seconds ?? Math.max(...times);
  const detectedStage = speedSegmentsForAnalysis(analysis).find((stage) => (
    isSelectableEconomyStage(stage)
    && typeof stage.start_seconds === "number"
    && typeof stage.end_seconds === "number"
    && stage.start_seconds <= start + 2
    && stage.end_seconds >= end - 2
  ));
  if (detectedStage) {
    return { ...detectedStage, stage_index: selection.stage_index, source: "manual" };
  }
  const selectedPoints = analysis.points.filter((point) => (
    typeof point.t_seconds === "number"
    && point.t_seconds >= start
    && point.t_seconds <= end
  ));
  const speeds = selectedPoints
    .map((point) => numeric(point.values.speed_kmh))
    .filter((value): value is number => value !== null);
  return {
    stage_index: selection.stage_index,
    speed_kmh: speeds.length ? speeds.reduce((sum, value) => sum + value, 0) / speeds.length : 0,
    start_seconds: start,
    end_seconds: end,
    point_count: selectedPoints.length,
    source: "manual",
  };
}

function isSelectableEconomyStage(stage: MetaSoftWarmupStage): boolean {
  const phase = normalisePhase(stage.phase);
  return typeof stage.start_seconds === "number"
    && typeof stage.end_seconds === "number"
    && stage.end_seconds - stage.start_seconds >= 30
    && stage.speed_kmh > 0
    && !phase.includes("repos")
    && !phase.includes("recuper")
    && !phase.includes("retabl");
}

function economyStageKey(stage: MetaSoftWarmupStage): string {
  return `${stage.start_seconds}-${stage.end_seconds}-${stage.speed_kmh}`;
}

function sameEconomyStage(left: MetaSoftWarmupStage, right: MetaSoftWarmupStage): boolean {
  return typeof left.start_seconds === "number"
    && typeof left.end_seconds === "number"
    && typeof right.start_seconds === "number"
    && typeof right.end_seconds === "number"
    && Math.abs(left.start_seconds - right.start_seconds) <= 2
    && Math.abs(left.end_seconds - right.end_seconds) <= 2
    && Math.abs(left.speed_kmh - right.speed_kmh) <= 0.2;
}

function normalisePhase(value?: string | null): string {
  return (value ?? "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}

function initialManualZoneDraft(analysis: MetaSoftAnalysis, stage: MetaSoftWarmupStage): ManualEconomyDraft {
  const positivePoints = analysis.points.filter((point) => (
    typeof point.t_seconds === "number" && (numeric(point.values.speed_kmh) ?? 0) > 0
  ));
  const stageStart = stage.start_seconds ?? 0;
  const stageEnd = stage.end_seconds ?? stageStart;
  const start = positivePoints[0]?.t_seconds ?? stageStart;
  return clampDraftToStage({
    stageIndex: stage.stage_index,
    enabled: true,
    startSeconds: Math.min(start ?? stageStart, Math.max(stageStart, stageEnd - 30)),
    endSeconds: Math.min(stageEnd, (start ?? stageStart) + 30),
    exclusions: [],
  }, stage);
}

function nextManualStageIndex(stages: MetaSoftWarmupStage[]): number {
  return Math.max(1000, ...stages.map((stage) => stage.stage_index)) + 1;
}

function hasRestSelection(value: unknown): value is ManualRunningEconomyRestSelection {
  if (!value || typeof value !== "object") return false;
  const selection = value as Partial<ManualRunningEconomyRestSelection>;
  return typeof selection.start_seconds === "number"
    && typeof selection.end_seconds === "number"
    && Array.isArray(selection.exclusions);
}

function hasStageBounds(stage: MetaSoftWarmupStage): boolean {
  return typeof stage.start_seconds === "number"
    && typeof stage.end_seconds === "number"
    && stage.end_seconds > stage.start_seconds;
}

function numeric(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function inRange(value: number | null, range: [number, number]): boolean {
  return typeof value === "number" && value >= range[0] && value <= range[1];
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
