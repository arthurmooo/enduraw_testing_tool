import { useEffect, useState } from "react";
import { AlertTriangle, Eye, EyeOff, FileJson, Send, ShieldCheck } from "lucide-react";
import Plot from "react-plotly.js";
import { formatNumber } from "../lib/markerUtils";
import type {
  ExportResponse,
  MetaSoftAnalysis,
  MetaSoftWarning,
  ProfileConflict,
  ReportPreviewResponse,
  ReportResponse,
} from "../types/metasoft";

export function AnalysisExportSection({
  analysis,
  busy,
  error,
  preview,
  report,
  exportResult,
  conflicts,
  onPreview,
  onReport,
  onReportOverwrite,
  onExport,
}: {
  analysis: MetaSoftAnalysis;
  busy: string | null;
  error: string | null;
  preview: ReportPreviewResponse | null;
  report: ReportResponse | null;
  exportResult: ExportResponse | null;
  conflicts: ProfileConflict[];
  onPreview: () => void;
  onReport: () => void;
  onReportOverwrite: () => void;
  onExport: () => void;
}) {
  const runningEconomy = analysis.computed.running_economy ?? [];
  const [hiddenEconomyStages, setHiddenEconomyStages] = useState<Set<number>>(new Set());
  const visibleRunningEconomy = runningEconomy.filter((row) => !hiddenEconomyStages.has(row.stage_index));

  useEffect(() => {
    setHiddenEconomyStages(new Set());
  }, [analysis.file.filename]);

  const toggleEconomyStage = (stageIndex: number) => {
    setHiddenEconomyStages((current) => {
      const next = new Set(current);
      if (next.has(stageIndex)) {
        next.delete(stageIndex);
      } else {
        next.add(stageIndex);
      }
      return next;
    });
  };

  return (
    <section id="metasoft-analysis-export" className="section-block">
      <div className="section-head">
        <h2>Analyse</h2>
        <p>EC par palier d'echauffement et actions officielles via Python.</p>
      </div>
      <div className="analysis-grid">
        <section className="panel wide-panel">
          <div className="panel-title-row">
            <h2>Economie de course</h2>
            <span className="status-muted">J/kg/m</span>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Palier</th>
                  <th>Vitesse</th>
                  <th>N pts</th>
                  <th>VO2</th>
                  <th>EC</th>
                  <th>DE</th>
                  <th>DECHO</th>
                  <th>DEFAT</th>
                  <th>DEPRO</th>
                  <th>Graphe</th>
                </tr>
              </thead>
              <tbody>
                {runningEconomy.map((row) => {
                  const stage = analysis.warmup_stages.find((item) => item.stage_index === row.stage_index);
                  const hidden = hiddenEconomyStages.has(row.stage_index);
                  return (
                    <tr key={row.stage_index} className={hidden ? "muted-row" : ""}>
                      <td>{row.stage_index}</td>
                      <td>{formatNumber(row.speed_kmh, 1)}</td>
                      <td>{row.point_count}</td>
                      <td>{row.vo2_ml_min ? formatNumber(row.vo2_ml_min / 1000, 2) : "-"}</td>
                      <td className="accent-cell">{formatNumber(row.value_j_kg_m, 0)}</td>
                      <td>{formatNativeDe(stage?.native_de?.de_kcal_h?.value)}</td>
                      <td>{formatNativeDe(stage?.native_de?.decho_kcal_h?.value)}</td>
                      <td>{formatNativeDe(stage?.native_de?.defat_kcal_h?.value)}</td>
                      <td>{formatNativeDe(stage?.native_de?.depro_kcal_h?.value)}</td>
                      <td>
                        <button
                          type="button"
                          className="table-icon-button"
                          onClick={() => toggleEconomyStage(row.stage_index)}
                          aria-pressed={!hidden}
                          title={hidden ? "Afficher dans le graphe" : "Masquer du graphe"}
                        >
                          {hidden ? <Eye size={14} /> : <EyeOff size={14} />}
                          {hidden ? "Afficher" : "Masquer"}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <Plot
            data={[{
              type: "scatter",
              mode: "lines+markers",
              x: visibleRunningEconomy.map((row) => row.speed_kmh),
              y: visibleRunningEconomy.map((row) => row.value_j_kg_m),
              line: { color: "#10d38f", width: 2 },
              marker: { color: "#10d38f", size: 7 },
              name: "EC",
            }]}
            layout={{
              autosize: true,
              paper_bgcolor: "rgba(0,0,0,0)",
              plot_bgcolor: "rgba(0,0,0,0)",
              margin: { l: 44, r: 12, t: 8, b: 36 },
              font: { color: "rgba(226,232,240,0.72)", size: 10 },
              showlegend: false,
              xaxis: { title: "Vitesse (km/h)", gridcolor: "rgba(255,255,255,0.06)" },
              yaxis: { title: "EC", gridcolor: "rgba(255,255,255,0.06)" },
            }}
            config={{ responsive: true, displayModeBar: false }}
            style={{ width: "100%", height: 210 }}
            useResizeHandler
          />
        </section>

        <section id="metasoft-export-json" className="panel action-panel">
          <div className="panel-title-row">
            <h2>Report / export</h2>
            {busy && <span className="status-muted">{busy}</span>}
          </div>
          <div className="action-stack">
            <button type="button" className="secondary-button" onClick={onPreview} disabled={Boolean(busy)}>
              <ShieldCheck size={16} />
              Previsualiser report profil
            </button>
            <button type="button" className="primary-button" onClick={onReport} disabled={Boolean(busy)}>
              <Send size={16} />
              Reporter au profil
            </button>
            {conflicts.length > 0 && (
              <button type="button" className="danger-button" onClick={onReportOverwrite} disabled={Boolean(busy)}>
                Ecraser les champs en conflit
              </button>
            )}
            <button type="button" className="secondary-button" onClick={onExport} disabled={Boolean(busy)}>
              <FileJson size={16} />
              Exporter JSON Valentin
            </button>
          </div>
          {error && <p className="error-text">{error}</p>}
          {preview && <ResultBox title={`Preview: ${preview.status}`} warnings={preview.warnings} />}
          {report && (
            <div className="result-box">
              <strong>Profil mis a jour</strong>
              <p>{report.profile_name}</p>
              <p>{report.updated_paths.length ? report.updated_paths.join(", ") : "Aucun champ modifie."}</p>
            </div>
          )}
          {exportResult && (
            <div className="result-box">
              <strong>Fichiers exportes</strong>
              <p>JSON: {exportResult.json.path}</p>
              <p>Audit: {exportResult.audit.path}</p>
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

function ResultBox({ title, warnings }: { title: string; warnings: MetaSoftWarning[] }) {
  return (
    <div className="result-box">
      <strong>{title}</strong>
      {warnings.length ? warnings.map((warning, index) => (
        <p key={`${warning.code ?? "warning"}-${index}`}>{warning.message}</p>
      )) : <p>Aucun warning.</p>}
    </div>
  );
}

function formatNativeDe(value: number | undefined): string {
  return formatNumber(value, 0);
}
