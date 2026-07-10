import { AlertTriangle, Send } from "lucide-react";
import type { ManualEconomyReportSummary } from "./RunningEconomyManualSection";
import type {
  MetaSoftWarning,
  ProfileConflict,
  ReportResponse,
} from "../types/metasoft";

export interface MarkerReportSummaryItem {
  name: string;
  status: "Brouillon" | "A reporter" | "Officiel" | "Supprimé";
  time: string;
  window: string;
  fc: string;
  vo2kg: string;
  speed: string;
}

export function AnalysisExportSection({
  busy,
  error,
  report,
  conflicts,
  markerSummary,
  manualEconomySummary,
  warnings,
  onReport,
  onReportOverwrite,
}: {
  busy: string | null;
  error: string | null;
  report: ReportResponse | null;
  conflicts: ProfileConflict[];
  markerSummary: MarkerReportSummaryItem[];
  manualEconomySummary: ManualEconomyReportSummary | null;
  warnings: MetaSoftWarning[];
  onReport: () => void;
  onReportOverwrite: () => void;
}) {
  return (
    <section id="metasoft-analysis-export" className="section-block">
      <div className="section-head">
        <h2>Analyse</h2>
        <p>Reporter au profil sauvegarde automatiquement les marqueurs et l'EC manuelle.</p>
      </div>
      <div className="analysis-grid report-only-grid">
        <section id="metasoft-profile-report" className="panel action-panel">
          <div className="panel-title-row">
            <h2>Report profil</h2>
            {busy && <span className="status-muted">{busyLabel(busy)}</span>}
          </div>
          <ReportSummary
            markerSummary={markerSummary}
            manualEconomySummary={manualEconomySummary}
            warnings={warnings}
          />
          <div className="action-stack">
            <button type="button" className="primary-button" onClick={onReport} disabled={Boolean(busy)}>
              <Send size={16} />
              Reporter au profil
            </button>
            {conflicts.length > 0 && (
              <button type="button" className="danger-button" onClick={onReportOverwrite} disabled={Boolean(busy)}>
                Ecraser les champs en conflit
              </button>
            )}
          </div>
          {error && <p className="error-text">{error}</p>}
          {report && (
            <div className="result-box">
              <strong>Profil mis a jour</strong>
              <p>{report.profile_name}</p>
              <p>{report.updated_paths.length ? report.updated_paths.join(", ") : "Aucun champ modifie."}</p>
            </div>
          )}
          {conflicts.length > 0 && (
            <div className="conflict-box">
              <strong>Conflits profil</strong>
              {conflicts.map((conflict) => (
                <p key={conflict.path}>
                  <AlertTriangle size={13} />
                  {conflict.path}: actuel {String(conflict.current)} / entrant {String(conflict.incoming)}
                </p>
              ))}
            </div>
          )}
        </section>
      </div>
    </section>
  );
}

function ReportSummary({
  markerSummary,
  manualEconomySummary,
  warnings,
}: {
  markerSummary: MarkerReportSummaryItem[];
  manualEconomySummary: ManualEconomyReportSummary | null;
  warnings: MetaSoftWarning[];
}) {
  const blockingWarnings = warnings.filter((warning) => warning.blocking === true);
  const nonBlockingCount = warnings.length - blockingWarnings.length;
  return (
    <div className="report-summary">
      <div className="summary-block">
        <div className="summary-block-head">
          <strong>Marqueurs officialises</strong>
          <span className="status-muted">{markerSummary.length}</span>
        </div>
        <div className="summary-list">
          {markerSummary.map((marker) => (
            <div key={marker.name} className="summary-row">
              <div>
                <strong>{marker.name}</strong>
                <span>{marker.time} / {marker.window}</span>
              </div>
              <div>
                <span className={statusClass(marker.status)}>{marker.status}</span>
                <span>FC {marker.fc} / VO2/kg {marker.vo2kg} / {marker.speed} km/h</span>
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="summary-block">
        <div className="summary-block-head">
          <strong>EC manuelle</strong>
          {manualEconomySummary ? (
            <span className="status-muted">
              {manualEconomySummary.includedCount} inclus / {manualEconomySummary.excludedCount} ecartes
            </span>
          ) : (
            <span className="status-muted">Indisponible</span>
          )}
        </div>
        <div className="summary-list compact">
          {manualEconomySummary?.rows.map((row) => (
            <div key={row.stageIndex} className={row.enabled ? "summary-row" : "summary-row muted"}>
              <div>
                <strong>Palier {row.stageIndex}</strong>
                <span>{row.speed} km/h / {row.bounds}</span>
              </div>
              <div>
                <span className={row.enabled ? "status-ok" : "status-muted"}>{row.enabled ? "Inclus" : "Ecarte"}</span>
                <span>EC {row.ec} / {row.pointCount} pts</span>
              </div>
            </div>
          )) ?? <p className="panel-note">Aucun palier EC disponible.</p>}
        </div>
      </div>
      <div className="summary-block">
        <div className="summary-block-head">
          <strong>Warnings</strong>
          <span className={blockingWarnings.length ? "status-warn" : "status-ok"}>
            {blockingWarnings.length} critiques
          </span>
        </div>
        {blockingWarnings.length > 0 ? (
          <>
            <div className="warning-list compact">
              {blockingWarnings.map((warning, index) => (
                <p key={`${warning.code ?? "blocking"}-${index}`}>
                  <AlertTriangle size={13} />
                  {warning.message}
                </p>
              ))}
            </div>
            <p className="panel-note">{nonBlockingCount} warnings non bloquants.</p>
          </>
        ) : (
          <p className="panel-note">{nonBlockingCount} warnings non bloquants.</p>
        )}
      </div>
    </div>
  );
}

function statusClass(status: MarkerReportSummaryItem["status"]): string {
  if (status === "Officiel") return "status-ok";
  if (status === "Supprimé") return "status-muted";
  if (status === "A reporter") return "status-warn";
  return "status-muted";
}

function busyLabel(value: string): string {
  if (value === "Report") return "Report en cours";
  if (value === "Overwrite") return "Ecrasement en cours";
  return value;
}
