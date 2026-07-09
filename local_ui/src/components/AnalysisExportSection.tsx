import { AlertTriangle, Send } from "lucide-react";
import type {
  ProfileConflict,
  ReportResponse,
} from "../types/metasoft";

export function AnalysisExportSection({
  busy,
  error,
  report,
  conflicts,
  onReport,
  onReportOverwrite,
}: {
  busy: string | null;
  error: string | null;
  report: ReportResponse | null;
  conflicts: ProfileConflict[];
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

function busyLabel(value: string): string {
  if (value === "Report") return "Report en cours";
  if (value === "Overwrite") return "Ecrasement en cours";
  return value;
}
