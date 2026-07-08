import { Activity, AlertTriangle } from "lucide-react";
import { formatNumber, secondsToClock } from "../lib/markerUtils";
import type { MetaSoftAnalysis, MetaSoftMetricKey, MetaSoftPoint } from "../types/metasoft";

const CURSOR_VALUES: Array<[MetaSoftMetricKey, string, string, string, number]> = [
  ["ve_vo2", "VE/VO2", "sans unite", "#2437d8", 1],
  ["vo2_l_min", "V'O2", "L/min", "#0057ff", 2],
  ["vo2_ml_kg_min", "V'O2/kg", "mL/kg/min", "#008bff", 1],
  ["ve_l_min", "V'E", "L/min", "#c80000", 1],
  ["bf_per_min", "BF", "br/min", "#008000", 1],
  ["rer", "RER", "sans unite", "#111111", 2],
  ["speed_kmh", "Vitesse", "km/h", "#007c65", 1],
];

export function CursorRail({
  analysis,
  cursorPoint,
}: {
  analysis: MetaSoftAnalysis;
  cursorPoint: MetaSoftPoint | null;
}) {
  const point = cursorPoint ?? analysis.points[0] ?? null;
  return (
    <aside className="side-rail">
      <section className="panel">
        <div className="panel-title-row">
          <h2>Valeurs au curseur</h2>
          <span className="live-dot">live</span>
        </div>
        <div className="cursor-time">
          <Activity size={14} />
          {point ? `${secondsToClock(point.t_seconds)} / ${point.phase ?? "phase absente"}` : "Survolez un graphe"}
        </div>
        <div className="cursor-values">
          {CURSOR_VALUES.map(([key, label, unit, color, digits]) => {
            const value = point?.values[key];
            if (!analysis.metrics[key]) return null;
            return (
              <div key={key} className="cursor-card">
                <div className="cursor-card-head" style={{ backgroundColor: color }}>
                  <span>{label}</span>
                  <span>{unit}</span>
                </div>
                <strong>{formatNumber(value, digits)}</strong>
              </div>
            );
          })}
        </div>
      </section>

      <section className="panel">
        <div className="panel-title-row">
          <h2>Warnings</h2>
          <span className="status-warn">{analysis.warnings.length}</span>
        </div>
        <div className="warning-list compact">
          {analysis.warnings.slice(0, 5).map((warning, index) => (
            <p key={`${warning.code ?? "warning"}-${index}`}>
              <AlertTriangle size={14} />
              {warning.message}
            </p>
          ))}
          {!analysis.warnings.length && <p>Aucun warning backend.</p>}
        </div>
      </section>
    </aside>
  );
}
