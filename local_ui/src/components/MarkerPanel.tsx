import { Save } from "lucide-react";
import { MARKER_COLORS } from "../lib/graphConfig";
import { formatNumber, MARKER_NAMES, secondsToClock } from "../lib/markerUtils";
import type { ConfirmedMarkers, DraftMarkers, MetaSoftMarkerName } from "../types/metasoft";

export function MarkerPanel({
  draftMarkers,
  confirmedMarkers,
  dirtyMarkers,
  saving,
  onSave,
}: {
  draftMarkers: DraftMarkers;
  confirmedMarkers: ConfirmedMarkers;
  dirtyMarkers: Set<MetaSoftMarkerName>;
  saving: boolean;
  onSave: () => void;
}) {
  return (
    <section className="panel marker-panel">
      <div className="panel-title-row">
        <h2>Marqueurs</h2>
        <button type="button" className="primary-button" onClick={onSave} disabled={saving}>
          <Save size={16} />
          {saving ? "Sauvegarde..." : "Sauvegarder marqueurs"}
        </button>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Nom</th>
              <th>Mode</th>
              <th>Temps</th>
              <th>Fenetre</th>
              <th>FC</th>
              <th>VO2</th>
              <th>Vitesse</th>
              <th>Statut</th>
            </tr>
          </thead>
          <tbody>
            {MARKER_NAMES.map((name) => {
              const draft = draftMarkers[name];
              const confirmed = confirmedMarkers[name];
              const dirty = dirtyMarkers.has(name);
              const official = confirmed && !dirty ? confirmed : null;
              const row = official ?? draft;
              return (
                <tr key={name}>
                  <td>
                    <span className="marker-name" style={{ color: MARKER_COLORS[name] }}>
                      {name === "VO2_max" ? "VO2max" : name}
                    </span>
                  </td>
                  <td>{draft.mode === "point" ? "Ligne" : "Range"}</td>
                  <td>{secondsToClock(row.t_seconds)}</td>
                  <td>
                    {row.window_start_seconds === null || row.window_end_seconds === null
                      ? "-"
                      : `${secondsToClock(row.window_start_seconds)} - ${secondsToClock(row.window_end_seconds)}`}
                  </td>
                  <td>{formatNumber(row.values.fc_bpm, 0)}</td>
                  <td>{formatNumber(row.values.vo2_l_min, 2)}</td>
                  <td>{formatNumber(row.values.speed_kmh, 1)}</td>
                  <td>
                    {dirty ? (
                      <span className="status-warn">needsSave</span>
                    ) : official ? (
                      <span className="status-ok">Python</span>
                    ) : (
                      <span className="status-muted">preview</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="panel-note">
        Les valeurs Python remplacent la preview apres sauvegarde. Un drag/click repasse le marqueur en needsSave.
      </p>
    </section>
  );
}
